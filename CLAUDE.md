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

## Data Quality Rules

- **No U+FFFD** replacement characters anywhere in the database
- **HTML entities must be decoded**, not stripped (use `html.unescape()`, never regex)
- **Accented characters must be preserved** (Bogota, Brasilia, Charge d'Affaires, etc.)
- The `strip_html()` function in `etl/reload_json_years.py` is the JSON-era parser -- any changes there affect all 2021-2025 data
- Run `etl/validate_integrity.py` after any bulk data changes

## Code Style

- Python: `C:/Users/milan/anaconda3/python.exe`
- No emojis in code, docs, or UI
- UI theme: "Dark Intelligence" -- use classes from `intel-theme.css`, never inline styles
- Filter inputs: always use example placeholder text (e.g. `placeholder="e.g. Afghanistan, China"`)

## Key File Locations

| File | Purpose |
|------|---------|
| `etl/reload_json_years.py` | JSON-era parser (2021-2025), has `strip_html()` |
| `etl/sync_sqlite_to_sqlserver.py` | Sync SQLite -> SQL Server |
| `etl/stardict/build_stardict.py` | Build StarDict dictionaries |
| `etl/stardict/validate_stardict.py` | Validate StarDict dictionaries (16 tests) |
| `etl/structured_parsing/parse_field_values.py` | Parse raw text into FieldValues sub-values |
| `etl/fix_encoding_and_duplicates.py` | Fix U+FFFD encoding corruption |
| `CIA_Factbook_Tars/` | Mirror of StarDict scripts for the tarballs repo |
| `data/factbook.db` | SQLite database (source of truth) |
| `data/stardict/` | Built StarDict dictionaries |
| `data/stardict-tarballs/` | Compressed tarballs for release |
