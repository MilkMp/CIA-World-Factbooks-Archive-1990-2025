# Database Schema

The archive is stored in a single SQLite file (`factbook.db`, ~662 MB) with 6 core tables plus a full-text search index.

---

## Entity-Relationship Overview

```
MasterCountries (281)
    |
    +--> Countries (9,536)           one per entity per year
             |
             +--> CountryCategories (83,682)    section headings
             |        |
             |        +--> CountryFields (1,071,601)    the actual data
             |                  |
             |                  +--> FieldValues (1,775,588)    parsed sub-values
             |
             +--> FieldNameMappings (1,132)    field name standardization (lookup)

ISOCountryCodes (250)    reference table, not linked by FK
```

---

## Tables

### MasterCountries
The canonical list of 281 entities that appear across all 36 years.

| Column | Type | Description |
|--------|------|-------------|
| MasterCountryID | INTEGER PK | Unique entity identifier |
| CanonicalCode | TEXT | FIPS 10-4 code (e.g. `US`, `CH` for China) |
| CanonicalName | TEXT | Standardized name (e.g. `United States`) |
| ISOAlpha2 | TEXT | ISO 3166-1 alpha-2 code (nullable) |
| EntityType | TEXT | One of: `sovereign`, `territory`, `disputed`, `misc`, `crown_dependency`, `freely_associated`, `special_admin`, `dissolved`, `antarctic` |
| AdministeringMasterCountryID | INTEGER | Parent entity for territories (self-referencing FK) |

### Countries
One row per entity per year. Links entities to their yearly data.

| Column | Type | Description |
|--------|------|-------------|
| CountryID | INTEGER PK | Unique country-year identifier |
| Year | INTEGER | Edition year (1990-2025) |
| Code | TEXT | Country code as it appeared that year |
| Name | TEXT | Country name as it appeared that year |
| Source | TEXT | Data source (`gutenberg`, `wayback`, `json`, `cia_original`) |
| MasterCountryID | INTEGER | FK to MasterCountries |

### CountryCategories
Section headings that group fields (e.g. "Geography", "People", "Economy").

| Column | Type | Description |
|--------|------|-------------|
| CategoryID | INTEGER PK | Unique category identifier |
| CountryID | INTEGER | FK to Countries |
| CategoryTitle | TEXT | Section name (e.g. `Geography`, `Economy`) |

### CountryFields
The main data table. Each row is one field for one country in one year.

| Column | Type | Description |
|--------|------|-------------|
| FieldID | INTEGER PK | Unique field identifier |
| CategoryID | INTEGER | FK to CountryCategories |
| CountryID | INTEGER | FK to Countries |
| FieldName | TEXT | Field name as published (e.g. `Population`, `GDP - real growth rate`) |
| Content | TEXT | The raw text value, exactly as the CIA published it |

**This table contains ~263 MB of text data** -- the full content of every Factbook field across 36 years.

### FieldValues
Machine-readable sub-values parsed from CountryFields.Content. See [Structured Sub-Values](Structured-Sub-Values) for details.

| Column | Type | Description |
|--------|------|-------------|
| ValueID | INTEGER PK | Unique value identifier |
| FieldID | INTEGER | FK to CountryFields |
| SubField | TEXT | Sub-field label (e.g. `total`, `male`, `female`, `land`, `water`) |
| NumericVal | REAL | Extracted numeric value (nullable) |
| Units | TEXT | Unit of measurement (e.g. `sq km`, `years`, `%`) |
| TextVal | TEXT | Non-numeric text value (nullable) |
| DateEst | TEXT | Estimation date if present (e.g. `2023 est.`) |
| Rank | INTEGER | Global ranking if present |
| SourceFragment | TEXT | Exact text slice the value was parsed from |
| IsComputed | INTEGER | 0 = extracted from source, 1 = derived by parser |

### FieldNameMappings
Maps raw field names to standardized canonical names. See [Field Name Mappings](Field-Name-Mappings) for details.

| Column | Type | Description |
|--------|------|-------------|
| MappingID | INTEGER PK | Unique mapping identifier |
| OriginalName | TEXT | Field name as it appeared in the source |
| CanonicalName | TEXT | Standardized name |
| MappingType | TEXT | Rule that produced this mapping (e.g. `identity`, `known_rename`, `consolidation`, `noise`) |
| ConsolidatedTo | TEXT | Parent canonical name if consolidated |
| IsNoise | INTEGER | 1 = parser artifact / not real data |
| FirstYear | INTEGER | First year this variant appeared |
| LastYear | INTEGER | Last year this variant appeared |
| UseCount | INTEGER | How many CountryFields rows use this name |
| Notes | TEXT | Mapping rationale |

### ISOCountryCodes
Reference table with ISO 3166-1 codes for 250 countries.

| Column | Type | Description |
|--------|------|-------------|
| ISOAlpha2 | TEXT | Two-letter code |
| ISOAlpha3 | TEXT | Three-letter code |
| ISONumeric | TEXT | Numeric code |
| Name | TEXT | Short name |
| OfficialName | TEXT | Full official name |

---

## Full-Text Search

The database includes an FTS5 virtual table (`CountryFieldsFTS`) indexed on `CountryFields.Content`. This enables fast full-text search across all 1M+ fields:

```sql
SELECT cf.FieldID, cf.FieldName, cf.Content
FROM CountryFieldsFTS fts
JOIN CountryFields cf ON fts.rowid = cf.FieldID
WHERE CountryFieldsFTS MATCH 'nuclear weapons'
LIMIT 20;
```

---

## Indexes

The database ships with indexes on all foreign keys and common query patterns:

| Index | Table | Column(s) |
|-------|-------|-----------|
| IX_Countries_Year | Countries | Year |
| IX_Countries_Code | Countries | Code |
| IX_Countries_MasterCountryID | Countries | MasterCountryID |
| IX_Categories_Country | CountryCategories | CountryID |
| IX_Fields_Category | CountryFields | CategoryID |
| IX_Fields_Country | CountryFields | CountryID |
| IX_Fields_FieldName | CountryFields | FieldName |
| IX_FieldNameMappings_CanonicalName | FieldNameMappings | CanonicalName |
| IX_FV_FieldID | FieldValues | FieldID |
| IX_FV_SubField | FieldValues | SubField |
| IX_FV_Numeric | FieldValues | NumericVal (WHERE NOT NULL) |
