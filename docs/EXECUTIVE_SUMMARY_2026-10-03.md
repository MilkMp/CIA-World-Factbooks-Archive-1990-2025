---
title: "CIA World Factbook Archive"
subtitle: "Executive Summary | October 2026 review draft"
author: "Milan Milkovich, MLIS"
date: "3 October 2026"
---

## Purpose and scope

The CIA World Factbook Archive preserves 36 editions of the CIA's World Factbook, from 1990 through 2025, in a searchable research database. The online Factbook ended on 4 February 2026. The archive keeps the publication's historical country entries accessible across changes in format, names, and field labels. It also provides a public research website and a separate offline companion app.

**Current public database snapshot.** On 3 October 2026, the live archive displayed **285 entities**, **36 editions**, and **1,071,313 field rows**. Its country API listed **9,535 country-year records**. These are live figures, not the March 2026 v3.5 release totals still printed in some older documentation. Counts can change when documented parsing or identity errors are repaired. [Live archive](https://worldfactbookarchive.org/archive) · [Country API](https://worldfactbookarchive.org/api/countries)

## How the archive was made

| Editions | Published input used by the archive | Treatment |
|:--|:--|:--|
| 1990–1999 and 2001 | Project Gutenberg plain-text editions | Year-specific text parsers; the seven truncated 1996 country entries were supplemented from an archived CIA original. |
| 2000 and 2002–2020 | CIA HTML archive ZIPs preserved by the Wayback Machine | Parsers for successive HTML layouts. The damaged 2001 HTML ZIP was retained as evidence but did not produce database rows. |
| 2021–2025 | Git snapshots of the community-maintained `factbook/cache.factbook.json` mirror | Distinct year-end snapshots; the final 2025 edition uses the last pre-shutdown snapshot. |

The project published the **38 input files (2.98 GB)** in a [raw-source release](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/releases/tag/raw-sources-v1), with SHA-256 hashes and upstream locations in a [manifest](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/MANIFEST.json). The parser normalizes layout and maps changing field names into a separate lookup table. A structured-value table exposes sub-fields for analysis; values created by computation are marked `IsComputed`. [Methodology](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/METHODOLOGY.md)

\newpage

## What was verified

The [raw-source validation](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/VALIDATION.md) re-parsed the released inputs and compared them with a **May 2026 SQLite snapshot**. It recorded **1,070,747 matching rows against 1,071,489 database rows** (about 99.9%). The validator documents differences involving decoding, the special 1996 repair, and a duplicate Serbia source entry. Its published percentage and difference categories need accounting clarification, as the project report explains. This was not rerun against the October live database.

`SourceFragment` stores a **post-parser fragment**. Its presence for a parsed sub-value does not mean the raw publication contains those exact bytes: the parser can insert separators, flatten JSON keys, and join labels to values. The older summary's “100% provenance” claim therefore overstated what this column alone establishes. [Validation details](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/VALIDATION.md)

The website's [Final Snapshot Verification](https://worldfactbookarchive.org/about) reports that an independent preservation copy held by Mozilla Data Collective matched all **32,594 compared fields across 260 country codes**, with no content differences, on 12 May 2026. “2025 edition” names the archive's final edition; an individual field may carry an earlier estimate or source year.

## Ways to use it

The [website](https://worldfactbookarchive.org/) supports browsing, search, comparison, export, and analytical views. Its Intelligence Studies and other online OSINT collections are separate from the Factbook dataset. The [offline app](https://worldfactbookarchive.org/apps) bundles the 1990–2025 Factbook, CIA maps, search, Query & Dashboard, Border Explorer, and games; it does not include those online OSINT tools. The public app page lists iPhone/iPad, Android, macOS, and Windows options. GitHub's [1.4.1 release](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/releases/tag/apps-v1.4.1) supplies direct Android, macOS, and Windows downloads. App Store and Microsoft Store versions follow their own release processes and may differ from the direct download.

The database and raw-source bundles remain available from [GitHub Releases](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/releases). Cite the project's **concept DOI**, [10.5281/zenodo.18884612](https://doi.org/10.5281/zenodo.18884612), when referring to the continuing archive.

## Limits that matter for research

Factbook entries are the CIA's dated assessments, not measurements made by this archive. Format normalization, field mapping, and targeted corrections make them searchable but can affect the form of a record. Users should check the underlying edition, the field's own estimate year, `IsComputed` for derived sub-values, and the raw-source manifest before making a precise historical claim. The [September 2026 entity audit](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ENTITY_INTEGRITY_ISSUE_38.md) shows why entity identity and classification require explicit review. No claim of exhaustive error-free transcription or exclusive coverage of this subject is made here.
