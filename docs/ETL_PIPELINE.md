# ETL Pipeline

How the 36-year CIA World Factbook archive was built from three distinct source formats.

## Overview

The CIA changed their publication format multiple times over 36 years, requiring three separate ETL pipelines:

| Era | Years | Source | Parser | Script |
|-----|-------|--------|--------|--------|
| Text | 1990-1999, 2001 | Project Gutenberg | 6 text format variants | `load_gutenberg_years.py` |
| HTML | 2000, 2002-2020 | Wayback Machine | 5 HTML parser generations | `build_archive.py` |
| JSON | 2021-2025 | GitHub (factbook/cache.factbook.json) | Direct JSON parsing | `reload_json_years.py` |

## Pipeline 1: Project Gutenberg Text (1990-1999, 2001)

### Source
The CIA World Factbook was published as plain text via Project Gutenberg throughout the 1990s. Each year has a different ebook ID.

### Format Variants
The text format changed frequently:

| Years | Format | Country Marker | Section Marker | Field Format |
|-------|--------|---------------|----------------|--------------|
| 1990 | old | `Country:  Name` | `- Section` | `Field: value` |
| 1991 | tagged | `_@_Name` | `_*_Section` | `_#_Field: value` |
| 1992 | colon | `:Name Section` | (embedded) | Indented values |
| 1993-1994 | asterisk | `*Name, Section` | (embedded) | Indented values |
| 1995-1999 | atsign/atsign_bare | `@Name:Section` or `@Name` + bare headers | Inline/indented mix | Mixed |
| 2001 | equals | `@Name` | `Name    Section` (tab-separated) | Inline fields |

### Process
1. Download text file from Project Gutenberg
2. Strip PG header/footer wrapper
3. Parse with year-specific parser
4. Match country names to `MasterCountries` using fuzzy matching
5. Insert into database

### Why 2001 uses text
The 2001 HTML zip from the Wayback Machine was corrupted. The Project Gutenberg text edition serves as a reliable fallback.

## Pipeline 2: Wayback Machine HTML (2000, 2002-2020)

### Source
CIA published downloadable zip archives of the World Factbook at `cia.gov/the-world-factbook/about/archives/download/factbook-YYYY.zip`. These are preserved in the Wayback Machine.

### HTML Format Generations

| Years | Format | Key Markers |
|-------|--------|-------------|
| 2000 | Classic | `<b>FieldName:</b>` with `<a name="Geo">` section anchors |
| 2001-2008 | Table | `<td class="FieldLabel">` with `<a name="...">` sections |
| 2009-2014 | CollapsiblePanel | `<div class="CollapsiblePanel">` with `<span class="category">` |
| 2015-2017 | ExpandCollapse | `<h2 class="question" sectiontitle="...">` with field divs |
| 2018-2020 | Modern | `<li id="...-category-section-anchor">` with `<div id="field-...">` |

### Process
1. Download zip from Wayback Machine (using known-good timestamps)
2. If known timestamp fails, CDX API lookup for alternative
3. Extract HTML files from `geos/` directory within zip
4. Parse with year-appropriate parser (auto-selected)
5. Extract country name from `<title>` tag (format varies by year)
6. Insert categories and fields into database
7. Delete zip to save space

### Wayback Machine Timestamps
Each year has a verified Wayback Machine timestamp that returns a valid zip. These were discovered through manual testing and CDX API searches.

## Pipeline 3: GitHub JSON (2021-2025)

### Source
The [factbook/cache.factbook.json](https://github.com/factbook/cache.factbook.json) repository was auto-updated weekly (every Thursday) from August 2021 until the Factbook's discontinuation.

### Year-Specific Snapshots
Rather than loading the same JSON snapshot for all years, we use git history to find the last commit before each year-end:

| Year | Cutoff Date | Description |
|------|-------------|-------------|
| 2021 | 2022-01-01 | Last commit of 2021 |
| 2022 | 2023-01-01 | Last commit of 2022 |
| 2023 | 2024-01-01 | Last commit of 2023 |
| 2024 | 2025-01-01 | Last commit of 2024 |
| 2025 | 2026-02-04 | Final commit (CIA discontinued the Factbook) |

### Process
1. Clone or fetch the `factbook/cache.factbook.json` repository
2. For each year, find the last git commit before the cutoff date
3. Check out that commit
4. Parse all `{region}/{code}.json` files
5. Extract `name`, `code`, `categories[].title`, `categories[].fields[].name`, `categories[].fields[].content`
6. Strip HTML tags from content
7. Snapshot existing MasterCountryID links, delete old year data, insert new
8. Restore repo to master branch

## Post-ETL Processing

### Field Name Standardization (`build_field_mappings.py`)
After all data is loaded, this script analyzes the 1,090 distinct field names across all years and maps them to 414 canonical names using:
1. **Identity** — field exists in 2024/2025 data unchanged
2. **Dash normalization** — `Economy-overview` -> `Economy - overview`
3. **Known CIA renames** — `GDP - real growth rate` -> `Real GDP growth rate`
4. **Consolidation** — Oil sub-fields merged to `Petroleum` parent
5. **Government body detection** — Country-specific legislative body names -> `Legislative branch`
6. **Noise filtering** — Parser artifacts, fragments, sub-field labels

### Entity Classification (`classify_entities.py`)
Classifies each `MasterCountry` as sovereign, territory, disputed, etc. by examining the "Dependency status" and "Government type" fields from the most recent year's data, with manual overrides for edge cases.

### Validation (`validate_integrity.py`)
Runs 9 checks:
1. Structural overview (countries/categories/fields per year)
2. US population benchmark (known ground truth)
3. US GDP benchmark
4. Country count year-over-year deltas
5. Data source provenance
6. Field count progression smoothness
7. Category coverage check
8. China population spot check
9. Null/empty field audit
