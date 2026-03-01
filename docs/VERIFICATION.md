# Data Verification Guide

How to verify the integrity of the CIA World Factbook Archive database. These checks confirm that the SQL Server source and the SQLite distribution match, that row counts are correct, and that known ground-truth values appear where expected.

## Quick Counts

Run these queries against either database to confirm the expected totals:

| Table | Expected Count |
|-------|---------------|
| MasterCountries | 281 |
| Countries | 9,536 |
| CountryCategories | 83,682 |
| CountryFields | 1,071,603 |
| FieldNameMappings | 1,090 |
| FieldValues | 1,610,973 |

### SQLite

```sql
SELECT 'MasterCountries' AS tbl, COUNT(*) AS cnt FROM MasterCountries
UNION ALL SELECT 'Countries', COUNT(*) FROM Countries
UNION ALL SELECT 'CountryCategories', COUNT(*) FROM CountryCategories
UNION ALL SELECT 'CountryFields', COUNT(*) FROM CountryFields
UNION ALL SELECT 'FieldNameMappings', COUNT(*) FROM FieldNameMappings;
```

### SQL Server

```sql
SELECT 'MasterCountries' AS tbl, COUNT(*) AS cnt FROM MasterCountries
UNION ALL SELECT 'Countries', COUNT(*) FROM Countries
UNION ALL SELECT 'CountryCategories', COUNT(*) FROM CountryCategories
UNION ALL SELECT 'CountryFields', COUNT(*) FROM CountryFields
UNION ALL SELECT 'FieldNameMappings', COUNT(*) FROM FieldNameMappings;
```

## Year-by-Year Field Counts

Verify each edition has the expected number of fields:

```sql
SELECT c.Year, COUNT(*) AS FieldCount, COUNT(DISTINCT c.MasterCountryID) AS Countries
FROM CountryFields cf
JOIN Countries c ON cf.CountryID = c.CountryID
GROUP BY c.Year
ORDER BY c.Year;
```

Expected ranges:
- 1990s: 14,000-25,000 fields per year
- 2000s: 25,000-31,000 fields per year
- 2010s: 30,000-37,000 fields per year
- 2020s: 32,000-40,000 fields per year

## Ground-Truth Spot Checks

These values are independently verifiable from public sources.

### United States Population (2025 edition)

```sql
SELECT cf.Content
FROM CountryFields cf
JOIN Countries c ON cf.CountryID = c.CountryID
JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
WHERE mc.ISOAlpha2 = 'US' AND c.Year = 2025 AND fm.CanonicalName = 'Population';
```

Expected: ~341 million (should contain "341,963,408" or similar).

### United States GDP (2025 edition)

```sql
SELECT cf.Content
FROM CountryFields cf
JOIN Countries c ON cf.CountryID = c.CountryID
JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
WHERE mc.ISOAlpha2 = 'US' AND c.Year = 2025
  AND fm.CanonicalName = 'Real GDP (purchasing power parity)';
```

Expected: ~$25 trillion.

### China Population (2025 edition)

```sql
SELECT cf.Content
FROM CountryFields cf
JOIN Countries c ON cf.CountryID = c.CountryID
JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
WHERE mc.ISOAlpha2 = 'CN' AND c.Year = 2025 AND fm.CanonicalName = 'Population';
```

Expected: ~1.4 billion.

## Entity Classification Check

Verify entity type distribution:

```sql
SELECT EntityType, COUNT(*) AS cnt
FROM MasterCountries
GROUP BY EntityType
ORDER BY cnt DESC;
```

Expected:

| Type | Count |
|------|-------|
| sovereign | 192 |
| territory | 65 |
| misc | 7 |
| disputed | 6 |
| crown_dependency | 3 |
| freely_associated | 3 |
| special_admin | 2 |
| dissolved | 2 |
| antarctic | 1 |

## Field Name Mapping Check

Verify canonical field name counts:

```sql
SELECT COUNT(DISTINCT CanonicalName) AS canonical_names
FROM FieldNameMappings
WHERE IsNoise = 0;
```

Expected: 414 canonical names.

```sql
SELECT COUNT(*) AS noise_entries
FROM FieldNameMappings
WHERE IsNoise = 1;
```

Expected: ~281 noise entries.

## FIPS vs ISO Code Verification

The CIA uses FIPS 10-4 codes (stored as `CanonicalCode`) which differ from ISO 3166-1 Alpha-2 codes (`ISOAlpha2`) for 173 out of 281 entities. Verify this:

```sql
SELECT COUNT(*) AS mismatched
FROM MasterCountries
WHERE ISOAlpha2 IS NOT NULL AND CanonicalCode IS NOT NULL
  AND ISOAlpha2 != CanonicalCode;
```

Expected: 173.

### Notable FIPS/ISO Collisions

These country pairs share a two-letter code across the two systems. The web application resolves these by always preferring ISO Alpha-2:

| Code | FIPS Entity | ISO Entity |
|------|------------|------------|
| SG | Senegal | Singapore |
| AU | Austria | Australia |
| BF | Bahamas | Burkina Faso |
| GM | Germany | Gambia |
| NI | Nigeria | Nicaragua |
| BG | Bangladesh | Bulgaria |

```sql
-- Find all FIPS/ISO collisions (where one country's FIPS = another's ISO)
SELECT m1.CanonicalName AS fips_country, m1.CanonicalCode AS shared_code,
       m2.CanonicalName AS iso_country, m2.ISOAlpha2 AS iso_code
FROM MasterCountries m1
JOIN MasterCountries m2 ON m1.CanonicalCode = m2.ISOAlpha2
WHERE m1.MasterCountryID != m2.MasterCountryID
ORDER BY m1.CanonicalCode;
```

## Cross-Database Consistency

If you have both SQL Server and SQLite versions, verify they match:

```python
import pyodbc, sqlite3

# SQL Server
ss = pyodbc.connect('DRIVER={ODBC Driver 18 for SQL Server};'
                     'SERVER=localhost;DATABASE=CIA_WorldFactbook;'
                     'Trusted_Connection=yes;TrustServerCertificate=yes')
ss_count = ss.cursor().execute('SELECT COUNT(*) FROM CountryFields').fetchone()[0]

# SQLite
sl = sqlite3.connect('data/factbook.db')
sl_count = sl.execute('SELECT COUNT(*) FROM CountryFields').fetchone()[0]

assert ss_count == sl_count, f"Mismatch: SQL Server={ss_count}, SQLite={sl_count}"
print(f"Both databases have {ss_count:,} fields")
```

## Known Data Notes

1. **CountryCategories** may have 2 more rows in SQLite than SQL Server due to duplicate category entries for a small number of country-years. This does not affect field data.

2. **"World" and "European Union"** are classified as `EntityType='misc'`. These are excluded from aggregate trend calculations (population sums, etc.) to prevent double counting.

3. **Russia military expenditure** is reported as NA in the CIA Factbook for 1990-2007. Values shown for 2008-2013 repeat a stale 2005 estimate (3.9% of GDP). Fresh data begins in 2014.

4. **1996 edition**: Seven countries (Venezuela, Armenia, Greece, Luxembourg, Malta, Monaco, Tuvalu) were truncated in the Project Gutenberg source. These were repaired using the CIA's original `wfb-96.txt.gz` from the Wayback Machine.

5. **Broadband/telephone fields**: Pre-2020 data uses raw counts (e.g., "17,856,024"). Post-2020 data uses abbreviated forms (e.g., "18.17 million"). The web application's chart parser normalizes both formats to the same scale.

## Running the Full Validation Suite

The ETL repository includes an automated validation script:

```bash
python etl/validate_integrity.py
```

This runs 9 checks: field count benchmarks, US population/GDP ground truth, year-over-year consistency, source provenance, and NULL detection.
