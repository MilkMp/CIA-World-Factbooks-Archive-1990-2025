# Release v3.2 — Pipe Delimiters, SourceFragment, and 18 New Parsers

**Date:** February 28, 2026
**Triggered by:** [Issue #10](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/issues/10) — feedback from [@jarofromel](https://github.com/jarofromel)

---

## What Changed and Why

A contributor identified two problems in our v3.0 parsing pipeline:

1. **Ambiguous delimiters** — Collapsing original newlines to spaces in `CountryFields.Content` made sub-field parsing unreliable. Spaces appear everywhere in text, so there was no reliable way to tell where one sub-field ended and another began.

2. **Missing provenance** — When a FieldValues row said `NumericVal = 1.05, Units = male(s)/female`, there was no way to verify what text it was parsed from, or to detect when a parser silently dropped data.

Both problems were real. We fixed both.

---

## v3.0 vs v3.2 — By the Numbers

| Metric | v3.0 | v3.2 | Change |
|--------|------|------|--------|
| Country-year records | 9,500 | 9,536 | +36 |
| Category records | 83,599 | 83,682 | +83 |
| Data fields | 1,061,522 | 1,071,603 | +10,081 |
| Structured sub-values | 1,423,506 | 1,610,973 | +187,467 |
| Distinct sub-fields | 1,848 | 2,386 | +538 |
| Dedicated parsers | 34 | 55 | +21 |
| Database size (SQLite) | ~542 MB | ~636 MB | +94 MB |

Every delta is positive. No data was lost — only gained.

### Single Database

v3.0 shipped two separate SQLite files: `factbook.db` (core tables + FTS5 search) and `factbook_field_values.db` (core tables + FieldValues). This was confusing — people didn't know which to use or whether they needed both.

v3.2 consolidates everything into one file: **`factbook.db`** (636 MB). It contains all 8 tables (core + FieldValues + FTS5 + ISOCountryCodes). The size difference was only 78 MB, not worth the confusion of two files. Download one database, get everything.

---

## Architecture: How the Pipeline Works

```
                          CIA World Factbook Sources
                          ==========================

    1990-2001 (Text)        2002-2020 (HTML)        2021-2025 (JSON)
    Project Gutenberg       Wayback Machine         factbook-json-cache
         |                       |                        |
         v                       v                        v
  load_gutenberg_years.py   build_archive.py       reload_json_years.py
  4 format variants         5 HTML generations      git year-end commits
  ' | '.join(parts)         html_to_pipe_text()     pipe-aware strip_html()
         |                       |                        |
         +-------+---------------+------------------------+
                 |
                 v
         SQL Server (CIA_WorldFactbook)
         ==============================
         MasterCountries     281 canonical entities
         Countries           9,536 country-year records
         CountryCategories   83,682 section headings
         CountryFields       1,071,603 fields (pipe-delimited Content)
         FieldNameMappings   1,090 -> 414 canonical names
                 |
                 v
         parse_field_values.py (55 parsers)
         ==================================
         Reads CountryFields.Content
         Dispatches by CanonicalName -> dedicated parser
         Falls back to generic pipe-split parser
         Writes FieldValues with SourceFragment
                 |
                 v
         FieldValues          1,610,973 typed sub-values
         ===========          2,386 distinct sub-fields
         SubField             e.g. "total_population", "male", "land"
         NumericVal           e.g. 80.9, 9833517, 3.45
         Units                e.g. "years", "sq km", "% of GDP"
         TextVal              e.g. "parliamentary democracy"
         DateEst              e.g. "2024 est."
         SourceFragment       e.g. "total population: 80.9 years"
                 |
                 v
         export_to_sqlite.py -> factbook.db (636 MB)
         + FTS5 full-text index
         + ISOCountryCodes (250 rows)
                 |
                 v
         worldfactbookarchive.org (FastAPI + Jinja2)
```

---

## Change 1: Content Delimiter Migration (Space -> Pipe)

### The Problem

Original CIA data uses newlines between sub-fields:

```
total population: 80.9 years
male: 78.7 years
female: 83.1 years
```

v3.0 collapsed these to spaces during parsing:

```
total population: 80.9 years male: 78.7 years female: 83.1 years
```

This created ambiguity — "years male" could be a value continuation or a sub-field boundary. The generic parser had to use heuristic label detection (`r'(\w[\w\s]*?):\s'`) which failed on edge cases.

### The Fix

v3.2 uses pipe (`|`) as the sub-field delimiter:

```
total population: 80.9 years | male: 78.7 years | female: 83.1 years
```

Pipes never appear in CIA field values, so the boundary is always unambiguous. The generic fallback parser now simply splits on `' | '`.

### Blast Radius

Audited every downstream consumer. Impact was minimal:

```
 Component                     Impact    Reason
 ────────────────────────────── ──────── ──────────────────────────────
 Webapp (country, field pages)  None     Displays Content verbatim
 Webapp (analysis dashboards)   None     Parses with regex, not delimiters
 FTS5 search index              None     SQLite tokenizer treats | as boundary
 StarDict dictionaries          None     Shows Content verbatim
 API v2 endpoints               None     Returns Content as-is in JSON
 CSV/Excel exports              None     Exports Content column directly
 FieldValues parsers (55)       None     Use field-specific regex patterns
 Generic fallback parser        Better   Already split on ' | '
```

2015-2020 data was already pipe-delimited, so the entire stack was proven to work with pipes before we made the change.

### Files Changed

```
 File                       Change
 ────────────────────────── ──────────────────────────────────────────
 etl/build_archive.py       + html_to_pipe_text() helper function
                              Replaces <br>, </p><p>, </div><div> with |
                              Applied in parse_classic(), parse_table_format(),
                              parse_collapsiblepanel_format()

 etl/load_gutenberg_years.py  Changed 4 x ' '.join() to ' | '.join()
                              in extract_indented_fields() and
                              extract_mixed_fields()
                              (NOT extract_inline_fields — those are
                              continuation lines, not sub-fields)

 etl/reload_json_years.py   Rewrote strip_html() with pipe-aware logic
                              <br><br> and </p><p> become ' | '
                              Remaining tags become spaces
```

---

## Change 2: SourceFragment Column

### The Problem

v3.0 FieldValues had no provenance. You could see `NumericVal = 1.05` but not what text produced it.

### The Fix

Every FieldValues row now includes `SourceFragment` — the exact text slice matched by the parser:

```sql
SELECT SubField, NumericVal, Units, SourceFragment
FROM FieldValues fv
JOIN CountryFields cf ON fv.FieldID = cf.FieldID
JOIN Countries c ON cf.CountryID = c.CountryID
WHERE c.Name = 'United States' AND c.Year = 2025
  AND cf.FieldName = 'Sex ratio';
```

| SubField | NumericVal | Units | SourceFragment |
|----------|-----------|-------|----------------|
| at_birth | 1.05 | male(s)/female | at birth: 1.05 male(s)/female |
| 0-14_years | 1.06 | male(s)/female | 0-14 years: 1.06 male(s)/female |
| 15-24_years | 1.19 | male(s)/female | 15-24 years: 1.19 male(s)/female |
| total_population | 1.0 | male(s)/female | total population: 1 male(s)/female |

### Parse Confidence Metric

SourceFragment enables automated quality checks:

```sql
-- Flag under-parsed fields (< 50% of Content was captured)
SELECT cf.FieldID, cf.FieldName,
       LENGTH(cf.Content) AS content_len,
       SUM(LENGTH(fv.SourceFragment)) AS parsed_len,
       ROUND(100.0 * SUM(LENGTH(fv.SourceFragment)) / LENGTH(cf.Content), 1) AS pct
FROM FieldValues fv
JOIN CountryFields cf ON fv.FieldID = cf.FieldID
GROUP BY cf.FieldID
HAVING pct < 50
ORDER BY pct;
```

---

## Change 3: 18 New Dedicated Parsers

### The Problem

The generic parser splits Content on `' | '` and matches label:value patterns. This fails when:
- Labels start with digits: `0-14 years: 1.06 male(s)/female`
- Values have no label: the first entry in a list
- Sub-fields use non-standard formats: `at birth: 1.05 male(s)/female`

The issue #10 contributor's Sex ratio example showed 7 sub-values being collapsed to 1.

### The Fix

Wrote dedicated parsers for every field where the generic approach fails:

```
 Parser                    Fields Covered                Sub-values
 ────────────────────────── ──────────────────────────── ──────────
 parse_sex_ratio            Sex ratio                    7 age brackets
 parse_literacy             Literacy                     3 (total/m/f)
 parse_maritime_claims      Maritime claims               3-4 zones
 parse_natural_gas          Natural gas (x4)             5 per field
 parse_internet_users       Internet users               2 (total + %)
 parse_telephones           Telephones (x2)              2 per field
 parse_gdp_composition      GDP composition by sector    3 sectors
 parse_household_income     Household income shares      2 deciles
 parse_school_life_exp      School life expectancy       3 (total/m/f)
 parse_youth_unemployment   Youth unemployment           3 (total/m/f)
 parse_co2_emissions        CO2 emissions                4 (total + fuels)
 parse_water_withdrawal     Water withdrawal             3-5 sectors
 parse_broadband            Broadband subscriptions      2 (total + %)
 parse_water_sanitation     Drinking water + Sanitation  6 categories
 parse_waste_recycling      Waste and recycling          3 metrics
 parse_forest_revenue       Forest revenue               1 (% of GDP)
```

### Parser Dispatch Flow

```
                   CountryFields.Content
                          |
                          v
              FieldNameMappings lookup
              (OriginalName -> CanonicalName)
                          |
                          v
                 PARSER_REGISTRY[CanonicalName]
                    /          \
                found?        not found?
                 /                \
                v                  v
         Dedicated Parser    Generic Fallback
         (field-specific     (split on ' | ',
          regex patterns)     match label:value)
                \                /
                 v              v
              FieldValues rows
              (SubField, NumericVal, Units,
               TextVal, DateEst, SourceFragment)
```

---

## Change 4: 1996 Data Repair

During the full database rebuild, we discovered that the Project Gutenberg source for 1996 is truncated for 7 countries: Venezuela, Armenia, Greece, Luxembourg, Malta, Monaco, and Tuvalu. The text files end mid-sentence.

The v3.0 database had silently leaked neighboring country data into the truncated entries (e.g., Vanuatu's Communications and Defense fields appeared under Venezuela).

### The Fix

The CIA's original `wfb-96.txt.gz` file was found on the Wayback Machine:
`https://web.archive.org/web/19970528151800id_/http://www.odci.gov:80/cia/publications/nsolo/wfb-96.txt.gz`

A repair script (`etl/repair_1996_truncated.py`) parses the CIA's page-header format and replaces the truncated entries with complete data. Venezuela went from 8 fields (truncated) to 89 fields (complete).

---

## Data Flow: From Issue to Deployment

```
 Issue #10 feedback (jarofromel)
     |
     |  "space delimiter is wrong"
     |  "add source fragment for debugging"
     |
     v
 Investigation (Feb 27-28)
     |
     |  Audited all downstream consumers
     |  Confirmed 2015-2020 already used pipes
     |  Identified 16+ fields where generic parser fails
     |
     v
 Implementation (Feb 28)
     |
     |  1. Pipe delimiter migration (3 ETL scripts)
     |  2. SourceFragment column (schema + all 55 parsers)
     |  3. 18 new dedicated parsers
     |  4. Full database rebuild (all 36 years)
     |  5. 1996 data repair from CIA original
     |
     v
 Validation
     |
     |  v3.0 vs v3.2 comparison: all deltas positive
     |  Local webapp testing: all pages 200
     |  Pipe verification across all eras (1995, 2005, 2015, 2025)
     |
     v
 Deployment
     |
     |  Fly.io deploy with 636 MB database
     |  GitHub Pages updated
     |  Issue #10 response updated
     |
     v
 Live at worldfactbookarchive.org
```

---

## Files Changed

| File | Lines Changed | What |
|------|--------------|------|
| `etl/build_archive.py` | +35 | `html_to_pipe_text()` helper, applied in 3 parser functions |
| `etl/load_gutenberg_years.py` | +4/-4 | 4x `' '.join()` -> `' \| '.join()` |
| `etl/reload_json_years.py` | +15/-5 | Pipe-aware `strip_html()` rewrite |
| `etl/structured_parsing/parse_field_values.py` | +850 | 18 new parsers + SourceFragment in all parsers |
| `etl/structured_parsing/export_field_values_to_sqlite.py` | +79 | SourceFragment column support |
| `etl/structured_parsing/validate_field_values.py` | +68 | Updated validation for new parsers |
| `etl/structured_parsing/DESIGN.md` | +159 | v3.2 changelog and documentation |
| `schema/create_field_values.sql` | +1 | SourceFragment column in DDL |
| `README.md` | +40/-32 | Updated all stats to v3.2 numbers |
| `docs/index.html` | +12/-12 | Updated GitHub Pages stats and descriptions |

---

## Acknowledgments

This release was directly driven by feedback from [@jarofromel](https://github.com/jarofromel) in [Issue #10](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/issues/10). Their suggestion to add source provenance (SourceFragment) and fix the delimiter problem (space -> pipe) led to a full pipeline rebuild that improved every metric in the database.
