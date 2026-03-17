# Known Quirks & Limitations

Things to be aware of when working with the archive.

---

## Format Quirks

### 1994 Database Restructure
The CIA restructured their internal database in 1994. Sub-fields that were normally indented under parent fields suddenly appeared at column 0 as top-level entries. This inflated the 1994 field count to **28,633** (vs. ~19,000 for neighboring years). The parser handles this by checking if the first character of a field name is lowercase (sub-fields) vs. uppercase (parent fields). The extra sub-field entries are flagged as noise in `FieldNameMappings`.

### 2001 Corrupted HTML
The Wayback Machine's HTML zip archive for the 2001 edition was corrupted. Parsing falls back to the Project Gutenberg plain-text edition for that year. This is the only year where the HTML and text pipelines had to swap.

### 1996 Truncated Countries
Project Gutenberg's 1996 edition was truncated for 7 countries: Venezuela, Armenia, Greece, Luxembourg, Malta, Monaco, and Tuvalu. These were repaired using the CIA's original `wfb-96.txt.gz` file recovered from the Wayback Machine.

---

## Field Name Issues

### Silent Renames
The CIA renamed fields without notice across editions. Examples:
- `National product` became `GDP (purchasing power parity)` became `Real GDP (purchasing power parity)`
- `Defense expenditures` became `Military expenditures`
- `Telephones` split into `Telephones - fixed lines` and `Telephones - mobile cellular`

Always query through `FieldNameMappings` to get consistent results. See [Field Name Mappings](Field-Name-Mappings).

### Dash Formatting
Field names containing dashes appeared in at least 3 formats: `Airports-with paved runways`, `Airports--with paved runways`, `Airports - with paved runways`. All are normalized to the spaced-dash form.

### Country-Specific Noise
1990s editions embedded government body names (parliaments, assemblies, courts) as top-level fields. These are classified as `noise` in `FieldNameMappings` and should be filtered with `IsNoise = 0`.

---

## Entity Issues

### Name Changes
Some entities changed names during the archive period:
- Burma / Myanmar
- Ivory Coast / Cote d'Ivoire
- Swaziland / Eswatini
- Macedonia / North Macedonia

The `MasterCountries` table uses the most recent canonical name, and all year-specific entries link to the same `MasterCountryID`.

### Dissolved States
A few entities appear in early years but dissolve later:
- **Soviet Union**: 1990-1991 only
- **Yugoslavia**: Fragments through the 1990s
- **Serbia and Montenegro**: Splits in 2006
- **Netherlands Antilles**: Dissolved in 2010

These are tagged with `EntityType = 'dissolved'` in `MasterCountries`.

### Sub-Entries
Turkish Cyprus, Malaysian states, and Netherlands Antilles islands sometimes appear as separate sub-entries rather than part of their parent entity.

---

## Data Quality

### No Data Added
The archive contains only what the CIA published. No external data is mixed in. Reference tables (ISO codes, entity classifications, COCOM assignments) sit alongside the source data but are clearly separate.

### Computed Values
A small number of `FieldValues` rows are derived rather than extracted. For example, pre-1995 editions sometimes reported male and female life expectancy but not the total -- the parser computes the average and flags it with `IsComputed = 1`. Always check this flag if provenance matters for your analysis.

### Encoding
Early text editions (1990s) occasionally contain encoding artifacts from the ASCII-to-UTF-8 conversion. These are tracked in `data/encoding_audit.json` and `data/bad_chars.json`. As of v3.5, all known encoding issues have been fixed: 37 fields with U+FFFD replacement characters (2006-2017) were repaired, and 6,717 fields with accent-stripped characters (2021-2025) were re-parsed with corrected HTML entity decoding.

### Coverage Gaps
Not every field exists for every country in every year. The CIA added and removed fields over time, and smaller territories often have fewer fields than sovereign nations. Field counts per year range from ~15,000 (1990) to ~39,000 (2021).

---

## SQLite-Specific Notes

### FTS5 Search
The full-text search index (`CountryFieldsFTS`) uses SQLite's FTS5 extension. FTS5 must be enabled in your SQLite build (it is included by default in Python's `sqlite3` module and most modern SQLite distributions).

### Database Size
The database is ~662 MB due to the large volume of text in `CountryFields.Content` and `FieldValues.SourceFragment`. Queries that scan the full `CountryFields` table without index support may be slow. Always filter by `Year`, `FieldName`, or use the FTS index for text search.

### No Foreign Key Enforcement
SQLite does not enforce foreign keys by default. Run `PRAGMA foreign_keys = ON;` if you need FK constraint checking in your session.
