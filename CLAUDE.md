# CIA World Factbook Archive -- Development Guidelines

## Two Databases, One Source of Truth

This project maintains **two copies** of the same data:

| Database | Location | Purpose |
|----------|----------|---------|
| **SQLite** | `data/factbook.db` (~662 MB) | Production (webapp on Fly.io), distribution (GitHub releases), StarDict builds |
| **SQL Server** | `localhost/CIA_WorldFactbook` | Local dev/ETL, original import source |

### The Rule

**SQLite is the source of truth.** All data fixes go into `factbook.db` first. After any data change to SQLite, **always** sync to SQL Server:

```bash
python etl/sync_sqlite_to_sqlserver.py              # sync all years
python etl/sync_sqlite_to_sqlserver.py --years 2025  # sync one year
python etl/sync_sqlite_to_sqlserver.py --dry-run     # preview first
```

Never fix SQL Server without also fixing SQLite. Never leave them out of sync.

## Project Context

- The CIA World Factbook was **discontinued on February 4, 2026**
- This archive preserves every edition published since 1990 (36 years, 281 entities)
- **Webapp**: FastAPI + Jinja2 + SQLite, deployed on Fly.io (app: `cia-factbook-archive`, region: `iad`)
- **Live URL**: https://worldfactbookarchive.org/ (Cloudflare DNS + proxy)
- **GitHub Pages**: https://milkmp.github.io/CIA-World-Factbooks-Archive-1990-2025/
- **Concept DOI**: 10.5281/zenodo.18884612 (always resolves to latest -- use this everywhere, never version-specific DOIs)

## Database Schema

6 core tables: `MasterCountries`, `Countries`, `CountryCategories`, `CountryFields`, `FieldNameMappings`, `FieldValues`.

- `FieldValues` exists in SQLite only (not in SQL Server)
- `CountryFieldsFTS` (FTS5 full-text index) exists in SQLite only
- Both databases share identical `MasterCountries`, `Countries`, `CountryCategories`, `CountryFields`, `FieldNameMappings`

## Release Process

1. Fix/update data in `factbook.db`
2. Run `python etl/sync_sqlite_to_sqlserver.py` to sync SQL Server
3. Rebuild any affected artifacts (StarDict dicts, etc.)
4. Update version references in: `README.md`, `README.txt`, `docs/index.html`, `wiki/Home.md`, `wiki/Database-Schema.md`, `wiki/Known-Quirks.md`, `etl/stardict/README.md`
5. Update DB size (~XXX MB) in all the above files if it changed
6. Commit, push, create GitHub release
7. Check Zenodo picked up the release (concept DOI: 10.5281/zenodo.18884612)

## Webapp Deployment

- **ALWAYS** test locally before deploying: `python start.py` then check in browser
- **ALWAYS** use `bash deploy.sh` to deploy (it stashes uncommitted work)
- **NEVER** run `fly deploy` directly -- it builds from local filesystem, not git
- After deploying data changes, clear the cache: `/admin/clear-cache?key=KEY`

## StarDict Dictionaries

- Format: **per-field** (one entry per country+field pair, e.g. "Afghanistan - Population")
- Edition: **general only** for releases (structured is built but not shipped)
- Build: `python etl/stardict/build_stardict.py`
- Validate: `python etl/stardict/validate_stardict.py` (16 tests, all must pass)
- Output: `data/stardict/` (dictionaries), `data/stardict-tarballs/` (release archives)
- After any data fix, rebuild affected dictionaries before releasing

## Factbook Format Variants by Year

The CIA changed formats constantly. Each era requires its own parser:

| Years | Format | Key Pattern |
|-------|--------|-------------|
| 1990 | `old` | `Country: Name` / `- Section` / `Field: value` |
| 1991 | `tagged` | `_@_Name` / `_*_Section` / `_#_Field: value` |
| 1992 | `colon` | `:Country Section` / Field on next line |
| 1993-1994 | `asterisk` | `*Name, Section` / `Field:\n  value` |
| 1995-2000 | `atsign` | `@Name:Section` / `Field: value` (inline) |
| 2001 | `equals` | `@Name` / `Name Section` / `Field: value` |
| 2002-2020 | HTML | 5 different HTML layouts across the era |
| 2021-2025 | JSON | From factbook/cache.factbook.json git repo |

**Field name convention:**
- Top-level field names start with a capital letter: `Population`, `Area`, `Life expectancy at birth`
- Sub-field names are lowercase: `total population`, `male`, `female`, `land area`
- This capitalization rule is how parsers distinguish parent fields from sub-fields in the 1993-1994 asterisk format

**Pipe delimiters:** `CountryFields.Content` uses pipe (`|`) delimiters for sub-field boundaries across all eras. This is a parsing convention, not CIA original formatting.

## Data Quality Rules

- **No U+FFFD** replacement characters anywhere in the database
- **HTML entities must be decoded**, not stripped (use `html.unescape()`, never regex to strip entities)
- **Accented characters must be preserved** (Bogota, Brasilia, Charge d'Affaires, etc.)
- The `strip_html()` function in `etl/reload_json_years.py` is the JSON-era parser -- any changes there affect all 2021-2025 data
- Run `etl/validate_integrity.py` after any bulk data changes

## Known Data Quirks (Fixed)

These issues have been fixed but are documented here to prevent regressions:

- **Serbia 2008 duplicate**: CIA changed Serbia's FIPS code from `rb` to `ri` in 2008, leaving two Country rows. Merged in `etl/fix_encoding_and_duplicates.py`.
- **Yugoslavia/GDR NULL MasterCountryIDs**: Dissolved states (Yugoslavia 1990-1991, Yugoslavia 2001, GDR 1990) had NULL MasterCountryID, causing them to be excluded from StarDict dictionaries. Fixed: Yugoslavia -> 283, GDR -> 99.
- **ISO/FIPS synonym collisions**: 98 cases where one code system's code for Country A is the other system's code for Country B. Rule: ISO always wins. See `etl/stardict/README.md` for details.
- **Shared ISO codes**: 6 code groups where territories share a sovereign's ISO code (AU, GB, RE, UM, PF, PS). Rule: sovereign nation owns the code.

## Git Checkout Gotcha

When checking out historical commits from a git repo (e.g., factbook-json-cache for year-end snapshots), **always find all commits from master BEFORE checking any out**:

```python
# CORRECT: find all commits first, then checkout
for year in years:
    commits[year] = git_log('master', f'--before={cutoff}')
for year in years:
    checkout(commits[year])
    # process...

# WRONG: find and checkout one at a time
# After detaching HEAD, git log only shows history reachable from that commit
```

## Beyond the Factbook -- OSINT Data Collections

This repo also archives several related CIA open-source intelligence datasets:

### Atlas (Interactive Globe)
- Full-screen Mapbox GL JS globe at `/analysis/atlas` on the webapp
- 20+ toggleable layers: military bases, nuclear facilities, missile sites, COCOM regions, disputed territories, submarine cables, shipping lanes, EEZ zones, night lights
- Missile facilities from ACA, FAS, CSIS Missile Threat OSINT data (~200+ sites)
- 7 facility types: silo fields, submarine bases, mobile garrisons, air bases, test ranges, production, storage
- Data: `data/missile_facilities_osint.csv`, loaded by `scripts/populate_missiles.py` and `scripts/populate_missile_sites.py` (in webapp repo)
- Webapp router: `webapp/routers/atlas.py`, template: `webapp/templates/analysis/atlas.html`

### World Leaders (Chiefs of State)
- Parsed from CIA's "Chiefs of State and Cabinet Members" directory
- 5,696 records across 193 countries and 6 years (2022-2026 + historical PDFs 2003-2019)
- 12 controlled subfields (executive head of state, defense, foreign affairs, etc.), 3-tier role classification
- Data: `data/world_leaders_model.json`, `data/world_leaders_structured.sqlite`
- Build: `scripts/build_world_leaders_model.py`
- Scraper: `CIA_World_Leaders/scrape_world_leaders.py`
- Webapp: 6 pages (overview, browse, governance, concentration, security, map)
- Docs: `docs/WORLD_LEADERS_HANDOFF.md`, `docs/WORLD_LEADERS_RESEARCH_PROJECT.md`

### CIA Maps Archive
- ~300+ maps by country (administrative, physiography, transportation variants)
- Scraped from cia.gov public domain maps
- Scraper: `CIA_Maps/scrape_cia_maps.py`
- Metadata: `CIA_Maps/maps_metadata.json`
- Webapp gallery: `/maps` route with pagination and type filters

### CIA Studies in Intelligence
- Parsed corpus of CIA's *Studies in Intelligence* journal
- Local-only analytics dashboard (not deployed to Fly.io)
- Data: `data/csi_studies_index.sqlite`, entity graph artifacts
- Corpus: `CIA_Studies_Intelligence_clean/` (text files by year, 1992-2002+)
- Server: `scripts/csi_reader_server.py` (local `http.server`)
- Handoff doc: `docs/CLAUDE_HANDOFF.md`

## Version History

| Version | Date | Key Changes |
|---------|------|-------------|
| v3.5 | 2026-03-17 | Accent fix (6,717 fields), StarDict per-field rebuild (2.1M entries), sync script |
| v3.4.2 | 2026-03-12 | Documentation cleanup, DOI update |
| v3.4.1 | 2026-03-06 | Screenshots refresh (49 PNGs + 9 GIFs) |
| v3.4 | 2026-03-05 | Pipe-after-colon parser fix, +164,494 sub-values (1,775,588 total) |
| v3.3 | 2026-03-05 | IsComputed flag, case-sensitive field mappings, 0 unmapped fields |
| v3.2 | 2026-03-01 | StarDict dictionaries (per-country), encoding repair (117 U+FFFD -> 0), single DB consolidation |
| v3.1 | 2026-02-28 | Pipe delimiters, SourceFragment, 18 new parsers, 1996 data repair |
| v3.0 | 2026-02-26 | Structured field parsing (FieldValues table), 55 parsers |

82 commits total. Initial release was the raw SQL Server database with ETL scripts. The project evolved through adding a webapp, migrating to SQLite, building structured parsing, adding StarDict exports, and accumulating OSINT data collections.

## Code Style

- Python: `C:/Users/milan/anaconda3/python.exe`
- No emojis in code, docs, or UI
- UI theme: "Dark Intelligence" -- use classes from `intel-theme.css`, never inline styles
- Filter inputs: always use example placeholder text (e.g. `placeholder="e.g. Afghanistan, China"`)

## Key File Locations

### ETL & Data Pipeline
| File | Purpose |
|------|---------|
| `etl/reload_json_years.py` | JSON-era parser (2021-2025), has `strip_html()` |
| `etl/load_gutenberg_years.py` | Plain-text parser (1990-2001), 4 format variants |
| `etl/build_archive.py` | HTML parser (2000-2020), 5 layout variants |
| `etl/build_field_mappings.py` | Maps 1,132 field name variants to 416 canonical names |
| `etl/structured_parsing/parse_field_values.py` | Parse raw text into 1,775,588 FieldValues sub-values |
| `etl/structured_parsing/export_field_values_to_sqlite.py` | Export to factbook.db (use `--webapp` for FTS5) |
| `etl/fix_encoding_and_duplicates.py` | Fix U+FFFD encoding corruption |
| `etl/sync_sqlite_to_sqlserver.py` | Sync SQLite -> SQL Server |
| `etl/validate_integrity.py` | 10-check validation suite |

### StarDict
| File | Purpose |
|------|---------|
| `etl/stardict/build_stardict.py` | Build StarDict dictionaries |
| `etl/stardict/validate_stardict.py` | 16-test validation suite |
| `etl/stardict/README.md` | Full design doc (format, synonyms, validation) |
| `CIA_Factbook_Tars/` | Mirror of StarDict scripts -- **must stay in sync** with `etl/stardict/` |

### Data Files
| File | Purpose |
|------|---------|
| `data/factbook.db` | SQLite database (source of truth) |
| `data/factbook_v3.2_backup.db` | Pre-v3.5 backup |
| `data/missile_facilities_osint.csv` | OSINT missile site locations |
| `data/world_leaders_model.json` | Structured world leaders data |
| `data/world_leaders_structured.sqlite` | World leaders SQLite DB |
| `data/stardict/` | Built StarDict dictionaries |
| `data/stardict-tarballs/` | Compressed tarballs for release |

### Documentation
| File | Purpose |
|------|---------|
| `docs/METHODOLOGY.md` | Full parsing methodology |
| `docs/ETL_PIPELINE.md` | ETL pipeline documentation |
| `docs/RELEASE_v3.*.md` | Release notes for each version |
| `docs/WORLD_LEADERS_HANDOFF.md` | World leaders implementation doc |
| `docs/CLAUDE_HANDOFF.md` | CSI Studies Intelligence handoff |
| `docs/CIA_Factbook_Archive_Executive_Summary.pdf` | 3-page executive summary |
