---
title: "CIA World Factbook Archive"
subtitle: "Project Report | Methods, Verification, and Distribution"
author: "Milan Milkovich, MLIS"
date: "3 October 2026 | Review draft"
---

This report describes the archive as of 3 October 2026. Exact public counts and app availability are dated observations. Validation results refer to the specific database snapshots named below. Its claims are limited to the cited evidence.

# 1. Project summary and evidence status

The project preserves 36 editions of the CIA World Factbook in a searchable database, serves them on a public research website, and bundles them in a separate offline app. It has published its raw inputs and a reproducible comparison against a dated database snapshot, checked the final Factbook edition against an independent preservation copy, and repaired documented entity identity errors. Each result has a defined scope.

| Current statement | Evidence and limit |
|:--|:--|
| Public database size | The live archive displayed 285 entities and 1,071,313 fields on 3 October; the live country API summed to 9,535 country-year records. These are live observations, not the v3.5 release counts. |
| Raw-input agreement | The May comparison recorded 1,070,747 matching rows against 1,071,489 SQLite rows. Those counts imply 99.93%, while the report printed 99.94%; its difference categories also mix rows and keys. It is not a test of every original byte or the October live database. |
| Database authority | The raw-source validation declared SQLite canonical and documented drift in the legacy SQL Server mirror. Current SQL Server parity requires a separate check. |
| Offline app | The Factbook app has iPhone/iPad, Android, macOS, and Windows distribution paths. Direct-download release 1.4.1 is available for Android, macOS, and Windows; store versions are separate. |
| Persistent citation | Use the concept DOI [`10.5281/zenodo.18884612`](https://doi.org/10.5281/zenodo.18884612) for the continuing project, and an exact release tag for a specific artifact. |

# 2. Scope, artifacts, and architecture

The core dataset remains the CIA World Factbook editions for 1990–2025. The CIA discontinued its online Factbook on 4 February 2026. “2025” is the project's name for its final edition. Its last pre-shutdown content snapshot was captured in January 2026; the estimate or source year shown inside an individual field can be earlier. Users should not read an edition label as a claim that every statistic was measured in that year. [Final Snapshot Verification](https://worldfactbookarchive.org/about)

The project now has three distinct delivery surfaces:

1. The [public archive repository](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025) holds extraction code, methodology, reference exports, provenance reports, and links to release assets. Its [`factbook.db` release](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/releases/tag/v3.5) is a **versioned data artifact**, so its counts must not be presented as a live total without a date.
2. The [research website](https://worldfactbookarchive.org/) serves the archive and online research tools. It uses a SQLite copy for its Factbook views. Intelligence Atlas, Studies in Intelligence, World Leaders, and other OSINT views belong to the website's broader research surface, with their own sources and update cycles. They should not be described as part of the CIA Factbook source dataset.
3. The [companion app](https://worldfactbookarchive.org/apps) is a separate Flutter product built for offline Factbook use. It bundles the 36-edition archive, CIA maps, search, Factbook Analysis, Query & Dashboard, Border Explorer, and games. The site's online Intelligence Studies and OSINT tools are absent from the offline app by design.

SQLite is the canonical published database for the raw-source comparison. The legacy SQL Server mirror is a development and export artifact; its state should be tested independently before a claim of parity. [Raw-source validation, L0 and L3b](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/VALIDATION.md)

# 3. Acquisition and transformation method

The archive combines inputs from three publication eras. The precise release inputs and upstream locations are recorded in [`raw-sources/MANIFEST.json`](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/MANIFEST.json).

- **1990–1999 and 2001:** Project Gutenberg text is parsed with rules that follow format changes within the decade. Seven truncated 1996 country entries are repaired from an archived CIA original text capture. The 2001 HTML ZIP was corrupt, so the text edition produced those rows.
- **2000 and 2002–2020:** Archived CIA HTML ZIPs retrieved through Wayback Machine captures are parsed according to their successive layouts.
- **2021–2025:** Distinct year-end commits of the `factbook/cache.factbook.json` mirror provide the JSON editions. The 2025 cutoff is the last pre-shutdown snapshot rather than an ordinary 31 December cutoff.

The published [raw-source bundle](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/releases/tag/raw-sources-v1) contains 38 input files totaling 2.98 GB. It includes the damaged 2001 ZIP as documentary evidence and marks it as producing no database rows. Each asset has a recorded SHA-256 and upstream URL or commit. The release also provides a fetch script and manifest so researchers can reconstruct which bytes were used.

The parsers turn variable text, HTML, and JSON layouts into country, category, and field rows. Original field names remain available while `FieldNameMappings` supplies canonical labels for cross-year queries. Pipe separators in some stored text are parser boundary markers, not characters asserted to appear in the CIA source. `FieldValues` derives typed sub-values from field text; `IsComputed = 1` distinguishes values calculated from neighboring source values from directly extracted ones. These transformations should be disclosed whenever a user compares a database value with the raw publication. [Methodology](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/METHODOLOGY.md)

# 4. Verification evidence and its limits

The raw-source validation separates several questions under “data integrity.” File hashes test asset identity. A parser rerun tests whether those released inputs reconstruct the stored rows. Structural checks test database relationships and field coverage. A comparison against an independent preservation snapshot tests the final edition. Each addresses a different risk.

**Raw inputs to SQLite.** In May 2026, the L3 validator re-parsed all 36 editions and compared the results to `factbook.db.CountryFields`. It recorded 1,070,747 matching rows against 1,071,489 database rows. Dividing those counts yields **99.93%**, whereas the [validation report](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/VALIDATION.md) originally printed 99.94%. The validator counts matches in rows but missing and extra items in distinct `(country, field)` keys; its difference categories cannot be summed into a single unmatched-row total. The report attributes differences to its simplified 1996 repair, decoding of some HTML text, and a duplicate Serbia source entry curated downstream. A corrected rerun is needed to measure the residual precisely. This was a comparison to the then-current SQLite snapshot, **not** a rerun against the October database.

**`SourceFragment` is not a byte-for-byte citation.** The L1 test found only 3,991 of 7,200 sampled fragments (55.4%) verbatim in raw files. The validator explains why: stored fragments can contain inserted pipe separators, reattached HTML labels, flattened JSON keys, or joined source spans. L1 was treated as a sanity signal, not the provenance gate. A researcher needing exact source wording should consult the raw file and edition context, then compare the normalized database row. [Validation, L1](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/VALIDATION.md)

**SQL Server mirror.** The L3b comparison found 1,063,060 matches among 1,071,601 SQL Server rows (99.20%) at its May baseline and reported real legacy text-year differences. The report explicitly selected SQLite as canonical for the release. A later cleanup plan is documented, but this update does not claim that the mirror is currently identical without a fresh parity check. [L3b report](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/L3B_REPORT.md)

**Final edition.** The website's [Final Snapshot Verification](https://worldfactbookarchive.org/about) reports that on 12 May 2026 the project's last edition was compared with a separate Mozilla Data Collective preservation copy: 260 country codes on each side, 32,594 fields compared, and zero content differences. This evidence concerns the final snapshot; it does not validate every prior edition or every derived field.

**Entity identity repair.** A [September 2026 audit](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ENTITY_INTEGRITY_ISSUE_38.md) found Georgia and Zimbabwe mislabeled as territories, Cook Islands and Niue mislabeled rather than freely associated, 34 historical edition links attached to the wrong entity, and 176 glossary rows absorbed into Zimbabwe's 1998 entry. The repair documents source-based identity decisions, backup-first transactional application, regression tests, and a copy-of-production field total changing from 1,071,489 to 1,071,313. The current public archive displays the latter field count. This audit is strong evidence for those specific corrections, not a universal certification of every country label or historical figure.

# 5. Current access and distribution

On 3 October 2026, the [live archive page](https://worldfactbookarchive.org/archive) displayed **285 entities, 36 editions, and 1,071,313 fields**. The [country API](https://worldfactbookarchive.org/api/countries) returned 285 entity rows whose edition counts sum to **9,535**. The 281/9,536/1,071,603 combination in older documentation describes an earlier release. Some repository and website metadata still repeat it; therefore exact metrics should always specify a snapshot and be refreshed before a new publication.

The [Apps page](https://worldfactbookarchive.org/apps) currently lists the app for iPhone/iPad, Android, macOS, and Windows. The [public GitHub 1.4.1 release](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/releases/tag/apps-v1.4.1), published 3 October 2026, contains the Android APK, a signed and notarized macOS DMG, a Windows portable ZIP, and a Windows MSIX submission package. The release note says the Microsoft Store and App Store have separate publication processes. The app page likewise says store versions can differ from direct downloads. Do not infer a store's current version from a GitHub asset.

The app is an **offline Factbook reference and analysis product**. It runs without an account or network for its bundled archive and maps. Website-only OSINT collections rely on different data and stay outside that bundle. Describing the website and the app separately avoids implying that every web research tool works offline.

The project also distributes `factbook.db`, source files, and StarDict dictionaries through versioned GitHub releases. Use the [concept DOI 10.5281/zenodo.18884612](https://doi.org/10.5281/zenodo.18884612) in general citations; cite an exact release tag or asset hash when reproducibility requires a particular version.

# 6. Research use, limitations, and next verification

The archive records the CIA's published assessments. It does not independently certify their real-world accuracy. Country boundaries, status labels, field names, and the estimate years inside values change over time. The project maps names and labels for retrieval, but researchers should inspect the original entry before treating a mapped series as directly comparable across all 36 years.

Parsing is a transformation. HTML entities and encoding, section boundaries, duplicate source records, and legacy name aliases have all needed corrections. The 1996 source repair and September 2026 identity audit show why a general “100% accurate” claim would be too broad. `SourceFragment` and `IsComputed` help users inspect transformation history but do not replace the raw source. The [raw-source manifest](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/MANIFEST.json) is the starting point for a disputed field.

Before issuing a new database release or updating exact public totals, repeat the counts and relevant integrity tests on the release candidate; compare its raw-input reconstruction with that candidate rather than reusing the May result; verify the live site after deployment; and test app assets and store listings as separate distribution channels. Visitor counts, feature inventories, and deployment details require current checks before reuse.

No exclusivity claim is made about competing archives. The supported contribution is concrete: a 36-edition structured collection, released raw inputs and provenance evidence, a public research website, and an offline app with platform-specific distribution.

# 7. How to verify a precise claim

A historical claim should be checked against a named edition and source asset, rather than against a rounded platform statistic. The following path is available to readers without access to the project's development database:

1. Open the [raw-source manifest](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/MANIFEST.json) and identify the file or files for the edition. Record the upstream URL or commit and SHA-256. For 1996, inspect both the Gutenberg text and the CIA repair source; for 2001, use the Gutenberg text rather than the damaged HTML ZIP.
2. Download that exact asset from [the raw-source release](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/releases/tag/raw-sources-v1) and compare its SHA-256 with the manifest. A fresh download from an upstream site may have different bytes, so keep the release asset and upstream copy distinct.
3. Find the country, field label, value, and any estimate year in the original text, HTML, or JSON. Then inspect the corresponding database row and mapping. A canonical field label is a retrieval aid; the CIA's original label remains the primary evidence for how the edition presented the fact.
4. If a typed sub-value is used, inspect `SourceFragment` and `IsComputed`. Trace transformed fragments back through the full field text to the raw publication. The fragment itself is not guaranteed to be a verbatim span of the raw file.
5. Record the database release or live-access date. For claims about the final edition, the [independent-snapshot comparison](https://worldfactbookarchive.org/about) supplies additional evidence. For corrected entity identities, consult the [September audit](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ENTITY_INTEGRITY_ISSUE_38.md).

The repository includes `scripts/validate_raw_l3.py` and `scripts/validate_raw_l3b.py` for full comparisons when the matching raw inputs and database are available. Their May results are historical baselines; rerunning against a newer database requires a new report and a fresh interpretation of differences.

# 8. Sources and citation

- [Archive README and release history](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025)
- [Raw-source release, manifest, and validation](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/tree/main/raw-sources)
- [September 2026 entity identity audit](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ENTITY_INTEGRITY_ISSUE_38.md)
- [Live archive](https://worldfactbookarchive.org/archive), [Final Snapshot Verification](https://worldfactbookarchive.org/about), and [Apps page](https://worldfactbookarchive.org/apps), checked 3 October 2026
- [App release 1.4.1](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/releases/tag/apps-v1.4.1), published 3 October 2026
- Milkovich, M. (2026). *CIA World Factbook Archive 1990–2025* [data set]. Zenodo. [https://doi.org/10.5281/zenodo.18884612](https://doi.org/10.5281/zenodo.18884612)
