# Release v3.5 -- Accent Fix and StarDict Per-Field Rebuild

**Date:** 2026-03-17

Two changes in this release: a data quality fix for accent/diacritic handling in the 2021-2025 JSON-era data, and a complete rebuild of the StarDict dictionaries in per-field format.

---

## Change 1: JSON-Era Accent Fix (6,717 fields + 229 sub-values)

### Problem

The JSON ETL parser (`reload_json_years.py`) used `re.sub(r'&[a-zA-Z]+;', ' ', s)` to remove what it assumed were leftover HTML tags. This regex also matched HTML entities like `&aacute;`, `&iacute;`, `&atilde;`, replacing accented characters with spaces.

**Affected years:** 2021-2025 (all JSON-sourced data)

**Examples of corruption:**
| Original | Corrupted | Scope |
|----------|-----------|-------|
| Bogota | Bogot  | Colombia capital (5 fields) |
| Brasilia | Bras lia | Brazil capital (15 fields) |
| Sao Paulo | S o Paulo | Brazil cities (8 fields) |
| Charge d'Affaires | Charg d'Affaires | 204 diplomatic fields |
| Nacoes | Na es | Portuguese text (14 fields) |
| BRASILIA | BRAS LIA | Brazil urban areas (15 fields) |

### Fix

Replaced `re.sub(r'&[a-zA-Z]+;', ' ', s)` with `html.unescape(s)` in `strip_html()`, which properly decodes HTML entities to their Unicode characters. Re-parsed all 2021-2025 data from the factbook-json-cache git repo using year-specific commits (one commit per year-end snapshot).

| Year | Fields Updated |
|------|---------------|
| 2021 | 876 |
| 2022 | 1,328 |
| 2023 | 1,757 |
| 2024 | 1,507 |
| 2025 | 1,249 |
| **Total** | **6,717 CountryFields + 229 FieldValues** |

### Verification

- 0 remaining accent-stripped patterns across all 2021-2025 data
- 0 U+FFFD replacement characters in the entire database (all years)
- Field counts unchanged (no data loss)

---

## Change 2: StarDict Per-Field Rebuild (2.1M entries)

### Problem

The v3.2 StarDict dictionaries used a per-country format (~260 entries per year), where each country was a single dictionary entry containing all its fields. The KOReader community's existing factbook dictionary (2014) uses a per-field format, where each (country, field) pair is its own entry. The per-field format is better for dictionary apps because users can look up specific facts directly.

### Fix

Rebuilt all dictionaries in per-field format. Each entry has a headword like `Afghanistan - Population` with synonyms `AF - Population` (ISO) and `FIPS - Population` (where non-colliding).

| Metric | v3.2 (per-country) | v3.5 (per-field) |
|--------|-------------------|-----------------|
| Entries per year | ~260 | 15,000-38,000 |
| Total entries | ~18,700 | 2,095,643 |
| Total size | ~97 MB | ~253 MB |
| Tarball size | ~97 MB | ~130 MB |

### Validation

16/16 tests pass:
- File presence (288 files)
- No empty entries (2,095,643 scanned)
- DB count match (36 years)
- Category labels, ISO synonyms, HTML balance
- Ground truth (50 data points)
- Historical entity names (Soviet Union, Yugoslavia, GDR)
- Encoding quality (0 bad chars / 380M bytes)
- Round-trip read via pyglossary

See [VALIDATION_REPORT.md](../etl/stardict/VALIDATION_REPORT.md) for full details.

---

## Database Statistics

| Metric | v3.4 | v3.5 | Change |
|--------|------|------|--------|
| Database size | ~656 MB | ~662 MB | +6 MB |
| Data fields | 1,071,603 | 1,071,603 | unchanged |
| Structured sub-values | 1,775,588 | 1,775,588 | unchanged |
| U+FFFD characters | 0 | 0 | unchanged |
| Accent-stripped fields | 6,717 | 0 | fixed |

---

## Release Assets

### v3.5 (Database)
- `factbook.db` -- Updated SQLite database (~662 MB)

### v3.5-stardict (Dictionaries)
- 36 `.tar.gz` tarballs (one per year, general edition)
- Each tarball contains a StarDict directory with `.ifo`, `.idx`, `.dict.dz`, `.syn` files

---

## Version History

| Version | Date | Summary |
|---------|------|---------|
| v3.5 | 2026-03-17 | Accent fix (6,717 fields) + StarDict per-field rebuild (2.1M entries) |
| v3.4.2 | 2026-03-12 | Documentation cleanup and DOI update |
| v3.4.1 | 2026-03-06 | Screenshots refresh |
| v3.4 | 2026-03-05 | Pipe-after-colon parser fix (+164,494 sub-values) |
| v3.3 | 2026-03-05 | IsComputed flag and case-sensitive field mappings |
| v3.2 | 2026-03-01 | StarDict dictionaries (per-country format) and encoding repair |
