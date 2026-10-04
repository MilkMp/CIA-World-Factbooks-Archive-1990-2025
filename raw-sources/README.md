# CIA World Factbook — Raw Sources (1990-2025)

The original input files that produced `factbook.db` — every CIA World
Factbook edition from 1990 to 2025, as the bytes the parsers consumed.

---

## Download the data

> **All 38 raw source files (2.98 GB) are in the [`raw-sources-v1` GitHub Release](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/releases/tag/raw-sources-v1).**
>
> Click → scroll to Assets → download what you want. Each year is its own
> file (5 MB to 367 MB per year). You don't need the whole 3 GB.

The Release contains:

- **21 HTML zips** for 2000-2020 (CIA Wayback Machine captures)
- **12 plaintext files** for 1990-1999, 2001 (Project Gutenberg) + the 1996 CIA original (Wayback ODCI)
- **5 JSON snapshot zips** for 2021-2025 (factbook-json-cache mirror, year-end commits)

**Why isn't the data in this folder?** GitHub's per-file git limit is 100 MB,
and 10 of our HTML zips exceed it (`factbook-2020.zip` alone is 367 MB).
GitHub Releases are designed for exactly this case: free unmetered downloads,
2 GB per file, no repo bloat.

---

## Read the validation alongside the data

Before you trust the raw bytes, see how we proved they produced `factbook.db`:

| File | What it answers |
|---|---|
| **[`VALIDATION.md`](VALIDATION.md)** | Full methodology, all four validation levels (L0 - L3b). The May comparison recorded **1,070,747 matching rows against 1,071,489 SQLite rows (99.93% from those counts)**; its difference categories mix rows and keys. |
| **[`L3_REPORT.md`](L3_REPORT.md)** | Per-year diff: re-parse the raw files in memory and compare every record to SQLite. |
| **[`L3B_REPORT.md`](L3B_REPORT.md)** | Same diff against the legacy SQL Server mirror. Surfaced real data drift in SQL Server (not in the raw files or SQLite). |
| **[`MANIFEST.json`](MANIFEST.json)** | SHA256 hash + upstream URL (Wayback timestamp, Gutenberg ebook ID, or upstream commit hash) for every file. |
| **[`INDEX.xlsx`](INDEX.xlsx)** | Browsable spreadsheet view of the same — open in Excel/LibreOffice. |
| [`SQL_SERVER_CLEANUP_PLAN.md`](SQL_SERVER_CLEANUP_PLAN.md) | Separate operational plan for the SQL Server drift the validation surfaced. Not required reading for raw-sources users. |

The Release bundle includes copies of `README.md`, `MANIFEST.json`, and
`INDEX.xlsx` so they ship alongside the data; the validation reports stay
in this folder where they can be browsed without downloading 3 GB.

---

## What you get from the Release (after download)

When you download from the Release, you get 38 binary assets + 3 metadata
files. They organize into this structure once extracted:

```
raw-sources/
  html/                              2.81 GB — 21 files
    factbook-2000.zip ... factbook-2020.zip
  text/                              38 MB — 12 files
    1990.txt ... 1999.txt, 2001.txt, 1996_cia_original.txt
  json/                              29 MB — 5 files
    factbook-json-2021.zip ... factbook-json-2025.zip
  MANIFEST.json                      manifest with SHA256 + upstream URLs
  INDEX.xlsx                         browsable spreadsheet view
  README.md                          this file
```

Total: 38 binary files, 2.98 GB.

## Sources by era

| Years | Source | Format | Upstream |
|---|---|---|---|
| 1990-1999, 2001 | Project Gutenberg eBooks | Plain text (.txt) | https://www.gutenberg.org/ |
| 2000, 2002-2020 | CIA Wayback Machine archives | HTML in .zip | https://web.archive.org/ |
| 2021-2025 | factbook/cache.factbook.json mirror | JSON in .zip | https://github.com/factbook/cache.factbook.json |

Every file's exact upstream URL (with Wayback timestamp, Gutenberg ebook ID,
or upstream commit hash) is in `MANIFEST.json`. The bundle is reproducible
end-to-end from those URLs via
[scripts/fetch_raw_sources.py](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/scripts/fetch_raw_sources.py)
in the main repo.

## Two special notes

- **`factbook-2001.zip`** is included for completeness but is flagged
  `"produced_db_rows": false` in `MANIFEST.json`. It was a corrupted Wayback
  download — the actual 2001 data was sourced from `text/2001.txt`
  (Project Gutenberg eBook 27638) as a fallback.

- **`text/1996_cia_original.txt`** is the original 1997-05-28 CIA capture from
  Wayback ODCI. It is used by `etl/repair_1996_truncated.py` to repair 7
  truncated countries in the 1996 Gutenberg edition (Venezuela, Armenia,
  Greece, Luxembourg, Malta, Monaco, Tuvalu). It is NOT a replacement for
  `text/1996.txt` — both are needed to fully reconstruct 1996.

## Integrity verification

Every file has a SHA256 in `MANIFEST.json`. To verify all files at once:

```bash
# Linux / macOS
cd raw-sources
python -c "
import json, hashlib
with open('MANIFEST.json') as f: m = json.load(f)
for entry in m['files']:
    # File is in html/, text/, or json/ — check both
    import os
    for sub in ['html','text','json']:
        p = os.path.join(sub, entry['filename'])
        if os.path.exists(p): break
    h = hashlib.sha256(open(p,'rb').read()).hexdigest()
    ok = h == entry['sha256']
    print(('OK' if ok else 'FAIL'), entry['filename'])
"
```

```powershell
# Windows PowerShell
Get-FileHash html\factbook-2010.zip -Algorithm SHA256
# compare to MANIFEST.json
```

## Provenance evidence

These raw bytes have been validated against the published `factbook.db` at
**99.93% from the published counts** (1,070,747 matching rows against
1,071,489 database rows). The May report attributes observed differences to
validator behavior and downstream curation, but its categories mix rows and
keys. A corrected rerun is needed for a precise residual count. Full methodology
and results:

[raw-sources/VALIDATION.md](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/VALIDATION.md)

## How this maps to the database

| Bundle file | ETL script in main repo | DB table populated |
|---|---|---|
| `text/{YEAR}.txt` for 1990-1999, 2001 | `etl/load_gutenberg_years.py` | `Countries`, `CountryCategories`, `CountryFields` |
| `text/1996_cia_original.txt` | `etl/repair_1996_truncated.py` | `CountryFields` (repairs 7 countries) |
| `html/factbook-{YEAR}.zip` for 2000, 2002-2020 | `etl/build_archive.py` | `Countries`, `CountryCategories`, `CountryFields` |
| `json/factbook-json-{YEAR}.zip` for 2021-2025 | `etl/reload_json_years.py` | `Countries`, `CountryCategories`, `CountryFields` |

After these three loaders populate `CountryFields.Content` as pipe-delimited
text, two further steps in the main repo build the structured artifacts in
`factbook.db`:

- `etl/build_field_mappings.py` populates `FieldNameMappings` for cross-year
  field-name queries.
- `etl/structured_parsing/parse_field_values.py` populates `FieldValues`
  (1.78M structured rows with `SourceFragment` provenance back to the original
  `CountryFields.Content` slice).

## License

All source files are in the **public domain**:

- CIA World Factbook content is U.S. government work and not subject to U.S.
  copyright (17 U.S.C. § 105).
- Project Gutenberg files are licensed under the
  [Project Gutenberg License](https://www.gutenberg.org/policy/license.html)
  and the bundled `.txt` files contain the original Project Gutenberg
  headers intact.
- The factbook/cache.factbook.json mirror is a community-maintained scrape of
  CIA's machine-readable JSON output; the underlying data is CIA public domain.

This bundle (the `raw-sources/` directory as a whole, including
`MANIFEST.json` and this README) is released under
[Creative Commons CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/)
— same as the main archive repository.

## Citation

If you use this bundle in research or publication, please cite:

> Milkovich, M. (2026). *CIA World Factbook Archive 1990-2025 — Raw Source
> Bundle.* Zenodo. https://doi.org/10.5281/zenodo.18884612

The DOI above is the concept DOI for the project; it always resolves to the
latest version.

## Questions / discussion

This bundle was produced in response to
[Discussion #30](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/discussions/30).
Open an issue or discussion for questions about specific years, formats, or
data provenance.
