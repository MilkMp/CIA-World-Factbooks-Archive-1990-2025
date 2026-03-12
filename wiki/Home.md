# CIA World Factbooks Archive 1990-2025

A complete, structured archive of the CIA World Factbook spanning **36 years** (1990-2025), covering **281 entities** with over **1 million data fields** in a normalized SQLite database.

The CIA World Factbook was discontinued on **February 4, 2026**. This archive preserves every edition published since 1990 in a structured, queryable format.

An interactive web application for exploring this archive is available at **[worldfactbookarchive.org](https://worldfactbookarchive.org/)**. The website queries the database to let users browse countries, compare fields across years, view rankings, track historical trends, and perform full-text search across all 36 editions.

---

## At a Glance

| Metric | Value |
|--------|-------|
| **Years covered** | 1990-2025 (36 editions) |
| **Entities** | 281 (190 sovereign states, 67 territories, 6 disputed, and more) |
| **Country-year records** | 9,536 |
| **Data fields** | 1,071,601 |
| **Structured sub-values** | 1,775,588 (parsed from raw text) |
| **Field name variants** | 1,132 mapped to 416 canonical names |
| **Database size** | ~656 MB (SQLite with FTS5 index) |
| **License** | MIT (code) / Public Domain (data) |
| **DOI** | [10.5281/zenodo.18884612](https://doi.org/10.5281/zenodo.18884612) |

---

## Wiki Pages

- **[Database Schema](Database-Schema)** -- Tables, columns, relationships, and how to query the SQLite file
- **[Data Sources & Formats](Data-Sources-and-Formats)** -- Where the data came from and the 7+ format variants across 36 years
- **[Field Name Mappings](Field-Name-Mappings)** -- How 1,132 field name variants normalize to 416 canonical names
- **[ETL Pipeline](ETL-Pipeline)** -- How raw Factbook editions were parsed and loaded
- **[Entity Coverage](Entity-Coverage)** -- 281 entities, dissolved states, entity types, and year-by-year coverage
- **[Structured Sub-Values (FieldValues)](Structured-Sub-Values)** -- Machine-readable numeric values parsed from raw text blobs
- **[Query Examples](Query-Examples)** -- Ready-to-use SQL queries for common analysis tasks
- **[Known Quirks & Limitations](Known-Quirks)** -- Format edge cases, data gaps, and encoding issues

---

## Data Integrity

No Factbook content is added or altered. The parsing process structures the CIA's raw text into queryable fields -- removing formatting artifacts, sectioning headers, and deduplicating noise lines -- but the actual data values are exactly as the CIA published them.

The only additions are reference lookup tables (FIPS-to-ISO code mappings, entity classifications, COCOM regional assignments) that sit alongside the original data, not inside it. In the FieldValues table, a small number of rows are derived by computation (e.g. total life expectancy averaged from male/female in pre-1995 data); these are flagged with `IsComputed = 1`.

---

## Citation

> Milkovich, M. (2026). *CIA World Factbooks Archive 1990-2025* [Dataset]. Zenodo. https://doi.org/10.5281/zenodo.18884612
