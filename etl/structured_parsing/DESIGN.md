# Structured Field Parsing — Design Document

> **Status**: Shipped (v3.0 2026-02-26, v3.2 2026-02-28)
> **Location**: `etl/structured_parsing/`
> **Author**: Milan Milkovich
> **Date**: 2026-02-26

## Why This Exists

[Issue #10](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/issues/10)
(see also [#9](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/issues/9))
pointed out that while our fields are stored as raw text, they contain more structure
than it appears — and directed us to
[iancoleman/cia_world_factbook_api](https://github.com/iancoleman/cia_world_factbook_api),
a project that parses the CIA Factbook HTML into structured JSON with typed values
(numbers, units, GPS coordinates, percentages). Their parser covers 2007-present and
breaks every field into individually queryable sub-values.

Separately, there has been a request for the archive in StarDict format for use with
KOReader (an open-source e-reader), which requires structured field data to produce
useful dictionary entries.

Our archive has broader coverage (1990-2025, 281 entities, 1,061,522 field records) but
stores each field's content as a single text blob. We have the same underlying data — we
just haven't decomposed it yet. Comparing the two side-by-side made the gap clear:

- **Their data**: `"area": {"total": {"value": 7741220, "units": "sq km"}}`
- **Our data**: `"total: 7,741,220 sq km | land: 7,682,300 sq km | water: 58,920 sq km"`

Same information, but theirs is machine-queryable and ours requires regex extraction on
every query. This project closes that gap — adding a structured parsing layer on top of
our existing data so every sub-value becomes individually chartable, rankable, and
comparable across all 36 years.

---

## Overview

The CIA Factbook Archive stores 1,061,522 field records across 281 entities and 36 years
(1990-2025). Currently, each field's content is stored as a **single text blob** in
`CountryFields.Content`. This project adds a **structured parsing layer** that decomposes
those text blobs into individually addressable, typed sub-values — without adding any new
information.

**This is not new data. Every value extracted already exists inside the text blobs. We are
decomposing, not inventing.**

---

## The Problem

### Current State (2 levels)

```
CountryFields
┌─────────────────────────────────────────────────────────────────────────┐
│ FieldName: "Area"                                                       │
│ Content:   "total: 7,741,220 sq km land: 7,682,300 sq km               │
│             water: 58,920 sq km note: includes Lord Howe Island"        │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ FieldName: "Life expectancy at birth"                                   │
│ Content:   "total population: 83.5 years (2024 est.)                    │
│             male: 81.3 years female: 85.7 years"                        │
└─────────────────────────────────────────────────────────────────────────┘
```

- Human-readable but not machine-queryable
- Cannot chart "total area" across 36 years without regex on every query
- Cannot rank countries by male life expectancy
- Cannot correlate GDP growth with military spending as percentages

### Why This Hurts — Query Comparison

**Example: "Rank the top 10 countries by total land area in 2025"**

Current state — regex on every row, fragile, slow:

```sql
-- CURRENT: regex extraction on every query (fragile, slow, breaks across eras)
SELECT c.Name,
       CAST(
         REPLACE(
           REPLACE(
             SUBSTR(cf.Content,
               INSTR(cf.Content, 'land:') + 5,
               INSTR(SUBSTR(cf.Content, INSTR(cf.Content, 'land:') + 5), ' sq km') - 1
             ),
           ',', ''),
         ' ', '')
       AS REAL) as land_area_sq_km
FROM CountryFields cf
JOIN Countries c ON cf.CountryID = c.CountryID
WHERE c.Year = 2025
  AND cf.FieldName = 'Area'
  AND cf.Content LIKE '%land:%'
ORDER BY land_area_sq_km DESC
LIMIT 10;

-- Problems:
--   1990-1994 says "land area:" not "land:"
--   1993 uses "km2" not "sq km"
--   2015-2020 uses " | " pipe delimiters
--   Some years put "land:" before "total:", some after
--   Breaks silently when format changes — wrong numbers, not errors
```

Target state — clean, fast, works across all eras:

```sql
-- AFTER: direct numeric query (clean, fast, works across all 36 years)
SELECT c.Name, fv.NumericVal as land_area_sq_km
FROM FieldValues fv
JOIN CountryFields cf ON fv.FieldID = cf.FieldID
JOIN Countries c ON cf.CountryID = c.CountryID
WHERE c.Year = 2025
  AND cf.FieldName = 'Area'
  AND fv.SubField = 'land'
ORDER BY fv.NumericVal DESC
LIMIT 10;

-- Works identically for 1990 and 2025
-- No regex, no string parsing, no era-specific hacks
-- Sub-field names already normalized during ETL
```

**Example: "Chart Japan's life expectancy (male vs female) from 1990 to 2025"**

```sql
-- CURRENT: different regex per era, male/female order varies
-- 1990: "76 years male, 82 years female (1990)"
-- 1995: "total population: 79.44 years male: 76.6 years female: 82.42 years"
-- 2018: "total population: 85.5 years (2018 est.) | male: 82.2 years | female: 89 years"
-- Need 3+ different regex patterns, UNION'd together, hope nothing breaks

-- AFTER: one query, all 36 years
SELECT c.Year, fv.SubField, fv.NumericVal
FROM FieldValues fv
JOIN CountryFields cf ON fv.FieldID = cf.FieldID
JOIN Countries c ON cf.CountryID = c.CountryID
WHERE c.Name = 'Japan'
  AND cf.FieldName = 'Life expectancy at birth'
  AND fv.SubField IN ('male', 'female')
ORDER BY c.Year, fv.SubField;
```

The regex approach doesn't just make queries ugly — it makes them **unreliable**. Format
changes across eras mean a regex that works for 2025 silently returns wrong values for
1995, or NULL for 1990. The structured parsing does the hard work once during ETL so
every downstream query is clean and trustworthy.

### Target State (3 levels)

```
CountryFields                          FieldValues
┌──────────────────────────┐           ┌────────────────────────────────────┐
│ FieldID: 42              │     ┌────>│ SubField: "total"                  │
│ FieldName: "Area"        │     │     │ NumericVal: 7741220.0              │
│ Content: "total: 7,74.." │─────┤     │ Units: "sq km"                     │
└──────────────────────────┘     │     ├────────────────────────────────────┤
                                 ├────>│ SubField: "land"                   │
                                 │     │ NumericVal: 7682300.0              │
                                 │     │ Units: "sq km"                     │
                                 │     ├────────────────────────────────────┤
                                 └────>│ SubField: "water"                  │
                                       │ NumericVal: 58920.0                │
                                       │ Units: "sq km"                     │
                                       └────────────────────────────────────┘

┌──────────────────────────┐           ┌────────────────────────────────────┐
│ FieldID: 87              │     ┌────>│ SubField: "total population"       │
│ FieldName: "Life         │     │     │ NumericVal: 83.5                   │
│  expectancy at birth"    │─────┤     │ Units: "years"                     │
│ Content: "total pop..."  │     │     ├────────────────────────────────────┤
└──────────────────────────┘     ├────>│ SubField: "male"                   │
                                 │     │ NumericVal: 81.3                   │
                                 │     │ Units: "years"                     │
                                 │     ├────────────────────────────────────┤
                                 └────>│ SubField: "female"                 │
                                       │ NumericVal: 85.7                   │
                                       │ Units: "years"                     │
                                       └────────────────────────────────────┘
```

- Same information, decomposed into queryable atoms
- Chart any sub-field across all years and countries instantly
- Rank, correlate, and compare at the sub-field level
- Original `Content` text blob remains untouched as source of truth

---

## What Changes in the UI

### Archive Country Page — No new sections

```
BEFORE                                    AFTER
─────────────────────────────             ─────────────────────────────
Geography          (section)              Geography          (section)
  Area             (field)                  Area             (field)
    "total: 7,741,220 sq km                  total     7,741,220 sq km
     land: 7,682,300 sq km                   land      7,682,300 sq km
     water: 58,920 sq km"                    water        58,920 sq km
                                             [raw text toggle]
  Coastline        (field)                  Coastline        (field)
    "25,760 km"                              25,760 km
```

The Table of Contents stays identical:
```
Geography .............. 20 entries
People and Society ..... 36 entries    <-- NO CHANGE to section count
Economy ................ 29 entries        or field count
Energy .................  7 entries
```

Sub-values appear WITHIN each field as an expandable detail view. No new TOC entries,
no new sections, no new fields. Just structured content inside existing fields.

### Analytics Pages — Major unlock

Field Explorer dropdowns expand from flat field names to nested sub-field selectors:
```
BEFORE                              AFTER
──────────────────                  ──────────────────
[ Area            ]                 [ Area > total (sq km)       ]
[ Population      ]                 [ Area > land (sq km)        ]
[ Exports         ]                 [ Area > water (sq km)       ]
                                    [ Population > total         ]
                                    [ Population > male          ]
                                    [ Population > female        ]
                                    [ Exports > value (USD)      ]
                                    [ Exports > commodities      ]
                                    [ Exports > partners         ]
```

Each sub-field becomes individually chartable, rankable, and comparable across all 281
entities and 36 years.

---

## Database Schema

### New Table: `FieldValues`

```sql
CREATE TABLE FieldValues (
    ValueID     INTEGER PRIMARY KEY AUTOINCREMENT,
    FieldID     INTEGER NOT NULL REFERENCES CountryFields(FieldID),
    SubField    TEXT NOT NULL,       -- 'total', 'male', 'land', 'growth_rate'
    NumericVal  REAL,                -- 7741220.0  (NULL if non-numeric)
    Units       TEXT,                -- 'sq km', '%', 'years', 'USD', 'bbl/day'
    TextVal     TEXT,                -- non-numeric: country names, descriptions
    DateEst     TEXT,                -- '2024 est.', 'FY93', '2019 est.'
    Rank        INTEGER,             -- global rank if present in source
    SourceFragment TEXT              -- (v3.1) exact substring of Content that produced this row
);

CREATE INDEX idx_fv_field ON FieldValues(FieldID);
CREATE INDEX idx_fv_subfield ON FieldValues(SubField);
CREATE INDEX idx_fv_numeric ON FieldValues(NumericVal) WHERE NumericVal IS NOT NULL;
```

**SourceFragment** (added v3.1): Stores the exact text slice from `CountryFields.Content`
that each sub-value was parsed from. Enables debugging (see what text produced each value)
and automated quality checks (detect when large Content strings produce few sub-values).

ParseConfidence is **not stored** — it can be computed from SourceFragment + Content:

```sql
-- Fields with lowest parse confidence (most unparsed content)
SELECT cf.FieldName, c.Name, c.Year,
       CAST(SUM(LENGTH(fv.SourceFragment)) AS REAL) / LENGTH(cf.Content) AS confidence,
       COUNT(fv.ValueID) AS values_extracted,
       LENGTH(cf.Content) AS content_len
FROM FieldValues fv
JOIN CountryFields cf ON fv.FieldID = cf.FieldID
JOIN Countries c ON cf.CountryID = c.CountryID
WHERE fv.SourceFragment IS NOT NULL
GROUP BY cf.FieldID
HAVING confidence < 0.3
ORDER BY confidence ASC
LIMIT 50;
```

### Existing Tables — Untouched

```
Countries          -- 9,501 rows    (unchanged)
CountryCategories  -- 83,626 rows   (unchanged)
CountryFields      -- 1,061,522 rows (unchanged, Content stays as-is)
FieldNameMappings  -- 1,091 rows    (unchanged)
MasterCountries    -- 282 rows      (unchanged)
```

### Relationship

```
Countries (1) ──> (N) CountryCategories (1) ──> (N) CountryFields (1) ──> (N) FieldValues
                                                         │                        │
                                                     Content blob           Parsed atoms
                                                    (source of truth)      (derived index)
```

---

## Content Format Variations by Era

The `Content` column stores text blobs from 6 different parsing eras. The structured
parser must handle all variations.

### Records by Era

```
Era                         Records      Delimiter Style
─────────────────────────   ─────────    ──────────────────────────────
1990-1994 (text/early)         85,296    pipe-delimited ( | ) [v3.2]
1995-2001 (text/atsign)       165,655    pipe-delimited ( | ) [v3.2]
2002-2008 (HTML table)        202,591    pipe-delimited ( | ) [v3.2]
2009-2014 (HTML collapsible)  203,848    pipe-delimited ( | ) [v3.2]
2015-2020 (HTML modern)       222,084    pipe-delimited ( | )
2021-2025 (JSON)              182,048    pipe-delimited ( | ) [v3.2]
─────────────────────────   ─────────
TOTAL                       1,061,522
```

### Same Field Across Eras — "Life expectancy at birth"

```
[1990]  76 years male, 82 years female (1990)
[1995]  total population: 79.44 years | male: 76.6 years | female: 82.42 years (1995 est.)
[2002]  total population: 80.91 years | female: 84.25 years (2002 est.) | male: 77.73 years
[2010]  total population: 82.17 years | male: 78.87 years | female: 85.66 years ...
[2018]  total population: 85.5 years (2018 est.) | male: 82.2 years | female: 89 years
[2025]  total population: 85.2 years (2024 est.) | male: 82.3 years | female: 88.2 years
```

### Same Field Across Eras — "Area"

```
[1990]  (stored as separate fields: "Total area", "Land area", "Comparative area")
[1995]  total area: 377,835 sq km | land area: 374,744 sq km | comparative area: ...
[2002]  total: 377,835 sq km | note: ... | water: 3,091 sq km | land: 374,744 sq km
[2010]  total: 377,915 sq km | land: 364,485 sq km | water: 13,430 sq km ...
[2018]  total: 377,915 sq km | land: 364,485 sq km | water: 13,430 sq km | note: ...
[2025]  total : 377,915 sq km | land: 364,485 sq km | water: 13,430 sq km | note: ...
```

### Same Field Across Eras — "Exports"

```
[1990]  $270 billion (f.o.b., 1989); commodities--manufactures 97% ...
[1995]  $395.5 billion (f.o.b., 1994) commodities: manufactures 97% ...
[2002]  $383.8 billion f.o.b. (2002 est.)
[2010]  $735.8 billion (2010 est.) country comparison to the world: 5
[2018]  $688.9 billion (2017 est.) | $634.9 billion (2016 est.)
[2025]  $922.447 billion (2024 est.) $923.488 billion (2023 est.) ...
```

### Same Field Across Eras — "Electricity"

```
[1990]  191,000,000 kW capacity; 700,000 million kWh produced, 5,680 kWh per capita
[1995]  capacity: 205,140,000 kW production: 840 billion kWh consumption per capita: 6,262 kWh
[2025]  installed generating capacity: 361.617 million kW (2023 est.)
        consumption: 902.769 billion kWh (2023 est.)
```

---

## Parsing Strategy

### Phase 1 — Delimiter Normalization

Before extracting sub-fields, normalize the delimiter styles:

```
Input (2015-2020):  "total: 377,915 sq km | land: 364,485 sq km | water: 13,430 sq km"
Input (2002-2014):  "total: 377,915 sq km land: 364,485 sq km water: 13,430 sq km"
Input (2021-2025):  "total : 377,915 sq km land: 364,485 sq km water: 13,430 sq km"
                         ▼
Normalized:         [("total", "377,915 sq km"), ("land", "364,485 sq km"), ("water", "13,430 sq km")]
```

Strategy:
1. Split on ` | ` (pipe) if present (2015-2020 era)
2. Otherwise, split on known sub-field label patterns: `label:` followed by value
3. Handle `country comparison to the world: N` as a rank extraction, not a sub-field

### Phase 2 — Value Type Detection

For each sub-field value string, detect and extract:

```
"7,741,220 sq km"         -> NumericVal=7741220,    Units="sq km"
"83.5 years (2024 est.)"  -> NumericVal=83.5,       Units="years",  DateEst="2024 est."
"$922.447 billion"        -> NumericVal=922447000000, Units="USD"
"18.1%"                   -> NumericVal=18.1,        Units="%"
"male 7,701,196"          -> NumericVal=7701196,     SubField="male"
"Pashtun, Tajik, Hazara"  -> TextVal="Pashtun, Tajik, Hazara"
```

Type detection rules:
1. Strip `$` prefix → currency
2. Detect magnitude words: thousand (1e3), million (1e6), billion (1e9), trillion (1e12)
3. Strip commas from numbers
4. Detect unit suffixes: sq km, km, nm, m, years, %, kW, kWh, bbl/day, liters, metric tonnes
5. Extract `(YYYY est.)` date patterns
6. Extract `country comparison to the world: N` as Rank
7. Anything that doesn't parse as numeric → TextVal

### Phase 3 — Field-Specific Parsers

Some fields have unique structures that need dedicated parsers:

| Field Pattern | Sub-fields | Example |
|---|---|---|
| Area | total, land, water | `total: 377,915 sq km land: 364,485 sq km` |
| Population | total, male, female, growth_rate | `total: 338,016,259 male: 167,543,554` |
| Age structure | 0-14, 15-24, 25-54, 55-64, 65+ (percent, males, females) | `0-14 years: 18.1% (male 31,618,532/female 30,254,223)` |
| Life expectancy | total_population, male, female | `total population: 83.5 years male: 82.3 years` |
| GDP variants | annual values (multi-year), per_capita, growth_rate | `$25.676 trillion (2024 est.) $24.977 trillion (2023 est.)` |
| Exports/Imports | value, commodities, partners | `$922.447 billion (2024 est.)` |
| Military expenditures | multi-year % of GDP values | `3.2% of GDP (2024 est.) 3.1% of GDP (2023 est.)` |
| Budget | revenues, expenditures | `revenues: $4.877 trillion expenditures: $6.857 trillion` |
| Land use | agricultural, arable, permanent_crops, forest, other | `agricultural land: 46.1% arable land: 16.6%` |
| Electricity | capacity, consumption, exports, imports | `installed generating capacity: 361.617 million kW` |
| Exchange rates | currency, multi-year rates | `British pounds per US dollar: 0.782 (2024 est.)` |
| Geographic coordinates | latitude, longitude (degrees, minutes, hemisphere) | `38 00 N, 97 00 W` |
| Elevation | highest, lowest, mean | `highest point: Mount McKinley 6,190 m` |
| Birth/Death rate | single value + units | `10.75 births/1,000 population (2025 est.)` |
| Dependency ratios | total, youth, elderly, support_ratio | `total dependency ratio: 56 youth: 26.8` |
| Sex ratio | at_birth, 0-14, 15-64, 65+, total_population | `at birth: 1.05 male(s)/female 0-14 years: 1.06 male(s)/female` |
| Literacy | definition, total_population, male, female | `total population: 81.7% male: 88.3% female: 74.9%` |
| Maritime claims | territorial_sea, EEZ, contiguous_zone, continental_shelf | `territorial sea: 12 nm exclusive economic zone: 200 nm` |
| Natural gas | production, consumption, exports, imports, proven_reserves | `production: 1.072 trillion cubic meters` |
| Internet users | total, percent_of_population | `total: 312.8 million percent of population: 93%` |
| Telephones | total_subscriptions, subscriptions_per_100 | `total subscriptions: 87.987 million` |
| GDP composition | agriculture, industry, services | `agriculture: 0.9% industry: 17.3% services: 79.7%` |
| Household income | lowest_10pct, highest_10pct | `lowest 10%: 1.8% highest 10%: 30.4%` |
| School life expectancy | total, male, female | `total: 16 years male: 15 years female: 17 years` |
| Youth unemployment | total, male, female | `total: 9.4% male: 10.4% female: 8.3%` |
| CO2 emissions | total, from_coal, from_petroleum, from_natural_gas | `4.795 billion metric tonnes of CO2` |
| Water withdrawal | municipal, industrial, agricultural (or old: total, pcts, per_capita) | `municipal: 58.39 billion cubic meters` |
| Broadband | total, subscriptions_per_100 | `total: 131 million subscriptions per 100 inhabitants: 38` |
| Drinking water source | improved/unimproved x urban/rural/total | `improved: urban: 99.9% of population` |
| Sanitation facility access | improved/unimproved x urban/rural/total | (same structure as drinking water) |
| Waste and recycling | generated_annually, recycled_annually, percent_recycled | `municipal solid waste generated annually: 265.225 million tons` |
| Revenue from forest resources | value (% of GDP) | `0.04% of GDP (2018 est.)` |

### Phase 4 — Generic Fallback Parser

Fields without a dedicated parser use the generic `key: value` splitter:

1. Try splitting on ` | ` (pipe)
2. Try splitting on known `label: value` patterns
3. If neither works, store entire content as a single TextVal with SubField="value"

This ensures 100% of fields get at least one FieldValues row, even if it's just the
raw text. No data is lost.

---

## Priority Fields for Implementation

Ranked by analytical value and frequency across the archive:

### Tier 1 — High Impact (numeric, highly structured, appears in most countries/years)

| Field | Records | Sub-fields |
|---|---|---|
| Population | 9,333 | total, male, female, growth_rate |
| Area | 8,740 | total, land, water |
| Life expectancy at birth | 8,404 | total_population, male, female |
| Birth rate | 8,418 | value |
| Death rate | 8,414 | value |
| Infant mortality rate | 8,397 | total, male, female |
| Total fertility rate | 8,407 | value |
| GDP / Real GDP (PPP) | ~8,000 | annual values |
| Military expenditures | ~7,500 | multi-year % of GDP |
| Exports | 8,376 | value, commodities, partners |
| Imports | 8,379 | value, commodities, partners |

### Tier 2 — Medium Impact (structured, good coverage)

| Field | Sub-fields |
|---|---|
| Age structure | age brackets with percent/male/female |
| Land use | agricultural, arable, forest, other |
| Electricity | capacity, consumption, exports, imports |
| Budget | revenues, expenditures |
| Coastline | value |
| Elevation | highest, lowest, mean |
| Dependency ratios | total, youth, elderly |
| Urbanization | urban_population, rate_of_urbanization |
| Unemployment rate | multi-year values |
| Inflation rate | multi-year values |

### Tier 3 — Lower Priority (text-heavy, less numeric)

| Field | Notes |
|---|---|
| Climate | mostly free text |
| Terrain | mostly free text |
| Natural resources | comma-separated list |
| Ethnic groups | percentages + names |
| Languages | percentages + names |
| Religions | percentages + names |
| Administrative divisions | count + list |

---

## Comparison with iancoleman/cia_world_factbook_api

| | This Project | iancoleman |
|---|---|---|
| **Year coverage** | 1990-2025 (36 years) | 2007-present |
| **Entities** | 281 | ~259 |
| **Total records** | 1,061,522 | N/A (weekly snapshots) |
| **Granularity** | 1 snapshot/year | ~52 snapshots/year |
| **Source parsing** | Python / BeautifulSoup | Go / goquery |
| **Field canonicalization** | 1,090 variants -> 416 canonical | None |
| **Type conversion** | Planned (this project) | Already implemented |
| **Output format** | SQLite + webapp | JSON files |

Key takeaway: iancoleman's Go parser already does the type conversion we need (numbers,
units, GPS, lists, percentages). Their `string_conversions.go` is a useful reference for
parsing patterns, but we implement independently in Python against our broader dataset.

---

## Implementation Plan

### Script: `etl/structured_parsing/parse_field_values.py`

```
Input:  factbook.db (CountryFields.Content blobs)
Output: factbook.db (new FieldValues table, populated)
```

### Steps

1. **Create FieldValues table** in factbook.db (additive, no existing tables modified)
2. **Build field-specific parsers** for Tier 1 fields (~11 parsers)
3. **Build generic fallback parser** for everything else
4. **Run against all 1,061,522 records** — populate FieldValues
5. **Validate** — spot-check parsed values against raw Content
6. **Index** — create indexes for fast sub-field queries

### Estimated Output

```
1,061,522 CountryFields records
    x ~3-5 sub-values average per field
    = ~3-5 million FieldValues rows (estimated)
```

### Dependencies

- Python 3.x (existing)
- sqlite3 (stdlib)
- re (stdlib)
- No new external packages required

---

## Future Uses

Once FieldValues is populated:

- **Webapp analytics**: Chart any sub-field across years/countries
- **StarDict dictionary**: Export structured entries for KOReader/GoldenDict
- **Book reader**: Display structured sub-fields instead of text walls
- **Rankings**: Rank countries by any numeric sub-field
- **Correlations**: Cross-field analysis (GDP vs. life expectancy, etc.)
- **API**: Return typed JSON instead of text blobs
- **CSV/Excel export**: Structured columns instead of text dump

---

## Changelog

### v3.2 (2026-02-28)

Driven by community feedback on [Issue #10](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/issues/10).

**SourceFragment column** — Every FieldValues row now includes the exact substring of
`CountryFields.Content` that the parser matched to produce that value. Enables debugging
and automated parse quality checks (e.g. detect when a large Content blob produces only
one sub-value).

**18 new dedicated parsers** replacing generic fallback for under-parsed fields.
Systematic audit found fields with structured `label: value` content where the generic
parser's regex (requires labels starting with a letter) was silently dropping sub-values
like `0-14 years:`, `lowest 10%:`, or unlabeled totals.

| Parser | Records | Sub-values | What was being lost |
|---|---|---|---|
| Sex ratio | 7,000+ | at_birth, 0-14, 15-64, 65+, total_population | Was: 1 (at_birth only). Now: 5 per country |
| Literacy | 7,700+ | definition, total_population, male, female | Was: total_population only. Now: 3-4 |
| Maritime claims | 8,600+ | territorial_sea, EEZ, contiguous_zone, continental_shelf | Was: territorial_sea only. Now: 2-4 |
| Natural gas | 2,000+ | production, consumption, exports, imports, proven_reserves | Was: production only. Now: 5 |
| Internet users | varies | total, percent_of_population | Now extracts both consistently |
| Telephones (fixed + mobile) | varies | total_subscriptions, subscriptions_per_100 | Now extracts per-100 density |
| Debt - external | varies | multi-year dollar values | Now uses parse_multi_year_dollar |
| GDP composition by sector | 6,931 | agriculture, industry, services | Was: 1 (generic). Now: 3 |
| Household income | 5,994 | lowest_10pct, highest_10pct | Was: 1. Now: 2 |
| School life expectancy | 3,217 | total, male, female | Was: 1-2. Now: 3 |
| Youth unemployment | 2,982 | total, male, female | Was: 1-2. Now: 3 |
| Carbon dioxide emissions | 2,804 | total, from_coal, from_petroleum, from_natural_gas | Was: 1. Now: 4 |
| Total water withdrawal | 2,268 | municipal, industrial, agricultural (+ old format) | Was: 1. Now: 3-5 |
| Broadband subscriptions | 1,685 | total, subscriptions_per_100 | Was: 1. Now: 2 |
| Drinking water source | 3,100 | improved/unimproved x urban/rural/total | Was: 3. Now: 6 |
| Sanitation facility access | 3,198 | improved/unimproved x urban/rural/total | Was: 3. Now: 6 |
| Waste and recycling | 1,085 | generated, recycled, percent_recycled | Was: 1. Now: 2-3 |
| Revenue from forest resources | 820 | value (% of GDP) | Was: generic. Now: dedicated |

**Registered parsers**: 55 canonical fields (up from 34 in v3.0).

**Content delimiter migration** — `CountryFields.Content` now uses pipe (`|`) delimiters
between sub-fields across all eras, replacing the previous space-joining that made sub-field
boundaries ambiguous. Community feedback ([Issue #10](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/issues/10))
correctly identified that collapsing original newlines to spaces loses structural information.

Changes by era:
- **2000 (classic HTML)**: `html_to_pipe_text()` replaces `<br>`, `</p><p>` etc. with ` | `
- **2001-2008 (table HTML)**: Same `html_to_pipe_text()` applied to content cells
- **2009-2014 (collapsible HTML)**: `' '.join(content_parts)` → `' | '.join(content_parts)`
- **2015-2020 (modern HTML)**: Already used `' | '.join()` — no change needed
- **2021-2025 (JSON/HTML)**: `strip_html()` rewritten to insert ` | ` at block element boundaries
- **1993-1999 (indented text)**: `' '.join(current_value_parts)` → `' | '.join(...)`
- **1990, 2001 (inline text)**: No change — continuation lines are text wrapping, not sub-fields

No parser or webapp changes required. The generic fallback parser already splits on `' | '`,
and all 55 dedicated parsers use field-specific regex that works regardless of delimiter.
The 2015-2020 era already proved pipe compatibility across the entire stack.

### v3.1 (2026-02-28)

StarDict dictionaries release (72 offline dictionaries for KOReader/GoldenDict).
See [release notes](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/releases/tag/v3.1).

### v3.2 (2026-02-28)

- **Content delimiter migration**: Replaced space-joining with pipe (`|`) delimiters
  across all eras (Gutenberg text, HTML, JSON) for unambiguous sub-field boundaries.
  Files changed: `build_archive.py` (`html_to_pipe_text()`), `load_gutenberg_years.py`
  (pipe-join in `extract_indented_fields`/`extract_mixed_fields`),
  `reload_json_years.py` (pipe-aware `strip_html()`).
- **SourceFragment column**: Every FieldValues row now carries the exact text slice
  that produced the value, enabling parse confidence computation.
- **18 new dedicated parsers**: sex_ratio, literacy, maritime_claims, natural_gas,
  internet_users, telephones, gdp_composition, household_income, school_life_expectancy,
  youth_unemployment, co2_emissions, water_withdrawal, broadband, water_sanitation,
  waste_recycling, forest_revenue — bringing total to 55 registered parsers.
- **1996 data repair**: Replaced truncated Gutenberg data for 7 countries (Venezuela,
  Armenia, Greece, Luxembourg, Malta, Monaco, Tuvalu) with CIA's original `wfb-96.txt.gz`.
- **Full database rebuild**: 1,071,603 fields decomposed into 1,610,973 sub-values
  across 2,386 distinct sub-fields. Country-year records: 9,536. Categories: 83,682.

### v3.0 (2026-02-26)

Initial release. Added FieldValues table decomposing 1,061,522 CountryFields entries
into 1,423,506 individually queryable sub-values across 34 dedicated parsers.
