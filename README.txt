CIA WORLD FACTBOOK ARCHIVE
==========================
36 years of data (1990-2025) — 281 entities, 1,071,603 fields
1,610,973 structured sub-values parsed from raw text (2,386 sub-fields)
Live: https://worldfactbookarchive.org

DATABASE SCHEMA:
  MasterCountries   -> MasterCountryID, CanonicalCode (FIPS), ISOAlpha2, CanonicalName, EntityType
  Countries         -> Year, Code, Name, Source, MasterCountryID (FK)
  CountryCategories -> CountryID, CategoryTitle
  CountryFields     -> CategoryID, CountryID, FieldName, Content
  FieldNameMappings -> RawFieldName, CanonicalFieldName (maps 1,090 variants to 414 canonical names)
  FieldValues       -> FieldID, SubField, NumericVal, Units, TextVal, DateEst, SourceFragment

  MasterCountries centralizes country identity across all 36 years.
  CanonicalCode = original FIPS 10-4 code (preserved for reference)
  ISOAlpha2     = ISO 3166-1 Alpha-2 code (international standard)
  Source: NGA GEC crosswalk via github.com/mysociety/gaze

KEY QUERY — Snapshot of all factbook content with country metadata:

  SELECT mc.MasterCountryID, mc.CanonicalCode, mc.CanonicalName,
         mc.ISOAlpha2, mc.EntityType,
         cf.FieldName, cf.Content
  FROM MasterCountries mc
  JOIN CountryFields cf ON mc.MasterCountryID = cf.CountryID

  This joins the master country table to all 1,071,603 field entries,
  giving you every piece of data in the archive with its country context.

DATABASES:
  SQL Server:  CIA_WorldFactbook on localhost (Windows Auth, ODBC Driver 18)
  SQLite:      data/factbook.db (~636 MB, all tables + FTS5 + ISOCountryCodes)

  factbook.db is a self-contained database used by the webapp and for distribution.
  SQL Server is the canonical source for ETL.
  To rebuild: python etl/structured_parsing/export_field_values_to_sqlite.py --webapp

PROJECT STRUCTURE:
  webapp/          Deployable FastAPI app (Jinja2 templates, SQLite backend)
  data/            factbook.db (SQLite database)
  etl/             ETL & build scripts
  scripts/         Validation & utility scripts
  queries/         SQL reference files
  samples/         Parser test samples (HTML + text)
  notebooks/       Jupyter notebooks

DEPLOYMENT (Fly.io):
  Dockerfile       Container definition
  fly.toml         Fly.io config (region: iad, auto-suspend)
  start.py         First-boot DB seeder + uvicorn launcher
  requirements.txt Python dependencies
  .dockerignore    Build exclusions

  Deploy: flyctl deploy
  Logs:   flyctl logs

ETL SCRIPTS (in etl/, run in order):
  Step 1: build_archive.py         Downloads & parses 2000-2020 HTML
  Step 2: load_gutenberg_years.py  Parses 1990-2001 text from Project Gutenberg
  Step 3: reload_json_years.py     Loads 2021-2025 JSON from factbook GitHub repo
  Step 4: classify_entities.py     Auto-classifies entities (sovereign/territory/etc.)
  Step 5: build_field_mappings.py  Maps 1,090 field name variants to 414 canonical names
  Step 6: export_to_sqlite.py      Exports SQL Server to SQLite
  Step 7: structured_parsing/parse_field_values.py  Parses text blobs into typed sub-values
  Step 8: structured_parsing/export_field_values_to_sqlite.py  Exports to SQLite

VALIDATION (in scripts/):
  validate_integrity.py            Data quality checks (needs steps 1-5)
  validate_cocom.py                COCOM region assignment verification
  etl/structured_parsing/validate_field_values.py  FieldValues spot checks & coverage

STARDICT DICTIONARIES (for KOReader / GoldenDict / offline use):
  etl/stardict/build_stardict.py   Builds StarDict (.ifo/.idx/.dict.dz) dictionaries
  Generates 72 dictionaries: 36 years x 2 editions (General + Structured)
  General:    full field text grouped by category
  Structured: parsed numeric sub-values with units from FieldValues
  Run: python etl/stardict/build_stardict.py
       python etl/stardict/build_stardict.py --years 2025
  Requires: pip install pyglossary python-idzip

UTILITIES:
  scripts/factbook_search.py       Command-line search & browse tool
  scripts/capture_screenshots.py   Screenshot capture tool
  queries/factbook_powerbi_queries.sql   18 sample queries for Power BI / SSMS
  queries/factbook_test_queries.sql      Test queries
  notebooks/factbook_analysis.ipynb      Jupyter analysis notebook
  notebooks/intelligence_analysis.ipynb  Intelligence analysis notebook
  scripts/archive/                       One-time migration scripts & diagnostics

HOW TO USE:
  Option 1: Visit https://worldfactbookarchive.org (live webapp)
  Option 2: Run locally:
    cd C:\Users\milan\CIA_Factbook_Archive
    python -m uvicorn webapp.main:app --port 8080
  Option 3: Open notebooks/factbook_analysis.ipynb in VS Code
  Option 4: Open queries/factbook_powerbi_queries.sql in SSMS
  Option 5: Command-line search:
    python scripts/factbook_search.py years
    python scripts/factbook_search.py search "nuclear"
    python scripts/factbook_search.py country "us" 2020
    python scripts/factbook_search.py compare "ch" "Population"

DATA SOURCES:
  1990-2001: CIA World Factbook text files from Project Gutenberg
  2000-2020: CIA World Factbook zip archives via Wayback Machine
  2021-2025: github.com/factbook/cache.factbook.json
