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

### 1996 Data Repair: CIA Original Text

The Gutenberg edition for 1996 (ebook #27675) is truncated for 7 sovereign countries (Venezuela, Armenia, Greece, Luxembourg, Malta, Monaco, Tuvalu). Their entries end mid-sentence in the source file.

The CIA's own complete text file (`wfb-96.txt.gz`) was recovered from the Wayback Machine at `odci.gov/cia/publications/nsolo/` (captured May 1997). This 3.8 MB file uses a different format from the Gutenberg version: page headers (`FACTBOOK COUNTRY REPORT Page NNN`), centered country/section names, and 5-space indented fields with 10-space indented values.

The repair script (`etl/repair_1996_truncated.py`) parses the CIA original and replaces the 7 truncated entries in the database. The CIA original is stored at `samples/text_samples/1996_cia_original.txt`.

**Note**: 1996 is the only year where the CIA published a downloadable text file. For 1990-1995 and 1997-1999, no CIA-original download archives exist -- Project Gutenberg is the only bulk text source. Validation confirmed those years have no truncation issues.

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

After all data is loaded, this script analyzes the 1,090 distinct field names across all years and maps them to 414 canonical names. The mapping uses a **priority-ordered rule system** — the first rule that matches wins.

#### Rule Priority (applied in order)

| Priority | Rule | Description |
|----------|------|-------------|
| 1 | **Identity** | If the field name exists in 2024/2025 data and isn't in `KNOWN_RENAMES`, keep it as-is |
| 2 | **Dash normalization** | Fix formatting: `Economy-overview` or `Economy--overview` → `Economy - overview` |
| 3 | **Known CIA renames** (`KNOWN_RENAMES` dict) | 159 manually curated old→new mappings based on CIA's own rename history |
| 4 | **Consolidation** (`CONSOLIDATION_MAP` dict) | 48 sub-fields that should roll up to a parent (e.g. oil sub-fields → Petroleum) |
| 5 | **Government body detection** | Country-specific legislative body names (containing "Assembly", "Senate", "Parliament", etc.) → `Legislative branch` |
| 6 | **Regional sub-entries** (`REGIONAL_ENTRIES` set) | Cyprus Turkish/Greek area splits, Serbia/Montenegro splits, etc. — kept as-is but flagged |
| 7 | **Noise detection** (`is_noise()` function) | Parser artifacts, fragments, sub-field labels — flagged `IsNoise=1` |
| 8 | **Manual fallback** | Anything unmatched is kept as-is and flagged `manual` for review |

#### The `KNOWN_RENAMES` Dictionary

This is the core mapping of 159 CIA field name changes across the 36-year span. It was built by:
1. Comparing the field names in 2024/2025 (the "modern" set) against earlier years
2. Identifying fields that disappeared and matching them to their modern equivalents
3. Consulting CIA Factbook documentation notes about field restructuring

Examples from the dictionary:

```python
KNOWN_RENAMES = {
    # Pre-standard era (1990s) → modern names
    "National product":                     "Real GDP (purchasing power parity)",
    "National product per capita":          "Real GDP per capita",
    "Defense expenditures":                 "Military expenditures",
    "Ethnic divisions":                     "Ethnic groups",
    "Comparative area":                     "Area - comparative",
    "Telecommunications":                   "Telecommunication systems",

    # Modern-era renames (CIA renamed for clarity)
    "Economy - overview":                   "Economic overview",
    "GDP (purchasing power parity)":        "Real GDP (purchasing power parity)",
    "GDP - real growth rate":               "Real GDP growth rate",
    "Military branches":                    "Military and security forces",
    "Elevation extremes":                   "Elevation",
    "Telephone system":                     "Telecommunication systems",

    # Broadcast media consolidation
    "Radio broadcast stations":             "Broadcast media",
    "Television broadcast stations":        "Broadcast media",
    ...  # 159 entries total
}
```

#### The `CONSOLIDATION_MAP` Dictionary

48 sub-fields that should be grouped under a parent field for analysis. The sub-field data is preserved as-is in the database, but the `ConsolidatedTo` column in `FieldNameMappings` indicates the parent:

```python
CONSOLIDATION_MAP = {
    # Oil/Petroleum (12 sub-fields → "Petroleum")
    "Oil - production":                     "Petroleum",
    "Crude oil - production":               "Petroleum",
    "Refined petroleum products - exports": "Petroleum",

    # Natural gas (5 sub-fields → "Natural gas")
    "Natural gas - production":             "Natural gas",
    "Natural gas - consumption":            "Natural gas",

    # Electricity (5 sub-fields → "Electricity")
    "Electricity - production":             "Electricity",
    "Electricity - consumption":            "Electricity",

    # Military personnel (7 sub-fields)
    "Military manpower - availability":     "Military and security service personnel strengths",
    "Manpower fit for military service":    "Military and security service personnel strengths",

    # Maritime claims (6 sub-fields)
    "Contiguous zone":                      "Maritime claims",
    "Continental shelf":                    "Maritime claims",
    "Exclusive economic zone":              "Maritime claims",
    ...  # 48 entries total
}
```

#### Noise Detection (`is_noise()` function)

The `is_noise()` function uses multiple heuristics to identify parser artifacts:

- **Single/two-letter entries** — fragments like "A", "US" (as field names, not country data)
- **Lowercase-starting entries** — almost always sub-field fragments from 1990s parsing
- **Entries with known noise phrases** — "consists mainly of", "includes the following", etc.
- **Very long entries (>80 chars)** with low use count — descriptive text accidentally captured as field names
- **Sub-field labels from 1994** — "adjective", "cabinet", "chancery" etc. appeared as standalone fields due to the HTML structure that year
- **Abbreviation entries** — short entries ending in `.` (glossary artifacts)
- **Political party names** — country-specific party/faction names from 1990s data that were parsed as field names

Additionally, a `SUB_FIELD_LABELS` set (34 known sub-field fragments) and `REGIONAL_ENTRIES` set (80+ regional sub-entries like "Turkish Area", "Serbia", "Sabah") provide explicit pattern matching.

### Entity Classification (`classify_entities.py`)

Classifies each of the 281 `MasterCountry` entries into one of 9 entity types.

#### Classification Logic

1. **Check `OVERRIDES` dictionary first** — 40+ manually classified entries for edge cases:

```python
OVERRIDES = {
    # Oceans and non-countries
    "XQ": "misc",      # Arctic Ocean
    "XX": "misc",      # World
    "EE": "misc",      # European Union

    # Disputed territories
    "KV": "disputed",  # Kosovo
    "GZ": "disputed",  # Gaza Strip
    "WE": "disputed",  # West Bank

    # Special Administrative Regions
    "HK": "special_admin",  # Hong Kong
    "MC": "special_admin",  # Macau

    # Crown dependencies
    "GK": "crown_dependency",  # Guernsey
    "JE": "crown_dependency",  # Jersey

    # Dissolved entities
    "NT": "dissolved",  # Netherlands Antilles
    "YI": "dissolved",  # Serbia and Montenegro
    ...
}
```

2. **Check "Dependency status" field** — If the most recent year's data contains a dependency status with keywords like "territory", "dependency", "overseas", "self-governing", classify as `territory`

3. **Check "Government type" field** — If it contains sovereign-state keywords like "republic", "monarchy", "parliamentary", "presidential", classify as `sovereign`

4. **Fallback** — If government type exists but doesn't match known patterns, default to `sovereign`

#### Entity Type Results

| Type | Count | How Determined |
|------|-------|----------------|
| sovereign | 192 | Government type contains republic/monarchy/parliamentary/etc. |
| territory | 65 | Has dependency status field, or manual override |
| misc | 7 | Manual override (oceans, World, EU) |
| disputed | 6 | Manual override (Kosovo, Gaza, West Bank, etc.) |
| crown_dependency | 3 | Manual override (Jersey, Guernsey, Isle of Man) |
| freely_associated | 3 | Manual override (Marshall Islands, Micronesia, Palau) |
| special_admin | 2 | Manual override (Hong Kong, Macau) |
| dissolved | 2 | Manual override (Netherlands Antilles, Serbia and Montenegro) |
| antarctic | 1 | Manual override (Antarctica) |

### Validation (`validate_integrity.py`)

Runs 9 automated checks against known ground truth:

| Check | Method | Pass Criteria |
|-------|--------|---------------|
| 1. Structural overview | Count countries/categories/fields per year | All years present with reasonable counts |
| 2. US population benchmark | Compare extracted population against known Census values | Within 10M for each year 2000-2025 |
| 3. US GDP benchmark | Spot-check GDP field content | Contains plausible dollar amounts |
| 4. Country count deltas | Year-over-year country count changes | No changes >10 countries (flags mergers/splits) |
| 5. Source provenance | Verify source column matches expected pipeline | text/html/json assigned correctly |
| 6. Field progression | Year-over-year field count % change | No anomalies >15% change |
| 7. Category coverage | Check key categories (People, Economy) exist | <10 countries missing per year |
| 8. China population | Spot-check China's population data | Plausible values across sampled years |
| 9. Null/empty fields | Count NULL or empty Content values | <5% empty per year |
