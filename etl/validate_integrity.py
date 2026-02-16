"""
Data integrity validation for CIA Factbook Archive (2000-2025).
Checks field counts, US benchmark data, year-over-year consistency,
and source provenance.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pyodbc
import re

conn = pyodbc.connect(
    'DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=CIA_WorldFactbook;'
    'Trusted_Connection=yes;TrustServerCertificate=yes;'
)
cursor = conn.cursor()

SEP = "=" * 70

# ============================================================
# 1. STRUCTURAL OVERVIEW
# ============================================================
print(f"\n{SEP}")
print("  1. STRUCTURAL OVERVIEW (2000-2025)")
print(SEP)
cursor.execute("""
    SELECT c.Year, c.Source, COUNT(DISTINCT c.CountryID) as Countries
    FROM Countries c WHERE c.Year >= 2000
    GROUP BY c.Year, c.Source ORDER BY c.Year
""")
year_info = cursor.fetchall()

print(f"  {'Year':<6} {'Src':<5} {'Countries':<11} {'Categories':<12} {'Fields':<10} {'Avg F/C':<8} {'Cats/C':<7}")
print(f"  {'-'*5:<6} {'-'*4:<5} {'-'*9:<11} {'-'*10:<12} {'-'*8:<10} {'-'*6:<8} {'-'*5:<7}")
for yr, src, cnt in year_info:
    cursor.execute("SELECT COUNT(*) FROM CountryCategories cc JOIN Countries c ON cc.CountryID=c.CountryID WHERE c.Year=?", yr)
    cats = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM CountryFields cf JOIN Countries c ON cf.CountryID=c.CountryID WHERE c.Year=?", yr)
    flds = cursor.fetchone()[0]
    avg_f = flds / max(cnt, 1)
    avg_c = cats / max(cnt, 1)
    print(f"  {yr:<6} {src:<5} {cnt:<11} {cats:<12} {flds:<10,} {avg_f:<8.1f} {avg_c:<7.1f}")

# ============================================================
# 2. US POPULATION BENCHMARK (known ground truth)
# ============================================================
print(f"\n{SEP}")
print("  2. US POPULATION BENCHMARK")
print(SEP)
# Known approximate US populations by year (Census/CIA estimates, millions)
known_us_pop = {
    2000: 275, 2001: 278, 2002: 280, 2003: 283, 2004: 290, 2005: 296,
    2006: 298, 2007: 301, 2008: 304, 2009: 307, 2010: 310, 2011: 314,
    2012: 314, 2013: 316, 2014: 319, 2015: 321, 2016: 324, 2017: 327,
    2018: 329, 2019: 330, 2020: 333, 2021: 332, 2022: 337, 2023: 339,
    2024: 340, 2025: 338,
}

print(f"  {'Year':<6} {'DB Population Field':<55} {'Expected ~M':<12} {'Match?'}")
print(f"  {'-'*5:<6} {'-'*50:<55} {'-'*10:<12} {'-'*6}")
pop_matches = 0
pop_total = 0
for yr in range(2000, 2026):
    cursor.execute("""
        SELECT TOP 1 cf.Content
        FROM Countries c
        JOIN CountryCategories cc ON c.CountryID = cc.CountryID
        JOIN CountryFields cf ON cc.CategoryID = cf.CategoryID
        WHERE c.Year = ? AND c.Name LIKE '%United States%'
          AND c.Name NOT LIKE '%Minor%' AND c.Name NOT LIKE '%Virgin%'
          AND cf.FieldName LIKE '%Population%'
          AND cc.CategoryTitle IN ('People', 'People and Society')
          AND cf.Content LIKE '%[0-9]%'
          AND cf.Content NOT LIKE '%no indigenous%'
          AND LEN(cf.Content) > 5
        ORDER BY cf.FieldID
    """, yr)
    row = cursor.fetchone()
    pop_text = row[0][:50] if row else "NOT FOUND"

    # Extract number from text
    nums = re.findall(r'[\d,]+', pop_text)
    db_pop_m = None
    for n in nums:
        val = int(n.replace(',', ''))
        if 200_000_000 < val < 400_000_000:
            db_pop_m = val / 1_000_000
            break

    expected = known_us_pop.get(yr, 0)
    if db_pop_m:
        ok = abs(db_pop_m - expected) < 10  # within 10M
        pop_matches += 1 if ok else 0
        match_str = "OK" if ok else f"MISMATCH ({db_pop_m:.0f}M vs {expected}M)"
    else:
        match_str = "NO NUM"
        ok = False
    pop_total += 1
    print(f"  {yr:<6} {pop_text:<55} {expected:<12} {match_str}")

print(f"\n  Population benchmark: {pop_matches}/{pop_total} years match within 10M")

# ============================================================
# 3. US GDP BENCHMARK
# ============================================================
print(f"\n{SEP}")
print("  3. US GDP BENCHMARK")
print(SEP)
# Known approximate US GDP (trillions, nominal)
known_gdp = {
    2000: 10, 2005: 13, 2010: 15, 2015: 18, 2020: 21, 2025: 29,
}
for yr in sorted(known_gdp.keys()):
    cursor.execute("""
        SELECT TOP 1 LEFT(cf.Content, 80)
        FROM Countries c
        JOIN CountryCategories cc ON c.CountryID = cc.CountryID
        JOIN CountryFields cf ON cc.CategoryID = cf.CategoryID
        WHERE c.Year = ? AND c.Name LIKE '%United States%'
          AND c.Name NOT LIKE '%Minor%' AND c.Name NOT LIKE '%Virgin%'
          AND (cf.FieldName LIKE '%GDP%' OR cf.FieldName LIKE '%Real GDP%')
          AND cc.CategoryTitle = 'Economy'
        ORDER BY cf.FieldID
    """, yr)
    row = cursor.fetchone()
    gdp_text = row[0] if row else "NOT FOUND"
    print(f"  {yr}: {gdp_text}")

# ============================================================
# 4. COUNTRY COUNT CONSISTENCY
# ============================================================
print(f"\n{SEP}")
print("  4. COUNTRY COUNT YEAR-OVER-YEAR DELTAS")
print(SEP)
cursor.execute("""
    SELECT Year, COUNT(*) as cnt FROM Countries WHERE Year >= 2000
    GROUP BY Year ORDER BY Year
""")
counts = cursor.fetchall()
prev = None
for yr, cnt in counts:
    delta = f"  ({cnt - prev:+d})" if prev else ""
    flag = " <-- large change" if prev and abs(cnt - prev) > 10 else ""
    print(f"  {yr}: {cnt} countries{delta}{flag}")
    prev = cnt

# ============================================================
# 5. DATA SOURCE PROVENANCE
# ============================================================
print(f"\n{SEP}")
print("  5. DATA SOURCE PROVENANCE")
print(SEP)
sources = {
    '2000': 'Wayback Machine HTML zip (web.archive.org/web/*/cia.gov/factbook)',
    '2001-2008': 'Wayback Machine HTML zips, re-parsed with parse_table_format (build_archive.py)',
    '2009-2014': 'Wayback Machine HTML zips, re-parsed with parse_collapsiblepanel_format (build_archive.py)',
    '2015-2017': 'Wayback Machine HTML zips, re-parsed with parse_expandcollapse_format (build_archive.py)',
    '2018-2020': 'Wayback Machine HTML zips, re-parsed with parse_modern_format (build_archive.py)',
    '2021-2025': 'factbook/cache.factbook.json GitHub repo, year-specific git commits (reload_json_years.py)',
}
for years, desc in sources.items():
    print(f"  {years:12s}  {desc}")

# ============================================================
# 6. FIELD PROGRESSION SMOOTHNESS
# ============================================================
print(f"\n{SEP}")
print("  6. FIELD PROGRESSION CHECK (year-over-year % change)")
print(SEP)
cursor.execute("""
    SELECT c.Year, COUNT(cf.FieldID) as flds
    FROM Countries c
    JOIN CountryFields cf ON c.CountryID = cf.CountryID
    WHERE c.Year >= 2000
    GROUP BY c.Year ORDER BY c.Year
""")
field_counts = cursor.fetchall()
prev_flds = None
anomalies = []
for yr, flds in field_counts:
    if prev_flds:
        pct = (flds - prev_flds) / prev_flds * 100
        flag = ""
        if abs(pct) > 15:
            flag = " <-- ANOMALY"
            anomalies.append((yr, pct))
        print(f"  {yr}: {flds:>7,} fields  ({pct:+.1f}%){flag}")
    else:
        print(f"  {yr}: {flds:>7,} fields")
    prev_flds = flds

# ============================================================
# 7. CATEGORY COVERAGE CHECK
# ============================================================
print(f"\n{SEP}")
print("  7. COUNTRIES MISSING KEY CATEGORIES")
print(SEP)
key_cats = ['Economy', 'Geography', 'Government', 'People', 'People and Society']
for yr in range(2000, 2026):
    cursor.execute("SELECT COUNT(DISTINCT CountryID) FROM Countries WHERE Year = ?", yr)
    total = cursor.fetchone()[0]
    # Which category to check depends on year
    if yr <= 2010:
        cat = 'People'
    else:
        cat = 'People and Society'

    cursor.execute("""
        SELECT COUNT(DISTINCT c.CountryID)
        FROM Countries c
        JOIN CountryCategories cc ON c.CountryID = cc.CountryID
        WHERE c.Year = ? AND cc.CategoryTitle = ?
    """, yr, cat)
    with_cat = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT c.CountryID)
        FROM Countries c
        JOIN CountryCategories cc ON c.CountryID = cc.CountryID
        WHERE c.Year = ? AND cc.CategoryTitle = 'Economy'
    """, yr)
    with_econ = cursor.fetchone()[0]

    missing_people = total - with_cat
    missing_econ = total - with_econ
    flags = []
    if missing_people > 10:
        flags.append(f"{missing_people} missing {cat}")
    if missing_econ > 10:
        flags.append(f"{missing_econ} missing Economy")
    if flags:
        print(f"  {yr}: {'; '.join(flags)}")

# ============================================================
# 8. SPOT CHECK: CHINA POPULATION
# ============================================================
print(f"\n{SEP}")
print("  8. CHINA POPULATION SPOT CHECK")
print(SEP)
for yr in [2000, 2005, 2010, 2015, 2020, 2025]:
    cursor.execute("""
        SELECT TOP 1 LEFT(cf.Content, 60)
        FROM Countries c
        JOIN CountryCategories cc ON c.CountryID = cc.CountryID
        JOIN CountryFields cf ON cc.CategoryID = cf.CategoryID
        WHERE c.Year = ? AND c.Name LIKE '%China%' AND c.Name NOT LIKE '%Taiwan%'
          AND cf.FieldName LIKE '%Population%'
          AND cc.CategoryTitle IN ('People', 'People and Society')
          AND cf.Content LIKE '%[0-9]%'
          AND LEN(cf.Content) > 5
        ORDER BY cf.FieldID
    """, yr)
    row = cursor.fetchone()
    print(f"  {yr}: {row[0] if row else 'NOT FOUND'}")

# ============================================================
# 9. NULL / EMPTY FIELD CHECK
# ============================================================
print(f"\n{SEP}")
print("  9. DATA QUALITY: NULL/EMPTY FIELDS")
print(SEP)
cursor.execute("""
    SELECT c.Year,
           SUM(CASE WHEN cf.Content IS NULL OR LTRIM(RTRIM(cf.Content)) = '' THEN 1 ELSE 0 END) as empty,
           COUNT(*) as total
    FROM Countries c
    JOIN CountryFields cf ON c.CountryID = cf.CountryID
    WHERE c.Year >= 2000
    GROUP BY c.Year ORDER BY c.Year
""")
for yr, empty, total in cursor.fetchall():
    pct = empty / max(total, 1) * 100
    flag = " <-- high" if pct > 5 else ""
    if empty > 0:
        print(f"  {yr}: {empty:,} empty of {total:,} ({pct:.1f}%){flag}")

# ============================================================
# SUMMARY
# ============================================================
print(f"\n{SEP}")
print("  CONFIDENCE ASSESSMENT")
print(SEP)

issues = []
if pop_matches < pop_total:
    issues.append(f"Population benchmark: {pop_matches}/{pop_total} years matched")
if anomalies:
    issues.append(f"Field count anomalies: {', '.join(f'{yr}({p:+.0f}%)' for yr, p in anomalies)}")

if not issues:
    print("  HIGH CONFIDENCE - all benchmarks pass")
else:
    for i in issues:
        print(f"  NOTE: {i}")

conn.close()
