# Database Schema

## Overview

The CIA World Factbook Archive uses a normalized relational schema with 5 tables. The design prioritizes faithful preservation of the original data while enabling cross-year analysis through the `MasterCountries` and `FieldNameMappings` lookup tables.

## Entity-Relationship Diagram

```
MasterCountries (281 rows)
  |
  |-- 1:N --> Countries (9,500 rows)
  |             |
  |             |-- 1:N --> CountryCategories (83,599 rows)
  |             |             |
  |             |             |-- 1:N --> CountryFields (1,061,341 rows)
  |             |
  |             |-- 1:N --> CountryFields (via CountryID)
  |
  |-- self-ref (AdministeringMasterCountryID)

FieldNameMappings (1,090 rows) -- standalone lookup, joins on FieldName
```

## Tables

### 1. MasterCountries

One row per canonical entity across all years. Provides stable identity for cross-year queries.

| Column | Type | Description |
|--------|------|-------------|
| MasterCountryID | INT IDENTITY | Primary key |
| CanonicalCode | NVARCHAR(10) | FIPS 10-4 code (e.g. "US", "CH") |
| CanonicalName | NVARCHAR(200) | Canonical name (e.g. "United States") |
| CreatedDate | DATETIME | Row creation timestamp |
| ISOAlpha2 | NVARCHAR(2) | ISO 3166-1 alpha-2 code (e.g. "US", "CN") |
| EntityType | NVARCHAR(20) | Classification: sovereign, territory, disputed, etc. |
| AdministeringMasterCountryID | INT | FK to self: which sovereign administers this territory |

**Indexes:** Unique on CanonicalCode.

### 2. Countries

One row per entity per year. Links to MasterCountries for cross-year identity.

| Column | Type | Description |
|--------|------|-------------|
| CountryID | INT IDENTITY | Primary key |
| Year | INT | Factbook edition year (1990-2025) |
| Code | NVARCHAR(10) | FIPS code as it appeared in that year's data |
| Name | NVARCHAR(200) | Country name as it appeared in that year |
| Source | NVARCHAR(50) | Data source: "text", "html", or "json" |
| MasterCountryID | INT | FK to MasterCountries |

**Indexes:** Year, Code.

### 3. CountryCategories

Section headings within each country-year (e.g. "Geography", "Economy", "People and Society").

| Column | Type | Description |
|--------|------|-------------|
| CategoryID | INT IDENTITY | Primary key |
| CountryID | INT | FK to Countries |
| CategoryTitle | NVARCHAR(200) | Section heading |

**Indexes:** CountryID.

### 4. CountryFields

Individual data fields. This is the main data table (~1M rows, ~263 MB of content).

| Column | Type | Description |
|--------|------|-------------|
| FieldID | INT IDENTITY | Primary key |
| CategoryID | INT | FK to CountryCategories |
| CountryID | INT | FK to Countries |
| FieldName | NVARCHAR(200) | Field name as it appeared in source data |
| Content | NVARCHAR(MAX) | The actual data value (text) |

**Indexes:** CategoryID, CountryID.

### 5. FieldNameMappings

Maps the 1,090 distinct field name variants to 414 canonical names. Join on `CountryFields.FieldName = FieldNameMappings.OriginalName`.

| Column | Type | Description |
|--------|------|-------------|
| MappingID | INT IDENTITY | Primary key |
| OriginalName | NVARCHAR(200) | Raw field name as found in CountryFields |
| CanonicalName | NVARCHAR(200) | Standardized field name |
| MappingType | NVARCHAR(30) | How it was classified: identity, rename, dash_format, consolidation, country_specific, noise |
| ConsolidatedTo | NVARCHAR(200) | Parent field for sub-field consolidation (e.g. "Petroleum" for oil sub-fields) |
| IsNoise | BIT | 1 = parser artifact/fragment, should be excluded from analysis |
| FirstYear | INT | Earliest year this field name appears |
| LastYear | INT | Latest year this field name appears |
| UseCount | INT | Total occurrences across all country-years |
| Notes | NVARCHAR(500) | Optional notes about the mapping |

**Indexes:** CanonicalName, Unique on OriginalName.

## Key Relationships

- Every `Countries` row should link to a `MasterCountries` row via `MasterCountryID` (some historical entities may be NULL)
- Every `CountryCategories` row belongs to exactly one `Countries` row
- Every `CountryFields` row belongs to both a `CountryCategories` row and a `Countries` row
- `FieldNameMappings` is a standalone lookup table joined by field name string matching

## Cross-Year Querying Pattern

To query a field across years with consistent naming:

```sql
SELECT c.Year, mc.CanonicalName AS Country, cf.Content
FROM CountryFields cf
JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
JOIN Countries c ON cf.CountryID = c.CountryID
JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
WHERE fm.CanonicalName = 'Population'
  AND mc.CanonicalName = 'United States'
  AND fm.IsNoise = 0
ORDER BY c.Year;
```
