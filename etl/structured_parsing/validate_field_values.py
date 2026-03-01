"""
Validate FieldValues — check counts, coverage, and spot-check ground truth.
Reads from both CIA_WorldFactbook and CIA_WorldFactbook_Extended_Sub_Topics.

Usage:
    python etl/structured_parsing/validate_field_values.py
"""
import pyodbc
import sys

SOURCE_DB = "CIA_WorldFactbook"
TARGET_DB = "CIA_WorldFactbook_Extended_Sub_Topics"

CONN_STR_SOURCE = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    f"DATABASE={SOURCE_DB};"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)
CONN_STR_TARGET = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    f"DATABASE={TARGET_DB};"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


def main():
    conn_src = pyodbc.connect(CONN_STR_SOURCE)
    conn_tgt = pyodbc.connect(CONN_STR_TARGET)
    cur_src = conn_src.cursor()
    cur_tgt = conn_tgt.cursor()

    passed = 0
    failed = 0
    warnings = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            print(f"  PASS  {name}")
            passed += 1
        else:
            print(f"  FAIL  {name}  {detail}")
            failed += 1

    def warn(name, detail=""):
        nonlocal warnings
        print(f"  WARN  {name}  {detail}")
        warnings += 1

    print("=" * 70)
    print("FieldValues Validation")
    print("=" * 70)

    # -- 1. Row counts ---
    print("\n-- Row Counts --")
    cf_count = cur_src.execute("SELECT COUNT(*) FROM CountryFields").fetchone()[0]
    fv_count = cur_tgt.execute("SELECT COUNT(*) FROM FieldValues").fetchone()[0]
    print(f"  CountryFields:  {cf_count:>12,}")
    print(f"  FieldValues:    {fv_count:>12,}")
    ratio = fv_count / cf_count if cf_count > 0 else 0
    print(f"  Expansion:      {ratio:>12.2f}x")
    check("FieldValues > CountryFields", fv_count > cf_count,
          f"({fv_count} vs {cf_count})")

    # -- 2. Coverage ---
    print("\n-- Coverage --")
    covered = cur_tgt.execute("""
        SELECT COUNT(DISTINCT FieldID) FROM FieldValues
    """).fetchone()[0]
    coverage_pct = covered / cf_count * 100 if cf_count > 0 else 0
    print(f"  CountryFields with FieldValues: {covered:,} / {cf_count:,} ({coverage_pct:.1f}%)")
    check("Coverage >= 95%", coverage_pct >= 95, f"({coverage_pct:.1f}%)")

    # Fields without any FieldValues
    uncovered = cf_count - covered
    if uncovered > 0:
        # Sample some uncovered fields
        sample = cur_src.execute("""
            SELECT TOP 10 cf.FieldID, cf.FieldName, LEFT(cf.Content, 80)
            FROM CountryFields cf
            WHERE cf.FieldID NOT IN (SELECT DISTINCT FieldID FROM CIA_WorldFactbook_Extended_Sub_Topics.dbo.FieldValues)
              AND cf.Content IS NOT NULL AND LEN(cf.Content) > 0
        """).fetchall()
        if sample:
            print(f"  Uncovered sample ({uncovered:,} total missing):")
            for fid, fname, snippet in sample:
                print(f"    FieldID={fid}  {fname}: {snippet}")

    # -- 3. Numeric coverage ---
    print("\n-- Numeric Coverage --")
    numeric_count = cur_tgt.execute(
        "SELECT COUNT(*) FROM FieldValues WHERE NumericVal IS NOT NULL"
    ).fetchone()[0]
    numeric_pct = numeric_count / fv_count * 100 if fv_count > 0 else 0
    print(f"  Rows with NumericVal: {numeric_count:,} / {fv_count:,} ({numeric_pct:.1f}%)")
    check("Numeric coverage >= 20%", numeric_pct >= 20, f"({numeric_pct:.1f}%)")

    # -- 4. SubField distribution ---
    print("\n-- Top 20 SubFields --")
    top_subs = cur_tgt.execute("""
        SELECT TOP 20 SubField, COUNT(*) AS cnt
        FROM FieldValues
        GROUP BY SubField
        ORDER BY cnt DESC
    """).fetchall()
    for sub, cnt in top_subs:
        print(f"  {sub:<40} {cnt:>10,}")

    # -- 5. Per-year breakdown ---
    print("\n-- Per-Year Breakdown --")
    print(f"  {'Year':<6} {'Fields':>10} {'Values':>10} {'Ratio':>8}")
    print(f"  {'-'*6} {'-'*10} {'-'*10} {'-'*8}")
    year_stats = cur_src.execute("""
        SELECT c.Year,
               COUNT(*) AS field_count,
               (SELECT COUNT(*) FROM CIA_WorldFactbook_Extended_Sub_Topics.dbo.FieldValues fv
                WHERE fv.FieldID IN (
                    SELECT cf2.FieldID FROM CountryFields cf2
                    JOIN Countries c2 ON cf2.CountryID = c2.CountryID
                    WHERE c2.Year = c.Year
                )) AS value_count
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        GROUP BY c.Year
        ORDER BY c.Year
    """).fetchall()
    for year, fc, vc in year_stats:
        r = vc / fc if fc > 0 else 0
        print(f"  {year:<6} {fc:>10,} {vc:>10,} {r:>8.2f}x")

    # -- 6. Spot checks ---
    print("\n-- Spot Checks --")

    spot_checks = [
        # (description, year, country_pattern, canonical_field, sub_field, expected_val, tolerance)
        ("US 2025 Population total", 2025, 'United States', 'Population', 'total', 338016259, 1000000),
        ("US 2025 Area total", 2025, 'United States', 'Area', 'total', 9833517, 10),
        ("US 2025 Life expectancy total", 2025, 'United States', 'Life expectancy at birth', 'total_population', 80.0, 3.0),
        ("Japan 2025 Military expenditures", 2025, 'Japan', 'Military expenditures', None, 1.4, 0.5),
        ("China 2025 Population total", 2025, 'China', 'Population', 'total', 1400000000, 50000000),
        ("Russia 2025 Area total", 2025, 'Russia', 'Area', 'total', 17098242, 100),
    ]

    for desc, year, country_pat, canon_field, sub_field, expected, tol in spot_checks:
        # Find the FieldID
        query = """
            SELECT TOP 1 cf.FieldID
            FROM CountryFields cf
            JOIN Countries c ON cf.CountryID = c.CountryID
            JOIN FieldNameMappings fnm ON cf.FieldName = fnm.OriginalName
            WHERE c.Year = ?
              AND c.Name = ?
              AND fnm.CanonicalName = ?
              AND fnm.IsNoise = 0
        """
        row = cur_src.execute(query, year, country_pat, canon_field).fetchone()
        if not row:
            warn(desc, "FieldID not found in source")
            continue

        field_id = row[0]

        # Get parsed value
        if sub_field:
            val_row = cur_tgt.execute("""
                SELECT NumericVal FROM FieldValues
                WHERE FieldID = ? AND SubField = ?
            """, field_id, sub_field).fetchone()
        else:
            # Get first numeric value for any sub_field
            val_row = cur_tgt.execute("""
                SELECT TOP 1 NumericVal FROM FieldValues
                WHERE FieldID = ? AND NumericVal IS NOT NULL
            """, field_id).fetchone()

        if not val_row or val_row[0] is None:
            warn(desc, "No numeric value found in FieldValues")
            continue

        actual = val_row[0]
        diff = abs(actual - expected)
        check(f"{desc}: expected ~{expected:,.1f}, got {actual:,.1f}",
              diff <= tol, f"(diff={diff:,.1f}, tolerance={tol:,.1f})")

    # -- 7. Parser coverage by canonical field ---
    print("\n-- Parser vs Generic Coverage --")
    # Count how many FieldValues came from registered vs generic parsers
    registered_fields = cur_src.execute("""
        SELECT COUNT(DISTINCT cf.FieldID)
        FROM CountryFields cf
        JOIN FieldNameMappings fnm ON cf.FieldName = fnm.OriginalName
        WHERE fnm.CanonicalName IN (
            'Area', 'Population', 'Life expectancy at birth', 'Age structure',
            'Birth rate', 'Death rate', 'Infant mortality rate', 'Total fertility rate',
            'Real GDP (purchasing power parity)', 'GDP (purchasing power parity)',
            'Real GDP per capita', 'GDP - per capita (PPP)', 'GDP (official exchange rate)',
            'Military expenditures', 'Exports', 'Imports', 'Budget', 'Land use',
            'Electricity', 'Unemployment rate', 'Inflation rate (consumer prices)',
            'Real GDP growth rate', 'GDP - real growth rate', 'Population growth rate',
            'Dependency ratios', 'Urbanization', 'Elevation', 'Geographic coordinates',
            'Coastline', 'Median age', 'Current account balance',
            'Reserves of foreign exchange and gold', 'Public debt',
            'Industrial production growth rate',
            'Sex ratio', 'Literacy', 'Maritime claims', 'Natural gas',
            'Internet users', 'Telephones - fixed lines', 'Telephones - mobile cellular',
            'Debt - external',
            'GDP - composition, by sector of origin',
            'Household income or consumption by percentage share',
            'School life expectancy (primary to tertiary education)',
            'Youth unemployment rate (ages 15-24)', 'Unemployment, youth ages 15-24',
            'Carbon dioxide emissions', 'Carbon dioxide emissions from consumption of energy',
            'Total water withdrawal', 'Freshwater withdrawal (domestic/industrial/agricultural)',
            'Broadband - fixed subscriptions',
            'Drinking water source', 'Sanitation facility access',
            'Waste and recycling', 'Revenue from forest resources'
        ) AND fnm.IsNoise = 0
    """).fetchone()[0]

    print(f"  Fields with registered parser: {registered_fields:,}")
    print(f"  Fields using generic fallback: {cf_count - registered_fields:,}")
    print(f"  Registered coverage: {registered_fields / cf_count * 100:.1f}%")

    # -- 8. SourceFragment coverage ---
    print("\n-- SourceFragment Coverage --")
    frag_count = cur_tgt.execute(
        "SELECT COUNT(*) FROM FieldValues WHERE SourceFragment IS NOT NULL"
    ).fetchone()[0]
    frag_pct = frag_count / fv_count * 100 if fv_count > 0 else 0
    print(f"  Rows with SourceFragment: {frag_count:,} / {fv_count:,} ({frag_pct:.1f}%)")
    check("SourceFragment coverage >= 95%", frag_pct >= 95, f"({frag_pct:.1f}%)")

    # -- 9. New parser spot checks ---
    print("\n-- New Parser Spot Checks --")
    new_spot_checks = [
        ("US 2025 Sex ratio at_birth", 2025, 'United States', 'Sex ratio', 'at_birth', 1.05, 0.02),
        ("US 2025 Sex ratio total_population", 2025, 'United States', 'Sex ratio', 'total_population', 0.97, 0.05),
        ("India 2025 Literacy total_population", 2025, 'India', 'Literacy', 'total_population', 81.7, 2.0),
        ("India 2025 Literacy male", 2025, 'India', 'Literacy', 'male', 88.3, 2.0),
        ("US 2025 Maritime claims territorial_sea", 2025, 'United States', 'Maritime claims', 'territorial_sea', 12.0, 0.1),
        ("US 2025 Maritime claims EEZ", 2025, 'United States', 'Maritime claims', 'exclusive_economic_zone', 200.0, 0.1),
        # v3.2 spot checks
        ("US 2025 GDP composition agriculture", 2025, 'United States', 'GDP - composition, by sector of origin', 'agriculture', 0.9, 0.5),
        ("US 2025 GDP composition services", 2025, 'United States', 'GDP - composition, by sector of origin', 'services', 79.7, 5.0),
        ("US 2025 Household income lowest 10%", 2025, 'United States', 'Household income or consumption by percentage share', 'lowest_10pct', 1.8, 0.5),
        ("US 2025 Household income highest 10%", 2025, 'United States', 'Household income or consumption by percentage share', 'highest_10pct', 30.4, 2.0),
        ("US 2025 School life expectancy total", 2025, 'United States', 'School life expectancy (primary to tertiary education)', 'total', 16.0, 2.0),
        ("US 2025 Youth unemployment total", 2025, 'United States', 'Youth unemployment rate (ages 15-24)', 'total', 9.4, 3.0),
        ("US 2025 Youth unemployment female", 2025, 'United States', 'Youth unemployment rate (ages 15-24)', 'female', 8.3, 3.0),
        ("US 2025 CO2 emissions total", 2025, 'United States', 'Carbon dioxide emissions', 'total', 4.795e9, 1e9),
        ("US 2025 Broadband total", 2025, 'United States', 'Broadband - fixed subscriptions', 'total', 131e6, 20e6),
        ("US 2025 Broadband per 100", 2025, 'United States', 'Broadband - fixed subscriptions', 'subscriptions_per_100', 38.0, 5.0),
        ("US 2025 Drinking water improved_urban", 2025, 'United States', 'Drinking water source', 'improved_urban', 100.0, 1.0),
        ("US 2025 Sanitation improved_total", 2025, 'United States', 'Sanitation facility access', 'improved_total', 99.6, 1.0),
    ]
    for desc, year, country_pat, canon_field, sub_field, expected, tol in new_spot_checks:
        row = cur_src.execute("""
            SELECT TOP 1 cf.FieldID
            FROM CountryFields cf
            JOIN Countries c ON cf.CountryID = c.CountryID
            JOIN FieldNameMappings fnm ON cf.FieldName = fnm.OriginalName
            WHERE c.Year = ? AND c.Name = ? AND fnm.CanonicalName = ? AND fnm.IsNoise = 0
        """, year, country_pat, canon_field).fetchone()
        if not row:
            warn(desc, "FieldID not found in source")
            continue
        val_row = cur_tgt.execute("""
            SELECT NumericVal FROM FieldValues WHERE FieldID = ? AND SubField = ?
        """, row[0], sub_field).fetchone()
        if not val_row or val_row[0] is None:
            warn(desc, "No numeric value found")
            continue
        actual = val_row[0]
        diff = abs(actual - expected)
        check(f"{desc}: expected ~{expected}, got {actual}",
              diff <= tol, f"(diff={diff}, tol={tol})")

    # -- Summary ---
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed, {warnings} warnings")
    if failed == 0:
        print("All checks passed!")
    else:
        print("Some checks FAILED — review output above.")
    print("=" * 70)

    conn_src.close()
    conn_tgt.close()
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
