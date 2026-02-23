# Methodology

Complete documentation of how the CIA World Factbook Archive was built, validated, and standardized — from raw source collection through final verification.

> **Data Integrity:** No Factbook content is added or altered. The parsing process structures the CIA's raw text into queryable fields — removing formatting artifacts, sectioning headers, and deduplicating noise lines — but the actual data values are exactly as the CIA published them. Original field names are preserved in the database; canonical name mappings live in a separate `FieldNameMappings` lookup table. The only additions to the source data are reference lookup tables (FIPS-to-ISO code mappings, entity classifications, COCOM regional assignments) that sit alongside the original data, not inside it.

## Table of Contents

1. [Source Collection](#1-source-collection)
2. [Parsing Strategy](#2-parsing-strategy)
3. [Database Design](#3-database-design)
4. [Entity Resolution](#4-entity-resolution)
5. [Field Name Standardization](#5-field-name-standardization)
6. [Entity Type Classification](#6-entity-type-classification)
7. [Validation & Quality Assurance](#7-validation--quality-assurance)
8. [Known Limitations](#8-known-limitations)

---

## 1. Source Collection

### The Challenge

The CIA World Factbook was published in three fundamentally different formats over its 36-year online run. No single source covers all years, so three separate collection strategies were needed.

### 1a. Project Gutenberg (1990-1999, 2001)

**What**: Plain text editions of the CIA Factbook uploaded to Project Gutenberg as public domain ebooks.

**How**: Each year has a specific Project Gutenberg ebook number, hardcoded in the `PG_EBOOKS` dictionary:

```python
PG_EBOOKS = {
    1990: 14,    # https://www.gutenberg.org/cache/epub/14/pg14.txt
    1991: 25,
    1992: 48,
    1993: 87,
    1994: 180,
    1995: 571,
    1996: 27675,
    1997: 1662,
    1998: 2016,
    1999: 27676,
    2001: 27638,  # Fallback — HTML zip for 2001 was corrupted
}
```

The script downloads each text file, strips the Project Gutenberg header/footer (everything before `*** START OF` and after `*** END OF`), then parses the remaining text.

**Why 2001 uses text**: The 2001 HTML zip archived in the Wayback Machine was found to be corrupted (invalid zip file). The Project Gutenberg text edition serves as a reliable alternative.

### 1b. Wayback Machine HTML Archives (2000, 2002-2020)

**What**: The CIA published downloadable zip files at `cia.gov/the-world-factbook/about/archives/download/factbook-YYYY.zip`. These were captured by the Internet Archive's Wayback Machine.

**How**: Each year has a verified Wayback Machine timestamp in the `WAYBACK_TIMESTAMPS` dictionary:

```python
WAYBACK_TIMESTAMPS = {
    2000: "20210115043153",
    2001: "20210115043222",
    2002: "20210115043238",
    ...
    2020: "20210115044405",
}
```

The download URL pattern is:
```
https://web.archive.org/web/{timestamp}id_/https://www.cia.gov/the-world-factbook/about/archives/download/factbook-{year}.zip
```

If the known timestamp fails (corrupted download), the script falls back to the CDX API (`web.archive.org/cdx/search/cdx`) to find alternative timestamps, then tries without the `id_` modifier as a last resort.

Each zip contains a `geos/` directory with individual HTML files per country (e.g., `geos/us.html`). Country codes are 2-3 characters. Files with codes longer than 5 characters or containing patterns like "template", "print", "summary" are filtered out.

### 1c. GitHub JSON Repository (2021-2025)

**What**: The [factbook/cache.factbook.json](https://github.com/factbook/cache.factbook.json) GitHub repository maintained a machine-readable JSON version of the Factbook, auto-updated weekly every Thursday.

**How**: Rather than using a single snapshot for all 5 years (which would give identical data), we use git history to check out the **last commit before each year-end**:

```python
YEAR_CUTOFFS = {
    2021: "2022-01-01",
    2022: "2023-01-01",
    2023: "2024-01-01",
    2024: "2025-01-01",
    2025: "2026-02-04",  # CIA discontinued Factbook on Feb 4, 2026
}
```

For each year, the script runs:
```bash
git log --before {cutoff} --format="%H %ai" -1
```
to find the exact commit hash, then checks out that commit and reads all JSON files from 13 region directories (africa, antarctica, australia-oceania, central-america-n-caribbean, central-asia, east-n-southeast-asia, europe, middle-east, north-america, oceans, south-america, south-asia, world).

Each JSON file has the structure:
```json
{
  "name": "Afghanistan",
  "code": "AF",
  "categories": [
    {
      "title": "Geography",
      "fields": [
        { "name": "Location", "content": "<p>Southern Asia...</p>" }
      ]
    }
  ]
}
```

HTML tags are stripped from `content` values using regex (`<[^>]+>` and `&[a-zA-Z]+;`).

---

## 2. Parsing Strategy

### The Problem

The CIA changed their HTML/text format at least 10 times across the 36-year span. Each format requires a different parser.

### Text Parsers (1990-1999, 2001)

Six distinct text formats were identified by examining the raw text files:

| Format | Years | Country Detection | Section Detection | Field Detection |
|--------|-------|-------------------|-------------------|-----------------|
| `old` | 1990 | `Country:  Name` (double space) | `- SectionName` at line start | `FieldName: value` at line start |
| `tagged` | 1991 | `_@_Name` marker | `_*_SectionName` marker | `_#_FieldName: value` marker |
| `colon` | 1992 | `:Name SectionName` | Embedded in country marker | Indented `FieldName:` then value on next line |
| `asterisk` | 1993-1994 | `*Name, SectionName` or `@Name, SectionName` | Known category names after comma | Unindented `FieldName:` with indented values below |
| `atsign` / `atsign_bare` | 1995-1999 | `@Name:SectionName` or `@Name` alone | After colon, or bare section name on own line | Mix of inline `Field: value` and indented sub-fields |
| `equals` | 2001 | `@Name` on own line | `CountryName    SectionName` (4+ spaces) | `FieldName: value` inline |

The `YEAR_FORMATS` dictionary maps each year to its format:

```python
YEAR_FORMATS = {
    1990: 'old',
    1991: 'tagged',
    1992: 'colon',
    1993: 'asterisk',
    1994: 'asterisk',
    1995: 'atsign',
    1996: 'atsign_bare',
    1997: 'atsign',
    1998: 'atsign',
    1999: 'atsign_bare',
    2001: 'equals',
}
```

**Key parsing challenge**: Countries with commas in their names (e.g., "Korea, North") must not be split at the comma. The asterisk parser solves this by only splitting on known category names:

```python
KNOWN_CATEGORIES = {
    'Geography', 'People', 'Government', 'Economy', 'Communications',
    'Defense Forces', 'Transportation', 'Military', 'Transnational Issues',
    'Introduction', 'People and Society', 'Energy', 'Environment',
}
```

### HTML Parsers (2000-2020)

Five HTML format generations, each with different DOM structures:

| Parser | Years | How Sections Are Found | How Fields Are Found |
|--------|-------|----------------------|---------------------|
| `parse_classic` | 2000 | `<a name="Geo">` anchor tags | `<b>FieldName:</b>` bold tags with regex |
| `parse_table_format` | 2001-2008 | `<a name="...">` anchors filtered by `section_map` | `<td class="FieldLabel">` elements with sibling `<td>` content |
| `parse_collapsiblepanel_format` | 2009-2014 | `<div class="CollapsiblePanel">` with `<span class="category">` | `<tr class="na_light">` rows with `<div class="category">` / `<div class="category_data">` |
| `parse_expandcollapse_format` | 2015-2017 | `<h2 class="question" sectiontitle="Geography">` | `<div id="field" class="category">` with `<a>` link for field name |
| `parse_modern_format` | 2018-2020 | `<li id="geography-category-section-anchor">` | `<div id="field-location">` with `<div class="category_data subfield text">` |

The `YEAR_PARSERS` dictionary auto-selects the correct parser:

```python
YEAR_PARSERS = {
    2000: 'classic',
    2001: 'table',  2002: 'table', ..., 2008: 'table',
    2009: 'collapsiblepanel', ..., 2014: 'collapsiblepanel',
    2015: 'expandcollapse', ..., 2017: 'expandcollapse',
    2018: 'modern', ..., 2020: 'modern',
}
```

**Country name extraction** is its own challenge — the `<title>` tag format changed across years:
- 2000-2005: `"CIA -- The World Factbook 2000 -- Aruba"`
- 2006-2012: `"CIA - The World Factbook"` (no country name!)
- 2013-2015: `"The World Factbook"`
- 2016-2017: `"The World Factbook — Central Intelligence Agency"`
- 2018-2020: `"North America :: United States — The World Factbook - CIA"`

The `get_country_name()` function tries 4 fallback strategies: title tag parsing, `<span class="countryName">`, breadcrumb `::` splitting, and `<h2 sectiontitle>` attributes.

**ALL-CAPS normalization**: Early years sometimes had country names in ALL CAPS (e.g., "UNITED STATES"). The `_normalize_country_case()` function title-cases these.

### Every Parser Has a Fallback

If structured parsing yields zero categories, every parser falls back to extracting the full page text:
```python
if not categories:
    full_text = soup.get_text(separator='\n')
    categories.append(('Full Content', [('Text', full_text[:100000])]))
```

This ensures no data is silently lost — worst case, we get one big text blob per country.

---

## 3. Database Design

### Schema Rationale

The schema was designed to:
1. **Preserve original data exactly** — field names are stored as-is from each year's source, never modified
2. **Enable cross-year queries** — `MasterCountries` provides stable identity across years where codes/names change
3. **Support field name evolution** — `FieldNameMappings` is a separate lookup table, so original data stays untouched
4. **Track provenance** — the `Source` column on `Countries` records whether data came from text, html, or json

### Why Not Normalize Content?

The `Content` column stores raw text exactly as parsed. We deliberately did NOT:
- Extract numeric values (populations are stored as "331,449,281" not as integers)
- Split compound fields (e.g., "total: 647,500 sq km | land: 652,230 sq km")
- Parse dates or units

This preserves the original data and avoids lossy transformations. Downstream analysis can parse values as needed.

---

## 4. Entity Resolution

### The Problem

The same country might appear with different codes and names across years:
- Code changes: CIA uses FIPS 10-4 codes, which occasionally change
- Name changes: "Burma" → "Myanmar", "Czech Republic" → "Czechia", "Swaziland" → "Eswatini"
- Entity splits: "Serbia and Montenegro" → "Serbia" + "Montenegro"

### Solution: MasterCountries Table

The `MasterCountries` table provides 281 canonical entities. Each `Countries` row (per-year) links to its `MasterCountryID` via foreign key.

For **text-era data** (1990s), country names must be fuzzy-matched since there are no standard codes. The `find_master_match()` function tries:
1. Exact name match (case-insensitive)
2. Without "The" prefix
3. Substring containment (handles partial matches)

A hardcoded `aliases` dictionary handles known historical name variants:
```python
aliases = {
    'burma': 'myanmar',
    'ivory coast': "cote d'ivoire",
    'zaire': 'congo, democratic republic of the',
    'czech republic': 'czechia',
    'swaziland': 'eswatini',
    'the bahamas': 'bahamas, the',
    ...
}
```

For **HTML/JSON data**, FIPS codes from filenames are matched directly to `CanonicalCode`.

### MasterCountryID Preservation

When reloading a year's data (e.g., fixing a parser bug), the script snapshots existing `Code → MasterCountryID` mappings before deletion, then restores them after reinsertion. This prevents orphaning.

---

## 5. Field Name Standardization

### The Problem

The CIA renamed fields frequently. "GDP" alone has had 6 different field names across 36 years. Without standardization, cross-year analysis requires knowing every historical variant.

### Solution: `FieldNameMappings` Table

A separate lookup table (1,090 rows) maps every distinct `FieldName` found in `CountryFields` to a canonical name. The original data is never modified.

### Rule System

Rules are applied in strict priority order. **First match wins.** This is implemented in `apply_rules()`:

#### Rule 1: Identity
If the field name exists in the 2024 or 2025 data and is NOT in `KNOWN_RENAMES`, it's already canonical.
```python
if original in modern_names and original not in KNOWN_RENAMES:
    return (original, original, "identity", ...)
```

#### Rule 2: Dash Normalization
Fixes formatting inconsistencies from the 1998-1999 editions:
- `Economy-overview` → `Economy - overview`
- `GDP--real growth rate` → `GDP - real growth rate`

The regex `^(.+?)(?:--|(?<! )-)(.+)$` matches single or double dashes that aren't preceded by a space.

#### Rule 3: Known CIA Renames (`KNOWN_RENAMES`)
159 manually curated entries mapping historical field names to their modern equivalents. Each mapping was verified by:
1. Confirming the old name no longer exists in recent years
2. Confirming the new name covers the same data concept
3. Checking CIA documentation/changelog notes where available

Categories of renames:
- **Pre-standard era** (1990s): `"National product"` → `"Real GDP (purchasing power parity)"`
- **Modern renames**: `"Economy - overview"` → `"Economic overview"`
- **Metric renames**: `"Maternal mortality rate"` → `"Maternal mortality ratio"`
- **Scope changes**: `"Military branches"` → `"Military and security forces"`
- **Format standardization**: `"Currency"`, `"Currency code"`, `"Currency (code)"` → `"Exchange rates"`

#### Rule 4: Consolidation (`CONSOLIDATION_MAP`)
48 sub-fields that are logically part of a parent aggregate:
- **Petroleum** (12 sub-fields): Oil production, consumption, exports, imports, proved reserves + Crude oil variants + Refined petroleum variants
- **Natural gas** (5 sub-fields): Production, consumption, exports, imports, proved reserves
- **Electricity** (5 sub-fields): Production, consumption, exports, imports, installed capacity
- **Military personnel** (7 sub-fields): Various manpower availability/fitness metrics
- **Maritime claims** (6 sub-fields): Contiguous zone, continental shelf, EEZ, fishing zone, etc.

The data is NOT merged — each sub-field retains its own row in `CountryFields`. The `ConsolidatedTo` column in `FieldNameMappings` simply indicates the logical parent for grouping in analysis.

#### Rule 5: Government Body Detection
1990s data often had country-specific legislative body names as field names (e.g., "Bundestag", "Knesset", "Majlis"). These are detected by checking against `GOV_BODY_KEYWORDS`:

```python
GOV_BODY_KEYWORDS = [
    "Assembly", "Senate", "Parliament", "Congress", "Council",
    "Chamber", "House of", "Duma", "Diet", "Sejm", "Knesset",
    "Bundestag", "Bundesrat", "Majlis", "Tribunal", "Court", ...
]
```

Only applied to entries from years ≤2001 with ≤100 uses (to avoid false positives on modern data).

#### Rule 5b/5c: Regional and Reference Entries
Two explicit sets handle known edge cases:
- `REGIONAL_ENTRIES` (80+ entries): "Turkish Area", "Serbia", "Sabah", "Welsh" — regional sub-entries from 1990s data
- `MISC_REFERENCE` (40+ entries): "Appendixes", "Terminology", "Data code" — reference/glossary entries

#### Rule 6: Noise Detection
The `is_noise()` function applies multiple heuristics:

```python
def is_noise(name, use_count, first_year, last_year):
    if len(name) <= 2 and name.isalpha(): return True          # "A", "UK" as field names
    if name.endswith('.') and len(name) <= 6: return True       # "avdp.", "c.i.f."
    if name[0].islower() and use_count <= 10: return True       # lowercase fragments
    if len(name) > 80 and use_count <= 3: return True           # long descriptive text
    if any(p in lower for p in NOISE_PHRASES): return True      # known junk phrases
    if name in SUB_FIELD_LABELS: return True                    # 1994 sub-field labels
    # ... more checks
```

281 entries are flagged as noise. They remain in the table (with `IsNoise=1`) for transparency but should always be filtered out in analysis queries with `WHERE fm.IsNoise = 0`.

#### Rule 7: Manual Fallback
Anything that doesn't match rules 1-6 is kept as-is and flagged `MappingType = 'manual'` for human review.

---

## 6. Entity Type Classification

Each of the 281 master entities is classified into one of 9 types using a combination of automated field analysis and manual overrides.

### Automated Classification

For each entity, the script reads the most recent year's "Dependency status" and "Government type" fields:

```sql
SELECT TOP 1 cf.Content
FROM CountryFields cf
JOIN Countries c ON cf.CountryID = c.CountryID
WHERE c.MasterCountryID = ?
  AND cf.FieldName LIKE '%ependency%status%'
ORDER BY c.Year DESC
```

**If dependency status exists** and contains keywords like "territory", "dependency", "overseas", "unincorporated", "self-governing" → classified as `territory`.

**If no dependency status**, government type is checked for sovereign-state keywords: "republic", "monarchy", "kingdom", "democracy", "federation", "parliamentary", "presidential", "communist", etc. → classified as `sovereign`.

### Manual Overrides (`OVERRIDES` Dictionary)

40+ entries that can't be auto-classified or where the automated logic gets it wrong:

- **Oceans**: Arctic, Atlantic, Indian, Pacific, Southern Ocean → `misc`
- **Non-countries**: World, European Union → `misc`
- **Disputed**: Kosovo, Gaza Strip, West Bank, Paracel Islands, Spratly Islands → `disputed`
- **Special Administrative Regions**: Hong Kong, Macau → `special_admin`
- **Crown Dependencies**: Jersey, Guernsey, Isle of Man → `crown_dependency`
- **Freely Associated**: Marshall Islands, Micronesia, Palau → `freely_associated`
- **Antarctic**: Antarctica → `antarctic`
- **Dissolved**: Netherlands Antilles, Serbia and Montenegro → `dissolved`
- **US Minor Outlying**: Baker Island, Howland Island, etc. → `territory`
- **French Scattered Islands**: Bassas da India, Europa Island, etc. → `territory`

### Administering Country Links

The `AdministeringMasterCountryID` column in `MasterCountries` is a self-referencing foreign key that records which sovereign nation administers each territory. This was populated by cross-referencing the "Dependency status" field content (e.g., "overseas territory of the UK") with the master country list.

---

## 7. Validation & Quality Assurance

### Validation Script (`validate_integrity.py`)

Nine automated checks run against the completed database:

#### Check 1: Structural Overview
```sql
SELECT c.Year, c.Source, COUNT(DISTINCT c.CountryID) as Countries
FROM Countries c WHERE c.Year >= 2000
GROUP BY c.Year, c.Source ORDER BY c.Year
```
Verifies every year has data, reasonable country counts (180-270), and correct source labels.

#### Check 2: US Population Benchmark
For each year 2000-2025, extracts the US population field and compares against known Census Bureau estimates:

```python
known_us_pop = {
    2000: 275, 2001: 278, 2002: 280, ..., 2025: 338,  # millions
}
```

The extracted text is parsed for numbers in the range 200M-400M. Pass criterion: within 10 million of the known value.

This is the **single most important validation** — if the US population is correct for a given year, the parser is almost certainly working correctly for that year's format.

#### Check 3: US GDP Benchmark
Spot-checks US GDP field content for years 2000, 2005, 2010, 2015, 2020, 2025. Verifies plausible dollar amounts are present (not a structural check, just a sanity check).

#### Check 4: Country Count Year-over-Year Deltas
```sql
SELECT Year, COUNT(*) as cnt FROM Countries WHERE Year >= 2000
GROUP BY Year ORDER BY Year
```
Flags any year-over-year change of more than 10 countries, which would indicate a parser issue (not real-world entity changes, which are gradual).

#### Check 5: Data Source Provenance
Verifies the `Source` column matches expected values:
- 1990-1999, 2001: `text`
- 2000, 2002-2020: `html`
- 2021-2025: `json`

#### Check 6: Field Count Progression
Calculates year-over-year percentage change in total fields. Flags anomalies >15%, which typically indicate a parser failing to extract data from a particular format change.

#### Check 7: Category Coverage
Verifies that key categories ("People" / "People and Society", "Economy") exist for nearly all countries each year. More than 10 missing countries per year triggers a warning.

#### Check 8: China Population Spot Check
Independent verification using a second country (China) to ensure the US benchmark isn't a fluke. Checks population values for years 2000, 2005, 2010, 2015, 2020, 2025.

#### Check 9: Null/Empty Field Audit
```sql
SELECT c.Year,
       SUM(CASE WHEN cf.Content IS NULL OR LTRIM(RTRIM(cf.Content)) = '' THEN 1 ELSE 0 END) as empty,
       COUNT(*) as total
FROM Countries c
JOIN CountryFields cf ON c.CountryID = cf.CountryID
GROUP BY c.Year ORDER BY c.Year
```
Flags years where >5% of fields have empty content, indicating a parser failing to extract field values.

### Additional Verification Queries

Beyond the automated script, the following SQL queries were used during development to verify data quality:

**Uniqueness check** — Verify JSON years have distinct data (not the same snapshot loaded 5 times):
```sql
SELECT c.Year, COUNT(cf.FieldID) AS Fields
FROM Countries c
LEFT JOIN CountryFields cf ON c.CountryID = cf.CountryID
WHERE c.Year BETWEEN 2021 AND 2025
GROUP BY c.Year ORDER BY c.Year
-- Field counts should differ between years
```

**Field name mapping coverage** — Verify every field name has a mapping:
```sql
SELECT COUNT(DISTINCT cf.FieldName) AS Total,
       COUNT(DISTINCT CASE WHEN fm.MappingID IS NOT NULL THEN cf.FieldName END) AS Mapped
FROM CountryFields cf
LEFT JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
-- Total should equal Mapped (100% coverage)
```

**Cross-year field consistency** — Track a known field across all years:
```sql
SELECT c.Year, cf.FieldName, LEFT(cf.Content, 80) AS Preview
FROM CountryFields cf
JOIN Countries c ON cf.CountryID = c.CountryID
JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
WHERE fm.CanonicalName = 'Population'
  AND mc.CanonicalName = 'United States'
ORDER BY c.Year
-- Should show population for all 36 years with field name changes visible
```

---

## 8. Data Repair Log

### v2 Data Drop (February 19, 2026)

Comprehensive validation identified and repaired two data quality issues:

#### 1996 Truncated Countries (7 sovereign states)

The Project Gutenberg edition (ebook #27675) of the 1996 CIA World Factbook was **truncated** for 7 sovereign countries: Venezuela, Armenia, Greece, Luxembourg, Malta, Monaco, and Tuvalu. Their entries in the Gutenberg text literally end mid-sentence with `======` separators, cutting off after Geography/People sections. This is a source defect in the Gutenberg transcription, not a parser bug.

**Root cause**: The Gutenberg volunteer who uploaded ebook #27675 (released December 2008) worked from incomplete source material. Sections for these 7 countries were never included.

**Fix**: Downloaded the CIA's own original text file (`wfb-96.txt.gz`) from the Wayback Machine, archived at `odci.gov/cia/publications/nsolo/` in May 1997. This file contains complete data for all 266 countries. Wrote a dedicated parser (`etl/repair_1996_truncated.py`) for the CIA original's page-header format (`FACTBOOK COUNTRY REPORT` headers, 5-space indented fields). Replaced truncated entries in the database:

| Country | Before (fields) | After (fields) |
|---------|-----------------|----------------|
| Venezuela | 8 | 89 |
| Armenia | 27 | 87 |
| Greece | 27 | 83 |
| Luxembourg | 35 | 88 |
| Malta | 49 | 86 |
| Monaco | 48 | 82 |
| Tuvalu | 47 | 80 |

#### Zimbabwe 1998 Field Duplication

The 1998 HTML parser incorrectly dumped 178 fields into the "Transnational Issues" category for Zimbabwe, including appendix pages (Abbreviations, Appendix A-H), field definition text, and duplicates of fields already correctly categorized elsewhere. Only 2 legitimate Transnational Issues fields existed (Disputes-international, Illicit drugs).

**Fix**: Deleted 176 noise/duplicate fields from the Transnational Issues category. Zimbabwe 1998 went from 272 fields to 96 (matching the 1997 count).

#### Germany GDP 1994-1996

Germany's GDP data for 1994-1996 was stored under the field name "Germany" (a self-named field artifact from the CIA's 1994 database restructuring) instead of "National product" or "GDP". The data existed but was invisible to cross-year GDP queries.

**Fix**: Inserted 3 new CountryFields records with `FieldName='National product'` for Germany 1994-1996, using the GDP values from the self-named "Germany" fields.

---

## 9. Known Limitations

### Data Quality
- **1990 has fewer fields per country** (~63 vs ~140+ in later years) due to the simpler text format
- **1994 has inflated field counts** (28,633 vs ~19,000 for neighboring years) because the HTML structure that year caused sub-field labels to be parsed as standalone fields (these are flagged as noise)
- **2001 uses text source** instead of HTML, which has slightly different field granularity
- **Content is text-only** — images, maps, and flags from the original Factbook are not included

### Parser Limitations
- **"Full Content" fallback**: If a parser can't identify structured sections, it captures the entire page text as a single field. This happens rarely but means some country-years may have one large text blob instead of structured categories/fields
- **Country name extraction**: For years 2006-2012, the country name was not in the `<title>` tag, requiring fallback to CSS class names or breadcrumb parsing. Some names may have formatting artifacts

### Standardization Limitations
- **Some 1990s field names are ambiguous** — e.g., "Branches" could refer to military branches or government branches. Context-dependent mappings default to the most common usage
- **Consolidation is logical only** — sub-field data is not actually merged in the database, just tagged with a `ConsolidatedTo` parent
- **281 noise entries may include some legitimate fields** — the noise heuristics are conservative but imperfect. Review with `SELECT * FROM FieldNameMappings WHERE IsNoise = 1 ORDER BY UseCount DESC`

### Entity Resolution
- **Some historical entities have no MasterCountryID** — dissolved states or very old entries may not link to the master table (NULL foreign key)
- **Name matching is fuzzy** — the 1990s text parser occasionally mismatches countries with very similar names
