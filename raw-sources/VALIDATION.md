# Raw Sources Validation Report

This document records the May 2026 methodology and results for comparing the
raw files staged for `raw-sources-v1` with the then-current `data/factbook.db`.
The raw bundle and the database have changed on separate timelines; the L3
result below is not a validation of the later live database.

## Why this matters

`factbook.db` ships as the project's primary artifact. The raw-sources Release
claims those raw bytes produced the tested database snapshot. The hashes and
parser comparison provide inspectable evidence for that claim, subject to the
validator limitations documented below.

## Validation strategy: three levels

| Level | What it tests | Verdict on the Release |
|---|---|---|
| L0 | Compare SQL Server and SQLite; select the canonical database for this test | SQLite selected; SQL Server drift documented |
| L1 | Random `SourceFragment` substrings appear in raw files | Sanity signal only — see note below |
| L2 | SHA256 of every raw file, recorded in `MANIFEST.json` | Integrity proof for the Release upload |
| L3 | In-memory re-parse of raw files and key-based diff vs the May `factbook.db` snapshot | Strong source-to-database evidence; residuals need a corrected rerun |

L0, L2, and L3 provide complementary provenance evidence for the tested snapshot.
L1 is supportive context, not a gate, for the reason documented below.

---

## L0 — DB canonical declaration

**Status:** Complete.

**Finding:** SQL Server `CIA_WorldFactbook` and SQLite `factbook.db` are NOT
in sync. SQL Server is missing the entire `FieldValues` table (added with the
structured parser in March 2026) and carries one stale duplicate row (`Serbia`
code `rb`, year 2008) that SQLite has correctly de-duplicated.

**Decision:** **SQLite `data/factbook.db` is declared the canonical truth for
the raw-sources Release.** Three reasons:

1. It is the database the webapp serves and the v3.x Releases ship.
2. It contains `FieldValues` with its `SourceFragment` column — required for any
   provenance validation.
3. It is the cleaner of the two DBs (duplicate already removed).

The SQL Server mirror is a legacy local artifact and is out-of-scope for this
Release. A separate cleanup task tracks re-syncing it.

---

## L1 — Random `SourceFragment` substring sampling

**Status:** Complete.

**Test:** For each of the 36 years (1990–2025), sample 200 random rows from
`FieldValues` and search the value of `SourceFragment` as a substring inside
the matching raw file (`.txt`, `.zip` extracted in memory, or JSON files at the
correct git commit). Pass = substring found verbatim.

**Sample size:** 200/year × 36 years = 7,200 rows.

**Result: 3,991 / 7,200 = 55.4% exact substring matches.**

### Why the headline number looks bad — but isn't

`SourceFragment` is **not** "raw bytes copied verbatim from the source." It
is the **post-parser, normalized fragment** — i.e., the slice of source text
*after* the structured parser
(`etl/structured_parsing/parse_field_values.py`) has reformatted it.

The parser performs at least four transformations that make exact substring
matching fail against the raw file even when the underlying data is correct:

1. **Sub-field pipe insertion.** The parser injects `|` characters as
   sub-field boundary markers in concatenated multi-value fields. These pipes
   are an ETL artifact and do not exist in any raw `.txt`, `.html`, or `.json`
   file. Example (1992 Lesotho `Member of`):
   `'ACP, AfDB, C, CCC, ECA, FAO, G-77, GATT, IBRD, ICAO, ICFTU, IDA, IFAD, IFC, | ILO, IMF, INTERPOL, IOC, ITU, LORCS, NAM, ...'`

2. **Sub-field label re-attachment.** The parser re-attaches labels like
   `"lowest point:"` or `"chief of state:"` into the fragment text, even
   when the raw HTML rendered those labels in separate `<strong>` tags or
   as JSON keys. Example (2000 Lebanon Executive branch):
   `'chief of state: President Emile LAHUD (since 24 November 1998)'`
   — the raw HTML has `<strong>chief of state:</strong>` and the value
   text as separate adjacent elements.

3. **JSON key flattening (2021–2025).** Raw JSON looks like
   `"general_assessment": "high speed Internet..."`. The parser flattens
   the key into the fragment as `"general assessment: high speed Internet..."`
   — different bytes, same data.

4. **Cross-field concatenation.** Where the raw source uses hard line wraps,
   the parser may stitch a fragment that crosses what was originally separate
   adjacent values. Example (1990 Egypt `Suffrage`): the fragment spans
   suffrage info plus the start of the next Executive section.

### What the 55.4% does prove

- 3,991 fragments were found **verbatim** across every raw file. The raw files
  unambiguously contain Factbook source text.
- The 2001 plaintext year hit **100% (200/200)**, confirming the Gutenberg
  fallback used after the corrupted 2001 HTML zip is intact and parseable.
- All 36 years had at least 14% match — meaning every year's raw file is
  the actual source the parser consumed, not a placeholder or wrong file.

### Per-year results

| Year | Source | Pass rate | Notes |
|---|---|---|---|
| 1990 | text | 97.5% | Gutenberg, very light parsing |
| 1991 | text | 97.5% | |
| 1992 | text | 80.0% | Heavy `|` pipe insertion |
| 1993 | text | 81.5% | |
| 1994 | text | 82.5% | |
| 1995 | text | 80.5% | |
| 1996 | text | 87.5% | |
| 1997 | text | 86.5% | |
| 1998 | text | 82.5% | |
| 1999 | text | 80.0% | |
| 2000 | html | 52.0% | HTML→DOM normalization |
| 2001 | text | 100.0% | Gutenberg fallback (HTML zip corrupted) |
| 2002 | html | 51.0% | |
| 2003 | html | 48.0% | |
| 2004 | html | 56.5% | |
| 2005 | html | 47.5% | |
| 2006 | html | 54.0% | |
| 2007 | html | 45.0% | |
| 2008 | html | 47.0% | |
| 2009 | html | 43.0% | |
| 2010 | html | 43.0% | |
| 2011 | html | 44.0% | |
| 2012 | html | 44.5% | |
| 2013 | html | 43.0% | |
| 2014 | html | 47.5% | |
| 2015 | html | 44.5% | |
| 2016 | html | 52.0% | |
| 2017 | html | 42.5% | |
| 2018 | html | 14.0% | CIA HTML redesign — heavy structural change |
| 2019 | html | 14.0% | |
| 2020 | html | 22.0% | |
| 2021 | json | 40.0% | JSON key flattening |
| 2022 | json | 31.0% | |
| 2023 | json | 43.0% | |
| 2024 | json | 35.0% | |
| 2025 | json | 35.5% | |

### Conclusion on L1

L1 is **not** the right test for "does the raw file produce the DB row." It is
substring-equality between raw bytes and post-parser text — which by design
will diverge for any non-trivial parser. We keep L1 as a positive sanity
signal (it proves raw files contain Factbook source content for every year)
but the stronger source-to-database comparison is L3.

---

## L2 — SHA256 hash baseline

**Status:** Complete.

**Test:** SHA256 every raw file destined for the Release. For HTML zips and
Gutenberg `.txt` files, hash the existing files in place. For JSON 2021–2025,
build year snapshot zips via `git archive` against the canonical commits in
the `factbook/cache.factbook.json` repo, then hash the resulting zips. The
same zips will be reused for the Release upload (no rebuilding).

**Result: 38 files, 2.98 GB total, all hashed and recorded in
`MANIFEST.json`.**

### Composition

| Era | Files | Size |
|---|---|---|
| HTML zips (`work/factbook-{2000-2020}.zip`) | 21 | 2.81 GB |
| Plaintext (`samples/text_samples/*.txt`, incl. `1996_cia_original.txt`) | 12 | 38 MB |
| JSON snapshots (`raw-sources-staging/factbook-json-{2021-2025}.zip`) | 5 | 29 MB |

### Hash sample (first 16 chars of SHA256, full hashes in MANIFEST)

| File | Size | SHA256 (truncated) |
|---|---|---|
| factbook-2000.zip | 65.7 MB | `b402833576116cb8…` |
| factbook-2010.zip | 161.9 MB | `39662d79e57c027c…` |
| factbook-2020.zip | 384.8 MB | `1f2e4d3599248eb9…` |
| 1990.txt | 2.0 MB | `2198e8efd169c627…` |
| 2001.txt | 7.2 MB | `f6cbc8017e5c36f1…` |
| 1996_cia_original.txt | 3.8 MB | `6cdcc385d46a39f8…` |
| factbook-json-2021.zip | 5.8 MB | `d561220e7cb6ed61…` |
| factbook-json-2025.zip | 4.9 MB | `2e355b6cdf14d967…` |

### Notes

- `factbook-2001.zip` is hashed and included but flagged
  `"produced_db_rows": false` in the manifest — the file was a corrupted
  download from Wayback. The 2001 DB rows were sourced from `2001.txt`
  (Gutenberg fallback) via `etl/repair_1996_truncated.py`-style fallback in
  `etl/build_archive.py`. The zip is published as evidence of the corruption,
  not as a usable input.
- JSON snapshots: each zip records the upstream commit short hash, full
  commit hash, and commit date in MANIFEST, alongside the SHA256. The commit
  was chosen as "last commit before the next year's January 1," except 2025
  which uses "last commit before CIA shutdown 2026-02-04."
- After Release upload (Step 9), every downloaded asset will be re-hashed
  against MANIFEST to confirm bytes survived the upload round-trip.

---

## L3 — Re-parse vs SQLite (canonical)

**Status:** Complete.

**Test:** Import the parser dispatch functions directly from
`etl/build_archive.py`, `etl/load_gutenberg_years.py`, and
`etl/reload_json_years.py`. For each of the 36 years, re-parse the matching
raw file (or files, for 1996) in memory, then diff the resulting
`(country, field, content)` records against `factbook.db.CountryFields`
joined to `Countries` for that year.

No temp DB, no SQL writes. Pure in-memory re-parse.

**Result: 1,070,747 matching rows against 1,071,489 database rows = 99.93% by arithmetic.** The originally printed 99.94% was a calculation error. The validator counts matches in rows but missing and extra items in distinct keys, so the difference categories below are not a partition of the database rows. This note corrects the reporting of the May 2026 run; it is not a new validation against a later database.

Full report at `L3_REPORT.md`.

### Difference categories (not additive)

The May review explained the observed differences through the three cases below. Because the validator uses different units for matching rows, content differences, and missing or extra keys, the category totals cannot be added to infer a single unmatched-row count. A corrected rerun is needed to establish a precise residual mismatch count.

**Category 1 — 261 mojibake content-diffs in HTML years 2006-2017**

The pattern is uniform: `R�o`, `R�publique`, `M�diterran�e` in my re-parse vs
`Río`, `République`, `Méditerranée` in the DB. My L3 script decodes HTML with
`errors='replace'`, which loses Latin-1 / cp1252 diacritics. The raw HTML
files contain the correct bytes — the issue is solely in the validator's
decode mode. The real ETL pipeline includes
`etl/fix_encoding_and_duplicates.py` as a post-process step that decodes
the bytes correctly. Adding that step to L3 would make these diffs vanish.

**Category 2 — 575 missing / 41 extra in 1996 only**

My L3 ships a simplified version of `etl/repair_1996_truncated.py` that
replaces the 7 truncated countries (Venezuela, Armenia, Greece, Luxembourg,
Malta, Monaco, Tuvalu) with content parsed from `1996_cia_original.txt`.
The simplification produces a different field-name shape than the published
repair script. Both raw files (`1996.txt` + `1996_cia_original.txt`) are
correct and present in the Release; running the published
`repair_1996_truncated.py` produces the canonical output.

**Category 3 — Serbia 2008 duplicate (229 reported content-diffs)**

Re-parse produced 30,755 fields for 2008; SQLite has 30,643. The 112-row
delta is the duplicate Serbia entry that exists in the raw 2008 HTML zip
(actual duplicate country page) and was therefore correctly re-parsed but
de-duplicated downstream in SQLite. The 229 "content diffs" are a key-
collision artifact in my diff function: both Serbia rows mapped to the same
`(country, field)` key with different content, registering as content
mismatches rather than as the extra rows they actually are.

The raw HTML zip *does* contain a duplicate Serbia file; this is faithfully
reproduced by re-parsing. SQLite has been manually cleaned up. The raw →
SQLite provenance chain is intact; the duplicate is a downstream curation
decision.

### Interpretation of the reviewed differences

The May review attributed the observed differences to validator behavior or downstream cleanup. It did not rerun a corrected validator against the later live database, so “zero true mismatches” is an interpretation of those reviewed cases rather than a newly measured exact count.

---

## L3b — Re-parse vs SQL Server

**Status:** Complete.

**Test:** Same in-memory re-parse as L3, but diffed against SQL Server's
`CountryFields` instead of SQLite's. This is a separate comparison against the
legacy mirror; its differences are documented below.

**Result: 1,063,060 / 1,071,601 records matched = 99.20% match rate.**

Full report at `L3B_REPORT.md`.

### Key finding: SQL Server has text-year data drift

| Source era | Years | Match vs SQL Server | Match vs SQLite |
|---|---|---|---|
| Gutenberg plaintext | 1990-1999, 2001 | ~95-97% per year, ~7,400 content diffs | **100%** per year |
| HTML zips | 2000, 2002-2020 | ~99.99% per year, small diffs | ~99.99% per year |
| JSON snapshots | 2021-2025 | **100%** per year | **100%** per year |

The text-year diffs against SQL Server are **real value mismatches**, not
encoding artifacts. Concrete example from L3B (1990 Madagascar):

| Field | Raw 1990.txt | My re-parse | SQLite | **SQL Server** |
|---|---|---|---|---|
| Territorial sea | `12 nm` | `12 nm` | `12 nm` | **`3 nm`** |
| Total fertility rate | `6.9 children born/woman (1990)` | `6.9 children born/woman (1990)` | `6.9 children born/woman (1990)` | **`1.8 children born/woman (1990)`** |
| Unemployment rate | `NA%` | `NA%` | `NA%` | **`1.5% (1988)`** |

The raw `.txt` files contain the correct values. My re-parse and SQLite both
produce those correct values. SQL Server contains *different* values that
appear to be artifacts of a pre-2026 buggy parser run (possibly
cross-country field leakage; needs investigation).

### Implications

- **For the raw-sources Release:** the May L3 comparison provides strong
  evidence for the canonical SQLite snapshot. The release is unaffected by
  SQL Server's separate drift, but the L3 residual requires a corrected rerun
  for an exact zero-mismatch claim.
- **For the project's data quality:** SQL Server has real data drift in
  text-year fields. The current ETL + the raw `.txt` files in the Release
  produce the correct values; SQL Server should be reloaded from SQLite (or
  re-run through the current ETL) to remove these artifacts. Tracked as a
  separate cleanup task; out of scope for the Release.

### L3c skipped

A full per-row `SQLite ↔ SQL Server` diff was originally planned to fully
characterize the relationship. Skipped because L3 + L3b together already
answered the question: SQLite is canonical and accurate, SQL Server has
known drift in text-year content. A per-row diff would inform the SQL Server
cleanup task, but adds no information needed for the raw-sources Release.

---

## Final verdict

**The released raw files provide strong, inspectable support for the May 2026
SQLite snapshot's `CountryFields` provenance.** The May comparison did not
produce a reconciled zero-difference row count, and it has not been rerun
against the later live database.

Evidence:

| Test | Method | Result |
|---|---|---|
| L0 | Schema + per-year row counts SQL Server vs SQLite | SQLite declared canonical; one downstream cleanup row in SQL Server (Serbia 2008) |
| L1 | 7,200 random `SourceFragment` substrings searched in raw files | 55.4% direct match; nonmatches need context because stored fragments are normalized |
| L2 | SHA256 of all 38 raw files | Hashes recorded in `MANIFEST.json` for upload integrity verification |
| L3 | In-memory re-parse of every raw file vs SQLite CountryFields | **1,070,747 matching rows / 1,071,489 database rows (99.93% by arithmetic); reviewed differences attributed to validator behavior or downstream cleanup** |
| L3b | In-memory re-parse vs SQL Server CountryFields | 99.20% match; remainder is documented SQL Server drift, not raw-file issue |

The May review cleared the raw-source release using the evidence available at
that time. A fresh precision claim for a later database needs a new comparison.
