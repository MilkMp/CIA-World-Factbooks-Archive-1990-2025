# CIA World Factbooks Archive 1990-2025

A complete, structured archive of the CIA World Factbook spanning **36 years** (1990-2025), covering **281 entities** with **1,071,213 data fields** in a normalized SQL Server database.

The CIA World Factbook was discontinued on **February 4, 2026**. This archive preserves every edition published during its 36-year run as a structured, queryable dataset.

## Database Statistics

| Metric | Value |
|--------|-------|
| **Years covered** | 1990-2025 (36 editions) |
| **Entities** | 281 (192 sovereign states, 65 territories, 6 disputed, and more) |
| **Country-year records** | 9,500 |
| **Category records** | 83,599 |
| **Data fields** | 1,071,213 |
| **Content size** | ~263 MB |
| **Field name variants** | 1,090 mapped to 414 canonical names |

## Year-by-Year Breakdown

| Year | Source | Countries | Fields |
|------|--------|-----------|--------|
| 1990 | Text | 249 | 15,750 |
| 1991 | Text | 247 | 14,903 |
| 1992 | Text | 264 | 17,372 |
| 1993 | Text | 266 | 18,509 |
| 1994 | Text | 266 | 28,633 |
| 1995 | Text | 266 | 19,599 |
| 1996 | Text | 266 | 20,764 |
| 1997 | Text | 266 | 23,405 |
| 1998 | Text | 266 | 23,524 |
| 1999 | Text | 266 | 25,178 |
| 2000 | HTML | 267 | 25,724 |
| 2001 | Text | 265 | 27,281 |
| 2002 | HTML | 268 | 27,430 |
| 2003 | HTML | 268 | 28,676 |
| 2004 | HTML | 271 | 28,958 |
| 2005 | HTML | 271 | 28,728 |
| 2006 | HTML | 262 | 28,950 |
| 2007 | HTML | 259 | 29,096 |
| 2008 | HTML | 261 | 30,753 |
| 2009 | HTML | 260 | 30,818 |
| 2010 | HTML | 262 | 30,805 |
| 2011 | HTML | 262 | 33,634 |
| 2012 | HTML | 262 | 35,183 |
| 2013 | HTML | 267 | 36,729 |
| 2014 | HTML | 267 | 36,679 |
| 2015 | HTML | 266 | 36,868 |
| 2016 | HTML | 268 | 36,804 |
| 2017 | HTML | 268 | 37,046 |
| 2018 | HTML | 268 | 37,285 |
| 2019 | HTML | 268 | 37,394 |
| 2020 | HTML | 268 | 36,687 |
| 2021 | JSON | 260 | 39,714 |
| 2022 | JSON | 260 | 37,344 |
| 2023 | JSON | 260 | 37,558 |
| 2024 | JSON | 260 | 34,838 |
| 2025 | JSON | 260 | 32,594 |

## Data Sources

| Years | Source | Method |
|-------|--------|--------|
| 1990-1999 | [Project Gutenberg](https://www.gutenberg.org/) | Plain text parsing (4 format variants across the decade) |
| 2000 | [Wayback Machine](https://web.archive.org/) | HTML zip download + classic format parser |
| 2001 | Project Gutenberg | Text fallback (HTML zip was corrupted) |
| 2002-2020 | Wayback Machine | HTML zip archives from cia.gov, 4 parser generations |
| 2021-2025 | [factbook/cache.factbook.json](https://github.com/factbook/cache.factbook.json) | Git history with year-end commit snapshots |

## Repository Structure

```
schema/
  create_tables.sql          # DDL for all 5 tables
data/
  master_countries.sql       # 281 canonical entities
  countries.sql              # 9,500 country-year records
  categories.sql             # 83,599 category records
  field_name_mappings.sql    # 1,090 field name standardization rules
  fields/
    country_fields_1990.sql.gz  # Split by year (36 gzipped files)
    ...
    country_fields_2025.sql.gz
etl/
  build_archive.py           # HTML parser (2000-2020)
  load_gutenberg_years.py    # Text parser (1990-2001)
  reload_json_years.py       # JSON loader (2021-2025)
  build_field_mappings.py    # Field name standardization
  classify_entities.py       # Entity type classification
  validate_integrity.py      # Data quality checks
queries/
  sample_queries.sql         # 18 analytical queries for Power BI / analysis
  search_cli.py              # Command-line search tool
docs/
  DATABASE_SCHEMA.md         # Table definitions and relationships
  ETL_PIPELINE.md            # How the archive was built
  FIELD_EVOLUTION.md         # How CIA field names changed over time
  METHODOLOGY.md             # Complete methodology: parsing, standardization, validation
```

## How to Restore

### Prerequisites
- SQL Server 2017+ (or Azure SQL)
- [ODBC Driver 18 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
- Python 3.8+ with `pyodbc` (for ETL scripts and CLI search tool)

### Steps

1. **Create the database:**
   ```sql
   CREATE DATABASE CIA_WorldFactbook;
   ```

2. **Run the schema script:**
   ```bash
   sqlcmd -S localhost -d CIA_WorldFactbook -i schema/create_tables.sql
   ```

3. **Import data (in order):**
   ```bash
   sqlcmd -S localhost -d CIA_WorldFactbook -i data/master_countries.sql
   sqlcmd -S localhost -d CIA_WorldFactbook -i data/countries.sql
   sqlcmd -S localhost -d CIA_WorldFactbook -i data/categories.sql
   sqlcmd -S localhost -d CIA_WorldFactbook -i data/field_name_mappings.sql
   ```

4. **Import field data (decompress and import each year):**
   ```bash
   cd data/fields
   # On Linux/macOS:
   for f in *.sql.gz; do gunzip -k "$f" && sqlcmd -S localhost -d CIA_WorldFactbook -i "${f%.gz}"; done
   # On Windows (PowerShell):
   Get-ChildItem *.sql.gz | ForEach-Object {
       $sql = $_.FullName -replace '\.gz$',''
       [System.IO.Compression.GZipStream]::new(
           [System.IO.File]::OpenRead($_.FullName),
           [System.IO.Compression.CompressionMode]::Decompress
       ).CopyTo([System.IO.File]::Create($sql))
       sqlcmd -S localhost -d CIA_WorldFactbook -i $sql
   }
   ```

5. **Verify:**
   ```sql
   SELECT COUNT(*) FROM CountryFields;  -- Should return 1,071,213
   ```

## Entity Types

| Type | Count | Description |
|------|-------|-------------|
| sovereign | 192 | Independent states |
| territory | 65 | Dependencies, overseas territories |
| misc | 7 | Oceans, World, EU |
| disputed | 6 | Kosovo, Gaza Strip, West Bank, etc. |
| crown_dependency | 3 | Jersey, Guernsey, Isle of Man |
| freely_associated | 3 | Marshall Islands, Micronesia, Palau |
| special_admin | 2 | Hong Kong, Macau |
| dissolved | 2 | Netherlands Antilles, Serbia and Montenegro |
| antarctic | 1 | Antarctica |

## Field Name Standardization

The CIA renamed many fields over the 36-year span. The `FieldNameMappings` table maps 1,090 raw field name variants to 414 canonical names:

| Mapping Type | Count | Description |
|-------------|-------|-------------|
| identity | 184 | Modern field names (unchanged) |
| rename | 159 | CIA renamed the field (e.g. "GDP - real growth rate" -> "Real GDP growth rate") |
| dash_format | 64 | Formatting differences (single vs double dashes) |
| consolidation | 48 | Sub-fields merged into parents (e.g. Oil production/consumption -> Petroleum) |
| country_specific | 354 | Regional sub-entries, government body names |
| noise | 281 | Parser artifacts, fragments (flagged IsNoise=1) |

## Sample Queries

See [queries/sample_queries.sql](queries/sample_queries.sql) for 18 ready-to-use analytical queries, including:

- Population time series (single country)
- GDP comparison across G7 nations
- Military expenditure trends
- Internet users growth
- Countries that appear/disappear over time
- Consolidated petroleum sub-field view

## License

The CIA World Factbook is a work of the United States Government and is in the **public domain** (17 U.S.C. &sect; 105). This archive is released under [CC0 1.0 Universal (Public Domain Dedication)](LICENSE).

## About

The CIA World Factbook was first published in 1962 as a classified document and made publicly available starting in 1971. The online edition launched in the 1990s and was updated weekly until its discontinuation on February 4, 2026.

This archive was built as a preservation project to ensure this unique longitudinal dataset remains accessible for researchers, analysts, and the public.
