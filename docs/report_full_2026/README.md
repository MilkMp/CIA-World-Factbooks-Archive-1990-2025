# Full project report source

This directory builds the dated full report at `../PROJECT_REPORT_FULL_2026-10-03.pdf`.
The companion executive summary is built separately with
`python docs/build_executive_summary.py`.
The report uses a recorded April 2026 SQLite snapshot for most archive-structure
figures, May 2026 validation documents for validation charts, and separately
dated October 2026 observations for the public site and app. Read figure
captions and the evidence register before comparing counts across snapshots.

## Rebuild

From the repository root, with Python, Matplotlib, NumPy, pypdf, Pandoc,
XeLaTeX, and their normal PDF dependencies available:

```text
python docs/report_full_2026/build_full_report.py
```

The builder regenerates the vector figures and appendices, converts narrative
source links to grouped notes, and renders the PDF. It requires the checked-in
`evidence.json` and repository validation and manifest documents.
To recalculate the local aggregates from a database with the recorded SHA-256:

```text
python docs/report_full_2026/extract_evidence.py --db PATH_TO_FACTBOOK_DB
python docs/report_full_2026/build_full_report.py
```

The extractor opens SQLite read-only and records its source hash and SQL in
`evidence.json`. A database with a different hash is a new evidence
state; update the narrative and captions before presenting regenerated numbers.

## Citations

`report.md` keeps readable source links. `make_cited_report.py`
turns the paragraph-ending source lists into Chicago notes, and Pandoc creates
the bibliography from `references.json`. The bundled
`chicago-notes-bibliography.csl` is the Chicago Manual of Style 18th
edition (notes and bibliography) style from the
[Citation Style Language styles repository](https://github.com/citation-style-language/styles/blob/master/chicago-notes-bibliography.csl).
Its embedded author and Creative Commons Attribution-ShareAlike 3.0 notice are
retained in the style file.
