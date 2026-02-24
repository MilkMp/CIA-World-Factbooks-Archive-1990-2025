# Lookup Tables

Standalone crosswalk and mapping files extracted from the ETL pipeline that built this archive.

The CIA World Factbook uses FIPS 10-4 country codes internally, which differ from the ISO 3166-1 codes used by most other systems. The Factbook also changed field names across its 36 editions (1990-2025) — a field called "Ethnic divisions" in 1993 became "Ethnic groups" by 2000. These lookup tables capture all of those translations so you don't have to reverse-engineer them yourself.

## Files

| File | Description |
|------|-------------|
| `fips_to_iso2.csv` | FIPS 10-4 to ISO 3166-1 Alpha-2 crosswalk (277 codes). Source: NGA Geopolitical Entities and Codes via [mysociety/gaze](https://github.com/mysociety/gaze). |
| `fips_code_merges.csv` | 7 historical FIPS codes that were retired and merged into modern ones (e.g. TC/Trucial States became AE/United Arab Emirates). |
| `country_name_fixes.csv` | 27 country names corrected from HTML parsing artifacts in the 2002-2020 editions. |
| `country_name_updates.csv` | 8 countries renamed to their current official names (e.g. Swaziland to Eswatini, Czech Republic to Czechia). |
| `entity_type_overrides.csv` | 45 manual entity type classifications for non-sovereign entries (territories, disputed areas, oceans, dissolved states). |
| `field_name_renames.csv` | 162 field name changes the CIA made across editions, mapped to their modern canonical equivalents. |
| `field_consolidation.csv` | 50 sub-field variants (e.g. "Crude oil - production", "Oil - exports") consolidated into parent fields (e.g. "Petroleum"). |
| `_generate.py` | Script to regenerate all CSVs from the ETL source scripts. |

## Why this exists

The raw Factbook archive (`data/fields/`) is preserved exactly as published by the CIA — nothing is modified. These lookup tables are the translation layer we built on top of that raw data to power the web dashboard at [worldfactbookarchive.org](https://worldfactbookarchive.org). They let us query across all 36 years consistently without altering any original content.

173 out of 277 FIPS codes differ from their ISO equivalents. Without this crosswalk, you can't join Factbook data against any standard country dataset. The field name mappings let you query "Population" across all 36 years even though the CIA used different labels in different eras.

These are provided separately so they can be used independently of the full database — if you're building your own tools on top of the Factbook data, these save you from having to solve the same normalization problems.

## Regenerating

```
python data/lookup_tables/_generate.py
```

This reads the mapping dictionaries from `etl/build_field_mappings.py`, `etl/classify_entities.py`, and `scripts/archive/cleanup_master_countries.py` and writes fresh CSVs.
