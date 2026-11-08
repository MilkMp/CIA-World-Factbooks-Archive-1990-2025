# StarDict Reader Edition: Local Validation

**Date:** 2026-11-08
**Status:** Built and validated locally. KOReader hardware testing remains pending.

## Source and scope

- A consistent, read-only SQLite backup was taken from the live Factbook archive on 2026-11-08. It passed `PRAGMA quick_check`.
- Source SHA-256: `4463dc615288bcb2fc0dd0f9e60c69ec4d1f43dea4872e19068fa5928a4b6cee` (702,590,976 bytes).
- One reader dictionary per year, 1990-2025. The snapshot includes historical data corrections not present in the older local archive database. No source database was changed.
- The previously released `general` tarballs remain unchanged during testing. Once the reader edition is accepted, mark the old release as superseded and update recommended download links.

## Format

Each year contains complete country profiles (`Afghanistan`), category pages (`Afghanistan Geography`), and direct field pages (`Afghanistan - Area`). ISO/FIPS aliases resolve to those entries when unambiguous. Category and field labels are colored; source subfield separators are rendered as line breaks. Headwords retain the year-specific CIA country names.

This is intentionally a **text-only** edition: the archive database is a 1990-2025 text collection, not a complete historical photo or map archive. The 2014 KOReader dictionary did include images, so the release notes should state this difference without treating missing images as a defect in the text export. Some 2000-2020 source ZIPs contain edition-specific maps, but image coverage is incomplete across years. Verified maps could be offered later as an optional, clearly labeled supplement; they are not a blocker for the text release.

## Results

| Check | Result |
| --- | --- |
| Years | 36/36 built and validated |
| Primary entries | 1,153,099 total |
| Aliases | 1,478,338 total |
| 2025 | 34,766 entries, 44,867 aliases, 260 countries |
| Archives | 36 `.tar.gz` files, 179,938,910 bytes total |
| Source match | Every definition and alias checked against the source snapshot |
| Binary integrity | `.ifo` counts, `.idx` offsets, `.syn` targets, UTF-8, and compressed definitions checked |
| Reader round-trip | PyGlossary read all entries across all 36 years |
| Packaging | Each archive reopened and its four StarDict files compared byte-for-byte |
| Unit tests | 5 passed, including historical name/alias collisions and reproducible packaging |

The local `reader-manifest.json` records SHA-256, byte size, and entry counts for each archive. The finalized formatted archives are in `builds/koreader-reader-20261108/tarballs-formatted/` outside the repository. An earlier unformatted local packaging trial remains in `tarballs/`; it is **not** a release candidate.

## Remaining release checks

1. Install at least the 1990, 2014, and 2025 dictionaries in KOReader and GoldenDict-ng; check bare names, category lookups, direct fields, long profile scrolling, and light/dark rendering. A labeled test release can be used to get device feedback. Suggested spot checks: `Soviet Union` (1990), `Afghanistan` and `Afghanistan Geography` (2014 and 2025), and `Zimbabwe` (1998).
2. Describe the edition as text-only and avoid implying complete historical image coverage. Maps can be pursued separately where provenance is clear.
3. Obtain explicit approval before publishing any release or updating KOReader's downloader. As observed on 2026-11-08, GitHub's `Latest` badge is on `apps-v1.4.2`, while the Zenodo concept DOI `10.5281/zenodo.18884612` resolves to the `raw-sources-v1` record, not the v3.5 database record. A new release in this repository could affect that DOI if Zenodo integration is active; choose the release destination and verify the DOI before and after publication.

## Rebuild

From the archive repository root, with `pyglossary` and `python-idzip` installed:

```powershell
python -m unittest discover -s tests -p stardict_reader_test.py -v
python -m etl.stardict.build_reader_stardict --db <reviewed-snapshot.db> --output-dir <dict-dir>
python -m etl.stardict.validate_reader_stardict --db <reviewed-snapshot.db> --dict-dir <dict-dir> --roundtrip
python -m etl.stardict.package_reader_stardict --db <reviewed-snapshot.db> --dict-dir <dict-dir> --output-dir <empty-tarball-dir>
```
