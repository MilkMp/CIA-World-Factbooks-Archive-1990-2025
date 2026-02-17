"""
Data integrity validation for CIA Factbook Archive (1990-2025).
Checks structural completeness, MasterCountryID linkage, field counts,
benchmark data, year-over-year consistency, and source provenance.
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

SEP = "=" * 72
issues = []

# ============================================================
# 1. STRUCTURAL OVERVIEW (ALL YEARS)
# ============================================================
print(f"\n{SEP}")
print("  1. STRUCTURAL OVERVIEW (1990-2025)")
print(SEP)
cursor.execute("""
    SELECT c.Year, c.Source, COUNT(DISTINCT c.CountryID) as Countries
    FROM Countries c
    GROUP BY c.Year, c.Source ORDER BY c.Year
""")
year_info = cursor.fetchall()

print(f"  {'Year':<6} {'Src':<6} {'Countries':<11} {'Categories':<12} {'Fields':<10} {'Avg F/C':<8} {'Cats/C':<7}")
print(f"  {'-'*5:<6} {'-'*5:<6} {'-'*9:<11} {'-'*10:<12} {'-'*8:<10} {'-'*6:<8} {'-'*5:<7}")
for yr, src, cnt in year_info:
    cursor.execute("SELECT COUNT(*) FROM CountryCategories cc JOIN Countries c ON cc.CountryID=c.CountryID WHERE c.Year=?", yr)
    cats = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM CountryFields cf JOIN Countries c ON cf.CountryID=c.CountryID WHERE c.Year=?", yr)
    flds = cursor.fetchone()[0]
    avg_f = flds / max(cnt, 1)
    avg_c = cats / max(cnt, 1)
    src_str = src[:5] if src else '?'
    flag = ""
    if avg_f < 30:
        flag = " <-- LOW avg fields"
        issues.append(f"Year {yr}: low avg fields/country ({avg_f:.0f})")
    print(f"  {yr:<6} {src_str:<6} {cnt:<11} {cats:<12} {flds:<10,} {avg_f:<8.1f} {avg_c:<7.1f}{flag}")

# ============================================================
# 2. MASTERCOUNTRYID LINKAGE CHECK
# ============================================================
print(f"\n{SEP}")
print("  2. MASTERCOUNTRYID LINKAGE CHECK")
print(SEP)

# 2a. NULL MasterCountryID
cursor.execute("""
    SELECT c.Year, c.Code, c.Name
    FROM Countries c
    WHERE c.MasterCountryID IS NULL
    ORDER BY c.Year, c.Name
""")
nulls = cursor.fetchall()
if nulls:
    print(f"\n  WARNING: {len(nulls)} countries with NULL MasterCountryID:")
    for yr, code, name in nulls:
        print(f"    {yr}  {code:<4} {name}")
    issues.append(f"NULL MasterCountryID: {len(nulls)} rows")
else:
    print(f"\n  PASS -- No NULL MasterCountryID entries")

# 2b. Suspect MasterCountryID mismatches (name vs master canonical name)
print()
cursor.execute("""
    SELECT c.Year, c.Code, c.Name, mc.CanonicalName, mc.MasterCountryID
    FROM Countries c
    JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
    ORDER BY c.Year, c.Name
""")
all_rows = cursor.fetchall()

# Known valid aliases: historical name -> modern canonical name
valid_aliases = {
    'soviet union': 'russia',
    'burma': 'myanmar',
    'ivory coast': "cote d'ivoire",
    'zaire': 'congo, democratic republic of the',
    'czech republic': 'czechia',
    'swaziland': 'eswatini',
    'cape verde': 'cabo verde',
    'turkey': 'turkiye',
    'kazakstan': 'kazakhstan',
    'man, isle of': 'isle of man',
    'german democratic republic': 'germany',
    'cocos islands': 'cocos (keeling) islands',
    'wake atoll': 'wake island',
    'yugoslavia': 'serbia and montenegro',
    'macedonia, the former yugoslav republic of': 'north macedonia',
    'the former yugoslav republic of macedonia': 'north macedonia',
    'st. helena': 'saint helena, ascension, and tristan da cunha',
    'st. kitts and nevis': 'saint kitts and nevis',
    'st. lucia': 'saint lucia',
    'st. pierre and miquelon': 'saint pierre and miquelon',
    'st. vincent and the grenadines': 'saint vincent and the grenadines',
    'east timor': 'timor-leste',
    'burma (myanmar)': 'myanmar',
    'congo, republic of the': 'congo, republic of the',
    'korea, north': 'korea, north',
    'korea, south': 'korea, south',
    'micronesia, federated states of': 'micronesia, federated states of',
    'congo, democratic republic of the': 'congo, democratic republic of the',
}

suspect = []
for yr, code, name, canonical, mid in all_rows:
    n = name.lower().strip()
    can = canonical.lower().strip()
    # Check if name matches canonical (or is a known alias)
    if n == can:
        continue
    if n in valid_aliases and valid_aliases[n] == can:
        continue
    # Fuzzy: check if either contains the other
    if n in can or can in n:
        continue
    # Check if first significant word matches
    n_words = [w for w in n.replace(',', '').split() if w not in ('the', 'of', 'and', 'republic')]
    c_words = [w for w in can.replace(',', '').split() if w not in ('the', 'of', 'and', 'republic')]
    if n_words and c_words and n_words[0] == c_words[0]:
        continue
    suspect.append((yr, code, name, canonical, mid))

if suspect:
    # Deduplicate by (name, canonical) to show unique mismatches
    seen = set()
    unique_suspects = []
    for yr, code, name, canonical, mid in suspect:
        key = (name.lower(), canonical.lower())
        if key not in seen:
            seen.add(key)
            unique_suspects.append((yr, code, name, canonical, mid))

    print(f"  REVIEW: {len(unique_suspects)} unique name-to-master mismatches (may be valid):")
    for yr, code, name, canonical, mid in unique_suspects[:30]:
        print(f"    {yr}  {name:<40} -> MasterID {mid} ({canonical})")
    if len(unique_suspects) > 30:
        print(f"    ... and {len(unique_suspects) - 30} more")
else:
    print(f"  PASS -- No suspect MasterCountryID mismatches")

# 2c. ISOAlpha2 coverage (needed for analysis maps)
cursor.execute("""
    SELECT COUNT(DISTINCT c.CountryID)
    FROM Countries c
    JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
    WHERE mc.ISOAlpha2 IS NULL AND mc.EntityType = 'sovereign'
""")
no_iso = cursor.fetchone()[0]
if no_iso > 0:
    print(f"\n  WARNING: {no_iso} sovereign country records lack ISO Alpha-2 codes")
    cursor.execute("""
        SELECT DISTINCT mc.CanonicalName, mc.CanonicalCode
        FROM Countries c
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        WHERE mc.ISOAlpha2 IS NULL AND mc.EntityType = 'sovereign'
    """)
    for name, code in cursor.fetchall():
        print(f"    {code} {name}")
    issues.append(f"Sovereign countries without ISO code: {no_iso} records")
else:
    print(f"\n  PASS -- All sovereign countries have ISO Alpha-2 codes")

# ============================================================
# 3. COUNTRY COUNT YEAR-OVER-YEAR DELTAS (ALL YEARS)
# ============================================================
print(f"\n{SEP}")
print("  3. COUNTRY COUNT YEAR-OVER-YEAR DELTAS (1990-2025)")
print(SEP)
cursor.execute("""
    SELECT Year, COUNT(*) as cnt FROM Countries
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
# 4. US POPULATION BENCHMARK (known ground truth)
# ============================================================
print(f"\n{SEP}")
print("  4. US POPULATION BENCHMARK")
print(SEP)
known_us_pop = {
    1990: 249, 1991: 252, 1992: 255, 1993: 258, 1994: 260, 1995: 263,
    1996: 266, 1997: 268, 1998: 270, 1999: 273,
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
for yr in range(1990, 2026):
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

    nums = re.findall(r'[\d,]+', pop_text)
    db_pop_m = None
    for n in nums:
        val = int(n.replace(',', ''))
        if 200_000_000 < val < 400_000_000:
            db_pop_m = val / 1_000_000
            break

    expected = known_us_pop.get(yr, 0)
    if db_pop_m:
        ok = abs(db_pop_m - expected) < 15  # within 15M (wider for early years)
        pop_matches += 1 if ok else 0
        match_str = "OK" if ok else f"MISMATCH ({db_pop_m:.0f}M vs {expected}M)"
    else:
        match_str = "NO NUM"
        ok = False
    pop_total += 1
    print(f"  {yr:<6} {pop_text:<55} {expected:<12} {match_str}")

print(f"\n  Population benchmark: {pop_matches}/{pop_total} years match")
if pop_matches < pop_total:
    issues.append(f"Population benchmark: {pop_matches}/{pop_total} years matched")

# ============================================================
# 5. KEY COUNTRY PRESENCE CHECK
# ============================================================
print(f"\n{SEP}")
print("  5. KEY COUNTRY PRESENCE CHECK")
print(SEP)
# These countries should exist in every year (or from their independence year)
key_countries = {
    'United States': 1990,
    'China': 1990,
    'Russia': 1992,   # Soviet Union before 1992
    'Soviet Union': 1990,  # only 1990-1991
    'France': 1990,
    'Germany': 1990,
    'Japan': 1990,
    'United Kingdom': 1990,
    'India': 1990,
    'Brazil': 1990,
    'Turk': 1990,  # matches Turkey, Turkiye, Turkey (Turkiye)
    'Australia': 1990,
    'Canada': 1990,
    'Iran': 1990,
    'Israel': 1990,
    'Ukraine': 1992,
}

for country, start_yr in key_countries.items():
    if country == 'Soviet Union':
        end_yr = 1991
    else:
        end_yr = 2025
    cursor.execute("""
        SELECT Year FROM Countries WHERE Name LIKE ?
        AND Year BETWEEN ? AND ?
        ORDER BY Year
    """, f'%{country}%', start_yr, end_yr)
    present_years = set(r[0] for r in cursor.fetchall())
    expected_years = set(range(start_yr, end_yr + 1))
    missing = expected_years - present_years
    if missing:
        print(f"  MISSING: {country} absent in years: {sorted(missing)}")
        issues.append(f"Key country {country} missing in {len(missing)} years")
    else:
        print(f"  OK: {country} ({start_yr}-{end_yr}) -- present in all {len(expected_years)} years")

# ============================================================
# 6. FIELD PROGRESSION SMOOTHNESS (ALL YEARS)
# ============================================================
print(f"\n{SEP}")
print("  6. FIELD PROGRESSION CHECK (year-over-year % change)")
print(SEP)
cursor.execute("""
    SELECT c.Year, COUNT(cf.FieldID) as flds
    FROM Countries c
    JOIN CountryFields cf ON c.CountryID = cf.CountryID
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

if anomalies:
    issues.append(f"Field count anomalies: {', '.join(f'{yr}({p:+.0f}%)' for yr, p in anomalies)}")

# ============================================================
# 7. CATEGORY COVERAGE CHECK (ALL YEARS)
# ============================================================
print(f"\n{SEP}")
print("  7. COUNTRIES MISSING KEY CATEGORIES (1990-2025)")
print(SEP)
for yr in range(1990, 2026):
    cursor.execute("SELECT COUNT(DISTINCT CountryID) FROM Countries WHERE Year = ?", yr)
    total = cursor.fetchone()[0]
    if total == 0:
        continue

    # People category name varies by era
    if yr <= 2010:
        people_cat = 'People'
    else:
        people_cat = 'People and Society'

    cursor.execute("""
        SELECT COUNT(DISTINCT c.CountryID)
        FROM Countries c
        JOIN CountryCategories cc ON c.CountryID = cc.CountryID
        WHERE c.Year = ? AND cc.CategoryTitle = ?
    """, yr, people_cat)
    with_people = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT c.CountryID)
        FROM Countries c
        JOIN CountryCategories cc ON c.CountryID = cc.CountryID
        WHERE c.Year = ? AND cc.CategoryTitle = 'Economy'
    """, yr)
    with_econ = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT c.CountryID)
        FROM Countries c
        JOIN CountryCategories cc ON c.CountryID = cc.CountryID
        WHERE c.Year = ? AND cc.CategoryTitle IN ('Government', 'Government and politics')
    """, yr)
    with_gov = cursor.fetchone()[0]

    missing_people = total - with_people
    missing_econ = total - with_econ
    missing_gov = total - with_gov
    flags = []
    if missing_people > 10:
        flags.append(f"{missing_people} missing {people_cat}")
    if missing_econ > 10:
        flags.append(f"{missing_econ} missing Economy")
    if missing_gov > 10:
        flags.append(f"{missing_gov} missing Government")
    if flags:
        print(f"  {yr}: {total} total -- {'; '.join(flags)}")
        issues.append(f"Year {yr}: {'; '.join(flags)}")

# ============================================================
# 8. DATA SOURCE PROVENANCE
# ============================================================
print(f"\n{SEP}")
print("  8. DATA SOURCE PROVENANCE")
print(SEP)
sources = {
    '1990-1999': 'Project Gutenberg Factbook texts, parsed with load_gutenberg_years.py',
    '2000':      'Wayback Machine HTML zip (web.archive.org/web/*/cia.gov/factbook)',
    '2001-2008': 'Wayback Machine HTML zips, parse_table_format (build_archive.py)',
    '2009-2014': 'Wayback Machine HTML zips, parse_collapsiblepanel_format (build_archive.py)',
    '2015-2017': 'Wayback Machine HTML zips, parse_expandcollapse_format (build_archive.py)',
    '2018-2020': 'Wayback Machine HTML zips, parse_modern_format (build_archive.py)',
    '2021-2025': 'factbook/cache.factbook.json GitHub repo (reload_json_years.py)',
}
for years, desc in sources.items():
    print(f"  {years:12s}  {desc}")

# ============================================================
# 9. CHINA POPULATION SPOT CHECK (extended)
# ============================================================
print(f"\n{SEP}")
print("  9. CHINA POPULATION SPOT CHECK")
print(SEP)
for yr in [1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025]:
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
# 10. NULL / EMPTY FIELD CHECK (ALL YEARS)
# ============================================================
print(f"\n{SEP}")
print("  10. DATA QUALITY: NULL/EMPTY FIELDS")
print(SEP)
cursor.execute("""
    SELECT c.Year,
           SUM(CASE WHEN cf.Content IS NULL OR LTRIM(RTRIM(cf.Content)) = '' THEN 1 ELSE 0 END) as empty,
           COUNT(*) as total
    FROM Countries c
    JOIN CountryFields cf ON c.CountryID = cf.CountryID
    GROUP BY c.Year ORDER BY c.Year
""")
for yr, empty, total in cursor.fetchall():
    pct = empty / max(total, 1) * 100
    flag = " <-- high" if pct > 5 else ""
    if empty > 0:
        print(f"  {yr}: {empty:,} empty of {total:,} ({pct:.1f}%){flag}")

# ============================================================
# 11. DUPLICATE COUNTRY CHECK
# ============================================================
print(f"\n{SEP}")
print("  11. DUPLICATE COUNTRY CHECK (same name+year)")
print(SEP)
cursor.execute("""
    SELECT Year, Name, COUNT(*) as cnt
    FROM Countries
    GROUP BY Year, Name
    HAVING COUNT(*) > 1
    ORDER BY Year
""")
dupes = cursor.fetchall()
if dupes:
    print(f"  WARNING: {len(dupes)} duplicate country entries:")
    for yr, name, cnt in dupes:
        print(f"    {yr}: {name} (x{cnt})")
    issues.append(f"Duplicate country entries: {len(dupes)}")
else:
    print(f"  PASS -- No duplicate country entries")

# ============================================================
# SUMMARY
# ============================================================
print(f"\n{SEP}")
print("  CONFIDENCE ASSESSMENT (1990-2025)")
print(SEP)

if not issues:
    print("  HIGH CONFIDENCE -- all checks pass across all 36 years")
else:
    print(f"  {len(issues)} issue(s) found:\n")
    for i, issue in enumerate(issues, 1):
        print(f"  {i:>2}. {issue}")

print(f"\n{SEP}\n")
conn.close()
