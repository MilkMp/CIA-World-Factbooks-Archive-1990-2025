---
title: "The CIA World Factbook Archive"
subtitle: "Preservation, methods, evidence, website, and offline app | Full project report"
author: "Milan Milkovich, MLIS"
date: "3 October 2026 | Review draft"
documentclass: report
classoption: oneside
fontsize: 10pt
geometry:
  - margin=0.83in
  - headheight=15pt
colorlinks: true
linkcolor: MidnightBlue
urlcolor: MidnightBlue
toc: true
toc-depth: 1
lof: true
numbersections: true
header-includes:
  - \usepackage{fancyhdr}
  - \pagestyle{fancy}
  - \fancyhf{}
  - \fancyhead[L]{\small CIA World Factbook Archive}
  - \fancyhead[R]{\small Review draft | 3 October 2026}
  - \fancyfoot[C]{\thepage}
  - \usepackage{microtype}
  - \let\originaltableofcontents\tableofcontents
  - \renewcommand{\tableofcontents}{\begingroup\footnotesize\setcounter{tocdepth}{0}\originaltableofcontents\setcounter{tocdepth}{1}\endgroup}
---

\begin{abstract}
This report documents a 36-edition archive of the CIA World Factbook, its source acquisition and transformation methods, the evidence available to check its integrity, and the public website and offline companion app built around it. It is a replacement for the unpublished March 2026 report. Most archive-structure figures were generated from a local SQLite snapshot last modified 8 April 2026; each figure identifies its own source and date. The public archive and app descriptions were checked on 3 October 2026. Each validation result is evidence about a named snapshot and test, not a universal accuracy certificate. A commercial book titled \emph{The CIA World Factbook 2026-2027} is addressed separately from the archive's final CIA digital edition, labeled 2025.
\end{abstract}

# Executive summary

The CIA ended The World Factbook on 4 February 2026. This archive preserves 36 editions labeled 1990 through 2025, together with source inputs, extraction code, a queryable SQLite database, and multiple ways to read the collection. Readers can inspect a field in its edition context and compare how the publication changed over time. It is an archive of what the CIA published, not an independent measurement of the world. [CIA farewell notice](https://www.cia.gov/stories/story/spotlighting-the-world-factbook-as-we-bid-a-fond-farewell/); [archive methodology](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/METHODOLOGY.md).

On 3 October 2026, the public archive displayed **285 entities, 36 editions, and 1,071,313 stored field rows**. Its public country API returned 285 entity rows whose reported YearCount values summed to 9,535 country-year records. Those are observations of the live service on that date. The older local SQLite snapshot used for most charts in this report contains 284 master entities, 9,535 country-year rows, and 1,071,489 fields. A September repair removed 176 1998 glossary rows and corrected historical entity links. The two snapshots must not be blended into a single time series. [Live archive](https://worldfactbookarchive.org/archive); [entity audit](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ENTITY_INTEGRITY_ISSUE_38.md).

The source bundle contains 38 files representing 36 editions: Project Gutenberg text, archived CIA HTML ZIPs, and year-specific JSON snapshots. Hashes and upstream references are recorded in the manifest. A May 2026 parser rerun reported 1,070,747 matching rows against 1,071,489 rows in its SQLite comparison snapshot, or **99.93% by arithmetic**. The old published 99.94% headline was wrong. Its unmatched categories mix row and key units, so their counts do not form a complete disjoint partition. The result is strong but bounded evidence for that May snapshot, and a corrected rerun is needed before any exact residual or current-database parity claim. [Manifest](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/MANIFEST.json); [validation report](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/VALIDATION.md).

The public website supports browsing, search, comparison, export, and research views. The separate companion app bundles the Factbook archive and related maps and tools for offline use. The 1.4.1 direct-release assets published on 3 October 2026 include Android, macOS, and Windows packages; iPhone and iPad distribution is listed on the Apps page. Store availability and version are separate from direct-release assets. The app's offline Factbook scope should not be conflated with the site's broader OSINT collections. [Apps page](https://worldfactbookarchive.org/apps); [1.4.1 release](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/releases/tag/apps-v1.4.1).

The final archive edition is labeled **2025**, although its last source capture occurred in January 2026. A publisher sells a book titled *The CIA World Factbook 2026-2027* (April 2026). That title does not establish a new CIA online data edition for either year: the CIA had already ended the publication. The commercial book has not been checked page by page against the archive, so this report does not assert literal identity of every page. The practical distinction is edition year versus commercial book title versus the estimate year embedded in an individual statistic. [CIA farewell notice](https://www.cia.gov/stories/story/spotlighting-the-world-factbook-as-we-bid-a-fond-farewell/); [publisher listing](https://www.skyhorsepublishing.com/9781510786042/the-cia-world-factbook-2026-2027/); [final snapshot verification](https://worldfactbookarchive.org/about).

## How to read the evidence

Every large count needs a population, unit, and date. A **field row** is one stored label-and-content pair in a country-year entry. A **sub-value row** is a parsed component derived from that field. An **entity** is a canonical identity used to connect entries across editions. A **country-year record** is one source entry in one edition; historical polities and territories are included, and the word “country” in a database table is not a claim of sovereignty. Counts from the April local SQLite snapshot are labeled **local snapshot** in chart captions. Counts from the website on 3 October are labeled **live observation**. Counts from the May validation are labeled **May comparison**.

The figures describe the structure of the archived publication and its extraction. They are not trends in real-world population, income, development, or political status. Changes in a chart can reflect the CIA's editorial choices, source format, parser behavior, and database corrections. The report uses the original CIA value and edition context as the first interpretive unit. SQL used for the aggregate figures and a SHA-256 digest of the local source database accompany this draft in the report source directory.

# Purpose, boundaries, and publication history

## Why preserve a changing reference work

The Factbook was a long-lived public reference work. It offered country and territory profiles that mixed statistical estimates, descriptions, geography, government information, and source notes. The CIA's retirement notice describes a publication that began as a classified reference in 1962, gained an unclassified version in 1971, and went online in 1997. The archive's 1990–2025 coverage is a project collection boundary, not the full historical lifetime of the CIA publication. A researcher interested in earlier printed editions needs a different collection. [CIA farewell notice](https://www.cia.gov/stories/story/spotlighting-the-world-factbook-as-we-bid-a-fond-farewell/).

A single final snapshot cannot answer when a field appeared, how a country's label was presented in earlier years, or whether a later edition revised wording. The project therefore treats each labeled edition as a distinct source object. Its relational model connects source entries to a canonical entity when that connection is supportable, while retaining the entry's year-specific name, code, field labels, and content. This enables retrieval without erasing the publication's historical vocabulary.

The archive is also a software system. Its web interface and offline app make the data usable, but the underlying preservation claim rests on source files, hashes, parsing rules, and verifiable records. The report accordingly distinguishes **preservation of inputs**, **faithful representation of source content**, **analytical standardization**, and **delivery**. These layers can succeed or fail independently. A correct download checksum says nothing by itself about a field-name mapping; a polished chart says nothing by itself about the raw source.

## The three clocks a reader must keep apart

An **edition label** is the archive's organizational year, from 1990 to 2025. A **snapshot date** is when an upstream source was captured. A **field estimate or source year** is a date printed inside a particular value. These can differ. The final 2025 edition was captured in January 2026 before shutdown, and individual rows can still contain estimates for earlier years. A chart of archived editions should not reassign values to the edition year unless the indicator's underlying date has been parsed and checked.

This distinction is especially important at the end of the series. A person may see “2026” in a field, a “2026–27” printed book, or a January 2026 archive snapshot and infer a new CIA digital edition. Those labels refer to different objects. The archive's final edition is the last CIA source dataset it preserved; its data-bearing capture occurred in January 2026 and is called 2025 by the project. The CIA announced the end of the Factbook on 4 February 2026. [Final snapshot verification](https://worldfactbookarchive.org/about); [CIA farewell notice](https://www.cia.gov/stories/story/spotlighting-the-world-factbook-as-we-bid-a-fond-farewell/).

## What the 2026–27 book means

Skyhorse Publishing lists *The CIA World Factbook 2026-2027* as a 1,040-page commercial book dated 7 April 2026, ISBN 9781510786042. The publisher's description calls it current for 2026 and looking ahead to 2027. The listing verifies that the **book title and product exist**. It does not provide a complete machine-readable data release or a documented post-closure CIA update sequence. [Skyhorse listing](https://www.skyhorsepublishing.com/9781510786042/the-cia-world-factbook-2026-2027/).

The archive uses “2025” for the final CIA digital edition because there is no separately documented CIA online Factbook edition for 2026 or 2027 after the agency's sunset. The commercial title may package, select, reformat, or supplement material from the final period. Given the publication date and closure, it is reasonable to treat it as a separately marketed print product built from pre-closure Factbook material; that is an inference from the timeline, not a page-level comparison. This draft does **not** assert that every map, appendix, or field in the book is byte-identical to the archive's 2025 snapshot. If exact print-to-digital equivalence becomes a public claim, it needs a documented copy comparison.

For citations, name the object actually used: “CIA World Factbook Archive, 2025 edition, field accessed [date]” for an archive value; *The CIA World Factbook 2026-2027*, ISBN 9781510786042, for the printed book. Neither label overrides the estimate year printed in a field. A bibliography should record the archive version or live access date, the entity, the field label, and the exact displayed source year where relevant.

## Project outputs and scope

The public data repository contains the extraction and parsing code, schema and methodology notes, raw-source manifest, validation reports, reference exports, and links to versioned releases. The research website serves browsing and analysis views. The companion app is a distinct Flutter product built around an on-device Factbook database and bundled assets. Additional website collections, including OSINT and other CIA publications, have separate provenance and should not be counted as Factbook fields. [Repository](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025); [Apps page](https://worldfactbookarchive.org/apps).

The project supports historical comparison and exploratory research. It does not provide an official CIA service, update the discontinued Factbook, validate the CIA's underlying estimates, or guarantee that every mapped field has unchanged meaning across 36 editions. These boundaries identify the checks needed before a specific analysis can be trusted.

# Source collection and edition construction

## Source inventory by publication era

No single bulk source covers all 36 years. The manifest records 38 released files totaling 2,981,435,015 bytes: 12 plaintext files, 21 HTML ZIPs, and five JSON snapshots. One extra plaintext file is the CIA original used to repair seven truncated 1996 country entries. The 2001 HTML ZIP is retained as evidence but marked as producing no database rows because it is corrupt; Project Gutenberg text supplies the 2001 entry data. The number of files is therefore greater than the number of editions. [Manifest](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/MANIFEST.json); [raw-source guide](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/tree/main/raw-sources).

![The source format assigned to each edition in the April local SQLite snapshot. Text = Project Gutenberg, HTML = archived CIA ZIP, JSON = year-specific mirror snapshot.](figures/01-source-timeline.pdf){width=94%}

The source formats also differ sharply in storage size. Summing the manifest's recorded byte lengths yields about 2,913.1 decimal MB of HTML ZIPs, 39.1 MB of text and the 1996 repair source combined, and 29.2 MB of JSON snapshots. The HTML total includes the damaged 2001 ZIP, which was preserved but did not generate database rows. The figure uses a logarithmic horizontal scale so the smaller formats remain visible. It measures bytes in released input packages, not the number of country profiles, fields, or meaningful facts. [Manifest](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/MANIFEST.json).

![Summed input bytes by format in the raw-source manifest, shown on a logarithmic axis. HTML includes a retained but non-producing 2001 ZIP. Package size is not content coverage.](figures/16-source-bytes.pdf){width=92%}

This storage mix affects reproducibility. A researcher who wants to reconstruct a specific JSON edition needs a small, commit-identified snapshot; a researcher who wants to audit all HTML years must manage a much larger package and format-specific tools. The source bundle's file hashes allow either workflow to start with exact assets. A targeted field audit need not download every year, but it must use all files that contributed to the selected edition. The 1996 two-input repair and 2001 fallback are the clearest exceptions to a one-edition, one-file assumption.

The text editions cover 1990–1999 and 2001. The project retrieves Project Gutenberg copies and removes the Gutenberg wrapper before parsing the Factbook body. The existence of a Gutenberg copy establishes access to a text transcription, not automatically byte identity with every contemporaneous CIA print page. For the affected 1996 entries, the separate CIA original text capture supplies a documented repair path. The source manifest identifies both files, and the ETL code names the replacement routine. [ETL pipeline](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ETL_PIPELINE.md); [1996 repair method](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/METHODOLOGY.md).

The HTML years are 2000 and 2002–2020. These are archived ZIP copies of CIA download packages located through Wayback Machine captures. The ZIPs contain country pages, but their HTML templates changed repeatedly. File discovery, country-code interpretation, section extraction, entity decoding, and cleanup are era-specific steps. A 2001 ZIP appears in the manifest for documentary completeness even though it produces no rows. The source inventory should not be simplified into “2000–2020 HTML” without this exception. [Raw-source guide](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/tree/main/raw-sources); [ETL pipeline](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ETL_PIPELINE.md).

For 2021–2025, the project uses distinct commits of the public Factbook JSON mirror. The first four selections use year-end cutoffs; the final cutoff is before the February 2026 shutdown. This matters because taking the newest JSON for every year would silently duplicate a later source state under five edition labels. The manifest records the exact upstream commit for each snapshot. The JSON is a mirror and structured representation of CIA material, so the comparison to an independent final snapshot is an additional check rather than a substitute for keeping the mirror commit. [Methodology](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/METHODOLOGY.md); [manifest](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/MANIFEST.json).

## Immutable inputs and reproducible identification

Each released file has a filename, byte length, SHA-256 digest, upstream URL or commit, parser script, and a flag recording whether it produced database rows. A hash allows a reader to verify that a downloaded release asset is the same sequence of bytes the manifest names. It does not tell the reader whether the parser assigned a line to the right field or whether a lookup table attached the right canonical entity. Those are different tests. The raw-source release and manifest together make the inputs more inspectable than a database download alone. [Raw-source release](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/releases/tag/raw-sources-v1).

For reproducibility, a researcher should use the released asset whose digest matches the manifest, record the parser commit and database version, and then run a comparison with clearly defined row keys. Fetching the same upstream URL again may return a different capture or a changed mirror state. A validation result cannot be transferred to a later database simply because its filename is also factbook.db. The May comparison, the April local chart snapshot, and the October website are separate objects.

## Selection and survival limits

The archive includes one project-designated edition for every calendar label from 1990 through 2025. This is not a claim that all CIA updates within each year were captured. The JSON years use selected commits, and the HTML packages represent downloadable annual archives. A country or field may be present at one point in a year and absent from the selected artifact. The report's charts measure the selected sources, not all possible interim states.

The roster of entities changes. A historical polity may disappear from later editions; a territory may enter the CIA source in a later year; some category titles are introduced or retired. A total across editions is therefore a collection-size measure, not an observation of a stable world population. Queries that compare across years must decide whether to use a fixed group of entities, all entries that year, or the source's own roster.

# Parsing and transformation

## Why one parser could not suffice

The early plaintext editions used several visible conventions for country, category, and field boundaries. The project identifies an old 1990 pattern, a tagged 1991 pattern, colon and asterisk patterns in 1992–1994, at-sign patterns across 1995–2000 text, and an equals pattern for 2001. HTML packages passed through multiple layouts from classic pages to tables, collapsible panels, and later templates. Modern JSON has explicit nested categories but still contains formatted content. The parsers dispatch by source era rather than treating every line or tag as a uniform table. [Methodology](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/METHODOLOGY.md); [ETL pipeline](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ETL_PIPELINE.md).

A parser first finds a source entry and its identity, then category boundaries, field labels, and field content. It records the edition and source type, and normalizes content into a form usable by search and queries. This can decode entities, join hard-wrapped lines, remove layout-only text, and insert delimiters for subfields. These are transformations even when the intention is faithful preservation. A label or fragment derived after parsing should never be presented as guaranteed verbatim source bytes without checking the raw file.

![Conceptual lineage from released source files through year-specific parsers and SQLite to public access channels. Arrows represent data flow; validation layers are independent checks.](figures/14-provenance-pipeline.pdf){width=94%}

The old report described data values as “exactly as the CIA published them.” That wording obscured known transformations and documented exceptions. The defensible claim is narrower: the project preserves source inputs, retains original field names and full field text as database content after documented normalization, and makes corrections inspectable. A researcher can reconstruct a disputed value against the raw source. The published May comparison supports substantial agreement for its tested snapshot but does not prove universal byte identity.

## Specific failure modes and repairs

The 1996 text source truncated seven entries. The project restored them from a separate archived CIA original text capture. A later validation script used a simplified repair that did not reproduce the published repair's field shape, producing missing and extra keys in its comparison. A validator can disagree with a database because its reconstruction differs from production ETL, even when the raw inputs exist. A corrected rerun is needed before an exact match claim. [Validation report](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/VALIDATION.md).

In the 2008 HTML archive, a duplicate Serbia source page produced collisions when the validator used a country-and-field key. The canonical SQLite snapshot had been deduplicated. The comparison classified 229 “content differences” in that year, but the validation discussion says the collisions arise from the duplicate and the key design. A rerun should use a multiset or stable source-row identity that can distinguish duplicate entries and explicitly account for curated removals. [L3 report](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/L3_REPORT.md).

HTML decoding is another source of false differences. The May validator decoded some HTML with replacement errors, while the production pipeline performed additional encoding repair. The validation report attributes 261 content differences across some 2006–2017 years to this discrepancy. This is evidence about comparison code and its baseline, not proof that every future extraction has no encoding defects. A robust rerun needs the same decoding and post-processing path as production and should still inspect remaining mismatches individually. [Validation report](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/VALIDATION.md).

The September entity audit found a different class of failure. Substring matching and guessed two-letter codes attached 34 historical edition records to the wrong canonical entities. The at-sign parser also let Zimbabwe's 1998 entry absorb 176 glossary rows from the book's back matter. The repair added reviewed aliases, an explicit section stop, classification checks, and tests. These are not cosmetic label changes: a wrong entity link can contaminate a time series while the field text itself is intact. [Entity audit](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ENTITY_INTEGRITY_ISSUE_38.md).

## A bounded local structural observation

The April local chart snapshot contains two 2008 Serbia field rows whose CountryFields.CountryID differs from the CountryID on their referenced CountryCategories row. Both referenced IDs exist, so a basic foreign-key check would not find this cross-table ownership mismatch. The two fields are “Population below poverty line” and “Economic aid - recipient” (FieldIDs 220341 and 220368). The evidence extraction script records the exact query and IDs. This finding is **only about the April local snapshot**. It has not been checked against the October live database and belongs in a release-candidate relational-integrity audit rather than a claim of a current live defect.

## What a transformation log should preserve

Each source-to-row step should retain an inspectable reason: source file and edition, country marker, category boundary, original field label, full source content or recoverable location, normalization rule, and any later repair. The manifest gives file-level provenance; row-level content and fields give database traceability; validation reports show aggregate reconstruction. There is still a gap between a normalized SourceFragment and an exact byte offset in the raw publication. The report does not treat that column as an exact citation.

Rebuilding should be deterministic under a named code commit and input manifest. If an output changes, the build should identify whether the cause was new source input, a parser change, identity mapping, field-name mapping, or curation. These categories have different interpretive consequences. A corrected parser may reduce stored row counts while improving fidelity; the September deletion of glossary material is an example.

# Data model and query semantics

## Core relational design

The local SQLite snapshot has six main data tables: MasterCountries, Countries, CountryCategories, CountryFields, FieldNameMappings, and FieldValues. A canonical entity in MasterCountries can have many edition entries in Countries. An edition entry has categories and fields. FieldNameMappings connects historically varying original names to canonical labels for cross-edition retrieval. FieldValues derives typed components from full text. SQLite also has an FTS5 index for field-content search. The downloadable schema and scripts are the source for this description; the local chart snapshot was queried read-only. [Database schema](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/DATABASE_SCHEMA.md).

| Table | Grain | Why it exists |
|:--|:--|:--|
| MasterCountries | One project canonical entity | Links historical source entries across editions and records classification. |
| Countries | One source entry in one edition | Preserves year, source code, and source name. |
| CountryCategories | One section of an entry | Preserves the source's category structure. |
| CountryFields | One field of an entry | Stores original label and full text content. |
| FieldNameMappings | One original label | Provides canonical name, mapping type, and review status. |
| FieldValues | One parsed sub-value | Supports numeric and text queries while retaining a link to the parent field. |

The model is intentionally not a single wide country table. A wide schema would need many sparse columns and frequent migrations as the CIA changed labels. The field-row model preserves the publication's open-ended vocabulary and makes source text the central stored record. The cost is that a comparative numerical query must select a field, choose a defensible mapping, parse units and dates, and handle missing observations. A convenient join is not proof that two historical values measure the same construct.

The local snapshot contains 284 canonical entities, 9,535 edition entries, 83,682 categories, 1,071,489 field rows, 1,132 mapping rows, and 1,778,669 parsed sub-values. These numbers describe that one local file, whose SHA-256 and extraction SQL are in the reproducibility appendix. The current public site reports different entity and field totals after later repairs. Counts from the two states should never be mixed in a denominator.

## Canonical labels are retrieval aids

The mapping table records seven broad mapping types: identity, dash normalization, known rename, consolidation, country-specific, noise, and manual. In the April snapshot, 1,132 original labels are represented; 355 are tagged country-specific, 310 noise, 185 identity, 162 rename, 64 dash-format, 49 consolidation, and seven manual. These are **distinct label counts**, not field-row percentages. They say how the mapping table classifies names; they do not establish that every name decision is semantically correct. [Field evolution](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/FIELD_EVOLUTION.md).

![Counts of distinct original field labels by mapping type in the April local SQLite snapshot. Counts sum to 1,132 mapping rows.](figures/08-mapping-types.pdf){width=91%}

Mappings improve discovery. A researcher may want to find versions of a population or communications field despite changes in punctuation or names. But consolidation can merge labels with different scopes, and a short label such as “Branches” can depend on category context. The methodology itself notes that some 1990s field names are ambiguous and that noise heuristics can classify legitimate-looking material. A cross-year analysis should inspect the original label, category, value text, unit, and estimate date, not just the canonical name. [Known limitations](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/METHODOLOGY.md).

Field mappings should be understood as a second layer alongside preserved original labels. If the CIA renamed a field, a query can use the canonical label to retrieve both periods, but the interpretation remains a research decision. If the CIA split one measure into fixed and mobile components, summing or substituting them would need explicit rules. If a field's unit changes, the content must be converted or presented separately. Mapping labels enable candidate joins; they do not license mechanical comparison.

## Sub-values are derived records

The FieldValues layer identifies candidate numeric and text parts within a full source field. It stores a parent FieldID, subfield label, numeric value if parsed, units, text value, estimated date, rank, source fragment, and IsComputed flag. The parent CountryFields row remains the record to inspect when an analytical extraction looks surprising. The local snapshot contains 1,778,669 FieldValues rows, of which 640 have IsComputed = 1. Computed rows are explicitly identified because an arithmetic value formed from neighboring source text is not itself a directly quoted CIA value. [Structured parsing design](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/etl/structured_parsing/DESIGN.md).

![Stored field rows and derived sub-value rows by edition in the April local SQLite snapshot. The layers are not additive and a changing ratio can reflect parsing design.](figures/09-field-values.pdf){width=94%}

![Share of parsed sub-value rows with non-null NumericVal by edition in the April local SQLite snapshot. This is a parser coverage measure, not a share of the Factbook that is inherently numeric.](figures/10-numeric-share.pdf){width=94%}

The share of sub-values with NumericVal is useful for assessing the parser's output, but it must not be called the share of the original publication that is numerical. Narrative fields may contain numbers that should remain narrative; a population field may contain multiple dated or qualified figures. Units and estimate dates can change. A researcher should keep non-numeric rows and missing values distinct from zero, preserve source qualifiers, and use the parent field when presenting a result.

![Count of FieldValues rows explicitly marked IsComputed = 1 by edition in the April local SQLite snapshot. Years absent from this figure have zero flagged rows in this snapshot.](figures/11-computed-values.pdf){width=88%}

The SourceFragment column is useful for navigating from a typed value toward the parent text. It is not a guarantee of verbatim raw bytes. The May L1 test looked for 200 randomly sampled fragments per edition as exact substrings in the corresponding source files. Only 3,991 of 7,200 sampled fragments, or 55.4%, matched literally. Inserted pipe boundaries, reattached HTML labels, flattened JSON keys, and joined spans explain why an exact substring test is poorly aligned with the stored fragment's purpose. A reader should trace the normalized fragment through the full field and raw source for a disputed claim. [L1 report](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/VALIDATION.md).

## SQLite and the legacy SQL Server mirror

The May raw-source review selected SQLite as canonical for the released dataset. It documented differences from a legacy SQL Server mirror, including the absence of the FieldValues table there and text-year content drift. The L3b comparison reported 1,063,060 matching records against 1,071,601 SQL Server rows, or 99.20% by its method. The example of 1990 Madagascar shows source text and SQLite agreeing where the SQL Server mirror differs. This report does not assert current SQL Server parity. Future synchronization requires a fresh row-level test, and a database user should identify which copy a query used. [L3b report](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/L3B_REPORT.md).

# Historical coverage and what it means

## Thirty-six editions do not imply a fixed roster

The local snapshot has 249 edition entries in 1990 and 260 in 2025. The count changes through time, reaching 274 in 2006 in this file. Those changes are not a direct count of sovereign states or a stable denominator for world indicators. The CIA's Factbook included territories, dependencies, special entities, and historical polities, and the project's identity mapping may later be corrected. The live archive's 285 entities are canonical identities across the whole collection, not the number of entries in the final edition.

![Country-year entry count by edition in the April local SQLite snapshot. The line measures source entries and is not a sovereignty count.](figures/02-country-years.pdf){width=94%}

The 2025 edition has 260 entry rows in the local snapshot. This is the same count used in the site's independently preserved final-snapshot comparison, but the matching count alone does not establish equivalence. The site's documented comparison states that 260 country codes and 32,594 fields were compared with a Mozilla Data Collective preservation copy, with zero content differences. That check is specific to the final snapshot and its comparison rules. [Final Snapshot Verification](https://worldfactbookarchive.org/about).

## Field totals encode editorial and technical changes

The local snapshot grows from 15,750 field rows in 1990 to a peak of 39,714 in 2021, then has 32,594 in 2025. It would be wrong to narrate the line as steady growth of “facts known about the world.” Fields are record units defined by the source format and extraction. A category can be reorganized; a nested item can become a separate label; an entire field can be omitted from a later edition; a parser can split or combine material differently. The May L3 per-year table records the same DB field totals for its tested snapshot.

![Stored field rows per edition in the April local SQLite snapshot. This is a database content measure, not a measure of global information or observation frequency.](figures/03-field-rows.pdf){width=94%}

The middle of the per-entry distribution also changes. The accompanying figure uses the median and 25th–75th percentile of field rows over all source entries in each year, including territories and special entities. It controls somewhat for the number of entries but still reflects source template and parser shifts. The chart is descriptive; it does not test whether a field in 1990 is comparable to a field in 2025.

![Median and middle 50% of field-row counts per country-year entry, April local SQLite snapshot. Each year's roster is the source roster for that edition.](figures/04-entry-distribution.pdf){width=94%}

Distinct original field-label counts show abrupt changes in some text years, especially 1994. The local 1994 snapshot has 518 distinct labels versus 122 in 1993 and 305 in 1995. The methodology documents that some older formats exposed government bodies and subfield labels as apparent fields. The chart is a diagnostic of label structure and parser output, not evidence of a sudden increase in substantive CIA topics. A comparison that depends on a new or vanished field needs a source inspection around the boundary. [Methodology](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/METHODOLOGY.md).

![Distinct original field labels per edition in the April local SQLite snapshot. Historical parser and publication layout changes affect this measure.](figures/05-field-names.pdf){width=94%}

## Final-edition category composition

The April snapshot's 2025 entry data has 32,594 fields across 13 category titles. “People and Society” contributes 7,463 rows, “Economy” 6,406, “Government” 5,636, and “Geography” 4,638. The smallest categories are not necessarily less important; some apply only to a subset of entries, and a single field can contain long text. The full category table in the appendices includes the number of entries where each category appears.

![Field-row counts by source category in the 2025 edition of the April local SQLite snapshot. Counts sum to 32,594.](figures/06-categories-2025.pdf){width=94%}

Category names themselves are historical data. A broad chart across all years that collapses categories by current title would require a documented category mapping. This report therefore shows a single-edition category composition and leaves cross-era category harmonization as a separate analytical task. The chosen snapshot had not yet received the September identity repair, but the repair concerned 1998 glossary material and entity links; the 2025 field count independently matches the final-snapshot comparison's reported total.

## Unequal entity histories

In the April local snapshot, 214 of 284 canonical entities have entries in all 36 distinct edition years. Others have shorter spans because a polity changed, an entry was introduced, or a source-specific identity needed resolution. The figure counts **distinct years per canonical entity**, not raw linked rows, because the pre-repair snapshot can have more than one row attached to an entity in a given year. The September audit changed several links; this figure is not a current live roster report.

![Distinct edition-year coverage per canonical entity in the April local SQLite snapshot. Years are deduplicated within an entity; later identity repairs can change bins.](figures/07-entity-editions.pdf){width=89%}

For historical analysis, the choice of population matters. A “full archive” total may include an entity that existed for only one edition; a fixed-panel comparison of 1990 and 2025 excludes it. A series for a modern country can conceal a predecessor relationship if the analyst joins by current name without checking the old entry. The archive's canonical ID is a useful starting point, but source title, geography, and historical context decide whether the link is appropriate for a specific question.

# Entity identity, classification, and repairs

## Linking names across time

A source entry has a contemporaneous name and code; the project also assigns a canonical identity for navigation and cross-year grouping. That assignment is interpretive. Names can change, political entities can divide or dissolve, and short codes can collide. The historical source name should remain visible even when a canonical name helps users find the record. The project records entities such as dissolved states and special territories rather than forcing them into a current-country list. [Entity methodology](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/METHODOLOGY.md).

The September audit demonstrates why exact identity rules matter. Historical Cape Verde entries had been linked to Canada; Isle of Man entries to Madagascar; Palau-era Trust Territory entries to Paraguay; the Iraq–Saudi Arabia Neutral Zone to Iraq. Other mislinks affected South Georgia, Cocos (Keeling) Islands, Wake Island, and several Saint-named territories or states. In total, 34 deployed edition links were corrected. This is a concrete repair of source-to-entity relationships, not evidence that all historical links are now universally correct. [Entity audit](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ENTITY_INTEGRITY_ISSUE_38.md).

The audit describes a safer loader rule: reviewed exact aliases resolve known historical names, while unknown names stop the import rather than falling back to a substring guess. This is a generalizable archival design choice. Silent fallback converts uncertainty into false confidence. Explicit unresolved identity records can be investigated with source text and a documented decision. The same principle applies to field-name mapping and category classification.

## Classification is a research aid

The archive's EntityType field distinguishes sovereign, territory, freely associated, disputed, dissolved, crown dependency, special administrative, Antarctic, and miscellaneous categories. These labels support browsing and filtering, but they summarize complex political facts and can be time-sensitive. The September audit found Georgia and Zimbabwe incorrectly typed as territories in the deployed database, and Cook Islands and Niue incorrectly typed as territories rather than freely associated. It used source fields and official references to correct the cases. [Entity audit](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ENTITY_INTEGRITY_ISSUE_38.md).

A classification should be tied to its evidence and effective time. A country that is a UN member today may have a different historical source entry in an earlier edition; an administering relationship may change. The canonical entity label is a present-day retrieval convenience unless the schema explicitly records temporal classification. An analysis of historical sovereignty or recognition cannot take a single current EntityType value as a year-by-year fact.

## The Zimbabwe 1998 back-matter error

The 1998 parser treated a book section boundary as continued Zimbabwe content. The result was 176 glossary or appendix rows and a glossary preamble in the Illicit drugs field. The later repair removed the 176 rows, trimmed the preamble, and removed 153 derived values associated with the contaminated fields while retaining the two genuine Transnational Issues fields. On a copy of production, the documented field total changed from 1,071,489 to 1,071,313. The live website's 3 October field total matches that repaired count. [Entity audit](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ENTITY_INTEGRITY_ISSUE_38.md).

This case shows why a high aggregate match rate does not eliminate concentrated local errors. A publication boundary mistake affects one entry, but it can generate many plausible-looking field rows and search results. The right regression test checks a parser stop marker, the expected legitimate fields, and absence of back-matter content. A global field count alone might even appear to improve when bad rows are added.

## Repair practice and residual uncertainty

The audit's repair workflow was dry-run by default, required a new full SQLite backup to apply, and used a transaction. It checked for conflicting identities, duplicate target editions, and unexpected glossary content. On a production copy, SQLite quick-check passed, repeat execution made no changes, and the repair introduced no new foreign-key violations. The audit also notes 165 pre-existing foreign-key violations not addressed by that patch. These facts should travel together: a successful targeted repair is not a blanket database-integrity pass. [Audit validation and limits](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ENTITY_INTEGRITY_ISSUE_38.md).

Future release candidates need both ordinary foreign-key checks and semantic ownership checks, such as whether a field's category belongs to the same country-year row. The two mismatches observed in the April local file illustrate the latter. They should be retested on a current release candidate before being described as unresolved defects. The report treats identity repair as an ongoing documented process rather than an event that permanently certifies every record.

# Verification: what was tested and what was not

## A layered evidence model

“Validated” can mean several different things. File hashes test whether an asset matches a recorded byte sequence. Parser reconstruction tests whether specified code can turn specified inputs into database rows. Structural checks test relationships and constraints in the database. Independent preservation comparison tests whether two copies of a source snapshot agree under a defined comparison. A usability check tests whether a person can find and interpret a record. None substitutes for all the others.

| Evidence layer | Question answered | Boundary |
|:--|:--|:--|
| L0 database selection | Which database was the May source comparison judging? | SQLite was canonical for that test; SQL Server drift remained. |
| L1 fragment search | How often was a normalized fragment verbatim in its raw file? | 7,200 sampled rows; exact substring is not an appropriate universal provenance test. |
| L2 SHA-256 manifest | Are the released input bytes the files named by the manifest? | File identity, not correctness of extraction. |
| L3 parser rerun | How many reconstructed rows matched the May SQLite comparison snapshot? | Dated snapshot; difference categories have mixed units. |
| L3b SQL Server comparison | Did the same reconstruction agree with the legacy mirror? | Mirror differed, especially in text years. |
| Final snapshot comparison | Did the final edition match another preserved copy? | One edition, 260 codes and 32,594 fields, not all years. |
| September entity audit | Were specified links, classes, and 1998 rows corrected? | Targeted repair; not a universal entity audit. |

The project benefits from having several independent-looking checks, but their independence must be described accurately. The Mozilla preservation copy is a separate preservation channel for the final CIA snapshot, not an independent census of real-world conditions. L2 and L3 use the project's own released inputs. The SQLite and SQL Server comparison is partly a check of internal copies. Agreement between two representations of the same upstream material supports preservation fidelity, not external truth of every statistic.

## The L1 fragment-sampling result

The May L1 procedure sampled 200 FieldValues rows from each of 36 years and searched for each stored SourceFragment as a literal substring in the matching raw file. It found 3,991 exact matches among 7,200 trials, 55.4%. The result varies by era, with high rates in lightly normalized early text and lower rates in HTML and JSON where structural transformations are common. The year-by-year figure exposes that pattern without turning it into a pass/fail verdict for content accuracy. [Raw-source validation, L1](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/VALIDATION.md).

![Exact SourceFragment substring hit rate by year in the May 2026 L1 sample. Each year had 200 sampled fragments; the test asks for literal equality with raw files and is not a full row-provenance measure.](figures/12-validation-l1.pdf){width=94%}

The raw-to-fragment relationship can include an inserted pipe separator between subfields, a label reattached to a value that was held in a separate HTML element, a JSON key converted to readable text, or several hard-wrapped lines joined. These are reasons a correct derivative can fail literal substring search. They are also reasons the derivative should not be quoted as if it were a raw-source excerpt. A stronger row-level test would use a defined source location and a normalization-aware comparison that records the transformation.

The 2001 text sample had 200 of 200 exact hits in L1. That is reassuring for the chosen fallback source and normalization path, but it remains a sample of fragments. It does not prove that every 2001 field has correct entity and category placement. Likewise, a low exact-hit rate in 2018 does not by itself prove a large content error. The test's denominator, selection, and exact equality rule must stay with any reported rate.

## L2 input identity

The raw-source manifest records SHA-256 for 38 files totaling 2.98 GB. The hash is a reproducible claim: if a future reader hashes the downloaded release asset and obtains the recorded digest, that reader has the same bytes named by the manifest. The manifest also records upstream locations or commits and identifies the 2001 ZIP as non-producing. A source file's presence in a release does not mean it was used in the database; the produced-db-rows flag resolves that ambiguity. [Manifest](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/MANIFEST.json).

Hashes are particularly important for year-specific JSON. A floating branch reference could move, while an exact commit and a released ZIP can be recovered. For archived HTML, a Wayback URL can identify a capture, but a local release asset with a digest protects against later retrieval differences. The report does not assert that every upstream path remains live today; the packaged source and recorded digest are the reproducibility baseline.

## L3 reconstruction and the arithmetic correction

The May L3 runner re-parsed all 36 released edition inputs in memory and compared resulting country/field/content records with the then-current SQLite CountryFields rows. It reported 1,070,747 matching rows and 1,071,489 database rows. Dividing those numbers gives 99.93075057%, which rounds to **99.93%**, not the original 99.94%. This correction is arithmetic. It does not change the underlying files or rerun the validator. [L3 report](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/L3_REPORT.md).

![Matched rows divided by database rows for each edition in the May 2026 L3 report. The 1996 and 2008 bars highlight reported repair and duplicate-source complications. A high fraction is not an exact zero-residual claim.](figures/13-validation-l3.pdf){width=94%}

The L3 report lists 261 content differences, 575 missing items, and 41 extra items. These numbers cannot be naively added to 1,070,747 to reconstruct the database total: the validator counts matches in rows, content differences using a key collision rule, and missing or extra items in distinct keys. The published explanation groups most observed disagreements into encoding, 1996 repair shape, and 2008 duplicate Serbia behavior. Those explanations are plausible and source-backed, but a corrected parser rerun with consistent row accounting is required for an exact residual. The report therefore avoids “zero true mismatches,” “100% provenance,” and universal “bit-perfect” language for the full 36-edition database. [Validation report](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/VALIDATION.md).

The per-year L3 table is informative. Most years show exact reported row equality under its comparison. The 1996 row shows 20,523 matches against 21,116 database rows, with the repair-shape issue. The 2008 row shows 30,526 matches against 30,643 database rows, with duplicate-source key collisions. Some 2006–2017 HTML years have small content differences attributed to validator decoding. The table is reproduced in the appendices for inspection. It should not be condensed into one all-years percentage without these cases.

## Final edition and entity audit

The website reports a 12 May 2026 comparison of its final snapshot against a Mozilla Data Collective preservation copy: 260 country codes on each side, 32,594 fields compared, and zero content differences. The zero is the result for that comparison scope. It should be described as final-edition content agreement with a separate preservation copy. It does not certify every prior edition or every numeric value against the world. [Final Snapshot Verification](https://worldfactbookarchive.org/about).

The September audit is a later, different evidence layer. It inspected deployed entity classification, historical links, and Zimbabwe's 1998 glossary contamination, then applied targeted repairs with a backup and transactional checks. Its production-copy outcome explains why the live field count on 3 October is 176 below the May database row count. It also says the database had pre-existing foreign-key violations outside that repair. A reader should use the audit to understand those specific corrections and should not substitute it for a fresh full-source comparison. [Entity audit](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ENTITY_INTEGRITY_ISSUE_38.md).

## A release-candidate validation sequence

For a new public data release, the most useful sequence is to freeze an exact candidate database and record its hash; verify raw input hashes; run all parser and repair steps under a named code commit; compare rows using a consistent multiset or stable source identity; inspect any residual differences; run structural and semantic ownership checks; then verify exported packages and the deployed website against that candidate. The sequence should report counts at each gate. Reusing the May percentage after a later repair would hide whether the repair changed the comparison baseline.

A candidate report should also state what was not checked. A checksum does not independently validate an estimate; a final-edition comparison does not cover 1990; a row match does not certify an entity taxonomy; a working website does not prove an offline app bundle contains the same revision. This discipline makes a research user more confident because the claim can be tested, rather than because a single large accuracy percentage looks impressive.

# The website as a research access layer

## From source record to readable entry

The public research website presents the database in forms suitable for browsing and investigation. The archive directory exposes editions and entities; country pages organize original fields by category; search finds source text; comparisons and charts help users locate changes. The site is implemented as a separate FastAPI and Jinja2 application backed by SQLite, with a full-text index for search. The repository's public README describes these surfaces, while the live website supplies the current reader experience. [Archive README](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025); [live archive](https://worldfactbookarchive.org/archive).

A web presentation is an interpretation layer. It can format numeric tokens, choose chart axes, truncate long values, or map names. Those operations help exploration but should lead back to the full field and source edition. A result card that names a canonical field is not a substitute for its original label. A trend line should carry a source year and unit rather than silently using the edition label as the measurement date. Missing editions or unavailable parsed values should appear as gaps, not as zeros.

The archive's navigation addresses different research questions. Browsing answers “what did the selected edition say about this entry?” Search answers “where does this term occur?” Field exploration answers “which entries have a candidate field?” A ranking or scatter chart answers a narrower numeric question after a field parser, unit, and cohort have been selected. Users should not treat all these modes as equivalent evidence. The closer a view gets to an analytical claim, the more it needs visible scope and original text.

## Analysis, maps, and adjacent collections

The website contains Factbook-based analytical views such as trends, rankings, comparison, change detection, and mapping. It also hosts broader research material, including a geopolitical atlas, CIA maps, a Studies in Intelligence reading area, and a World Leaders database. Some of those are separate datasets with different acquisition dates and methods. Their presence on the same domain does not make them part of the 1,071,313 live Factbook field total. [Archive README](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025); [research site](https://worldfactbookarchive.org/).

This separation should be visible in the report and user interface. A country Factbook field and an independently gathered missile-site layer may share a map, but their authority, update schedule, and precision differ. The Factbook is a retired CIA source; an OSINT layer can continue to change. A combined visualization should label each layer and avoid implying that the CIA published a later map or facility record as part of the Factbook.

## Exports and analytical responsibility

CSV, Excel, PDF, and database access support further work. An export preserves utility only if it also preserves enough context: edition, entity, original field label, field content, parsed sub-value or calculation method, unit, and source year. A flat numeric column alone can strip qualifiers such as “est.”, “NA”, or a definition note. The repository README explains that some numeric exports parse values at download time rather than reading a universal stored Value column. Such an export should be treated as a derived analytical representation. [README, database notes](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025).

The website can make an analyst's first pass faster, but it cannot decide whether two values are definitionally comparable. For any result used in publication, the analyst should inspect several source records, verify units and dates, state a population and denominator, and cite a named archive edition or release. The final section of this report gives a repeatable record-level verification path.

# The offline companion app

## Product role and data boundary

The companion app is a separate access channel for the Factbook archive. Its published 1.4.1 release says the 1990–2025 archive, CIA maps, search, Query & Dashboard, Border Explorer, and games are bundled for offline use. The Apps page lists iPhone/iPad, Android, macOS, and Windows distribution paths and says the full archive works without an account or network. The app uses a Flutter codebase and an on-device SQLite database, according to the local app source and public product description. The web site's separately sourced OSINT collections are not part of that offline Factbook bundle. [Apps page](https://worldfactbookarchive.org/apps); [release 1.4.1](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/releases/tag/apps-v1.4.1).

Offline access changes the reliability question. A web page can show the server's latest database after a deployment; an installed app has a bundled revision that may differ until an app update. The app's About & Sources view should identify its installed archive revision and counts. The source content stopped being updated by the CIA, but local parser and identity corrections can still produce new archive revisions. “Offline” does not mean “data corrections are impossible” or “every installed copy is identical.” App version, package build, and dataset revision should be recorded separately.

## What is available in 1.4.1

The direct-release page lists four downloadable packages: an Android APK of 510,272,121 bytes, a macOS DMG of 455,933,203 bytes, a Windows portable ZIP of 433,574,304 bytes, and a Windows MSIX submission package of 463,187,146 bytes. The macOS package is described as signed and notarized. The GitHub release provides SHA-256 values for all four. These package sizes are not comparable measurements of runtime performance or database quality; packaging formats and platform binaries differ. [Release 1.4.1](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/releases/tag/apps-v1.4.1).

| Platform or channel | Public 3 October evidence | Interpretation |
|:--|:--|:--|
| Android direct | APK in the 1.4.1 GitHub release and Android download on the Apps page | Direct package available; installation requirements are on the Apps page. |
| macOS direct | Signed, notarized 1.4.1 DMG in the GitHub release | Direct package available for listed Intel and Apple silicon baselines. |
| Windows direct | Portable 1.4.1 ZIP in the GitHub release and website route | Direct package available; unzipped portable delivery. |
| Windows MSIX | Submission package in the release | An asset exists; this does not prove Microsoft Store certification or publication. |
| iPhone and iPad | App Store path on the Apps page | Store-distributed mobile channel; its version must be checked separately. |

The 1.4.1 release note also describes an Android search improvement on devices without SQLite FTS5 support. This matters because an offline product cannot assume identical database capabilities on every target device. A fallback search path can preserve core lookup access where a preferred index is unavailable. The existence of a release note is not a benchmark of search speed or universal device compatibility; those require platform testing. [Release 1.4.1](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/releases/tag/apps-v1.4.1).

## Web and app parity should be stated by feature, not slogan

The app and website share the Factbook archive's historical source scope, but their data revision and tools can differ. The app is designed around offline reading and bundled analysis; the website hosts additional online collections and services. The user's task determines which surface is appropriate. For a field citation, either can expose the source, but the reader should record the database or app revision. For a live OSINT layer, the website's separate source information is necessary. For an airplane or field setting without network access, the app's bundle is the available channel.

The distinction also prevents inflated claims. A product page saying “full archive” refers to the Factbook collection, not all content reachable on the website. A direct GitHub release proves that packages were published there; it does not prove every app store has approved the same build. A store listing proves a distribution path, not that a specific installed user is on the latest dataset. A rigorous report can state these differences without diminishing the app's main contribution.

## Updating an offline archive

Because the CIA source is retired, content updates now chiefly concern extraction corrections, identity links, search behavior, maps, and product features. An offline app package should carry a documented dataset revision, database hash, and schema compatibility rule. A data correction should be validated against the canonical archive, built into each platform package, and checked on clean install and upgrade paths. These are release-process recommendations grounded in the documented September repair and the app's offline architecture, not claims that a particular store build has completed every check.

A useful parity check compares an app-bundled sample with the named canonical SQLite release: entry counts, final-edition row counts, selected known fields, the corrected historical identity cases, and a search query under both FTS and fallback paths. This would tell a researcher whether a discrepancy is a source correction, an app conversion issue, or simply different installed revisions. It should be documented per package rather than inferred from matching version labels.

# Research workflows and worked methods

## A source-first path for one historical field

Suppose a reader wants to cite what the 1990 edition said about a particular territory's government. The safe starting point is the **source entry as printed in that edition**, not a current canonical profile label. The reader selects 1990, finds the historical name, records the original category and field title, and reads the entire field text. The raw-source manifest then identifies the 1990 text asset and SHA-256 digest. The reader can locate the same entry in the released text and note any normalization between the raw line and the database's display. The result can be cited with edition, source title, field, release asset, and access date. [Raw-source manifest](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/MANIFEST.json).

If the user instead begins at a current canonical entity page, the MasterCountries link helps find candidate historical entries. The September identity audit shows why the candidate must be checked. An old Cape Verde source record incorrectly linked to Canada would yield a false longitudinal country series even though the original text row looked legitimate. The corrected alias table is evidence of repair, but the researcher's field-level citation should still use the source's contemporaneous name and the precise edition. [Entity audit](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ENTITY_INTEGRITY_ISSUE_38.md).

The output of this workflow is a statement about what the 1990 Factbook published. It is not a statement that a government or boundary was in fact as described, unless independent sources support that conclusion. The distinction matters most for disputed entities and rapidly changing political labels. An archive preserves a historical source's perspective; it does not retroactively make every source description neutral or current.

## Comparing a field across editions

A trend query begins with a candidate canonical field, but the analysis should select the original labels actually present in each edition and inspect how the CIA defined them. The unit can change, a field can split, or the reported estimate year can lag the edition. A useful extraction table contains: edition, source entry, original field label, full text, parsed value, unit, printed estimate year, and a comparability note. A trend line should include only observations that meet the same definition, or visibly separate regimes when they do not.

For example, a communications series may encounter separate fixed-line and mobile fields in later years where an older edition had a single telephone-related label. Combining them into one line would require a documented definition and possibly a new denominator. A field-name mapping can find the candidate rows, but cannot settle that methodological choice. The repository's field-evolution guide documents renames and consolidations as navigational mappings rather than data rewriting. [Field evolution](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/FIELD_EVOLUTION.md).

For an apparent year-to-year jump, inspect at least the preceding and following source text and its estimate years. An edition change from 2020 to 2021 might also coincide with a change from HTML parsing to JSON, a new field layout, or revised source content. The observed change can be real, editorial, or technical. A causal claim about a country's conditions would require external time-aligned evidence beyond the archive's extraction.

## Working with the final 2025 edition

The final-edition workflow has two extra checks. First, treat the edition as the project-labeled 2025 source snapshot captured in January 2026; do not assume a row tagged “2025” reports a 2025 measurement. Second, use the site's documented comparison to the Mozilla preservation copy as a check of final-snapshot content agreement within its 260-code, 32,594-field scope. This does not replace checking a disputed field's source wording, but it strengthens confidence that the final snapshot was preserved without content drift under that comparison. [Final Snapshot Verification](https://worldfactbookarchive.org/about).

If a reader finds a 2026–27 commercial book, the citation should not automatically change the archive edition to 2026. The book has its own publisher, date, ISBN, pagination, and possible editorial packaging. The archive has an independently named digital snapshot and record identifiers. To claim that a particular paragraph or map is identical across the two, a researcher must have access to both and compare them. Without that check, the defensible statement is that the commercial title exists after the CIA stopped publishing the online Factbook, while this archive ends with the final CIA digital edition labeled 2025.

## Building a reproducible multi-entity analysis

A comparative study should declare its population before plotting. “All entities in the 2025 source,” “all sovereign entities under a particular classification,” and “entities appearing in both 1990 and 2025” are different populations. Their denominators can differ and may change after identity repairs. The SQL used for the chart should join country-year entries through the intended identity table, inspect duplicate rows within an entity and year, and include an explicit rule for missing observations.

Numeric parsing should be field-specific. A general regular expression can extract the first number from a narrative phrase while missing a later year, a range, or a unit qualifier. If a percentage is compared with a count, the chart must convert or separate them. If an indicator is a rate, an aggregate across entities needs valid numerators and denominators rather than an unweighted mean of country rates. If no common denominator is available, the output should remain a comparison of source entries rather than a world total.

The report's own structural charts provide an example of this discipline. They use counts of database rows and explicit edition years; they do not extract a real-world indicator. The 2025 category chart covers one edition to avoid a category-harmonization problem. The entity-history figure counts distinct years, rather than raw records, because some pre-repair entities had multiple linked rows in one year. Each chart's caption states the snapshot and measurement unit, and the query is retained in evidence.json.

## Teaching and exploratory use

The archive can support lessons about how reference works change: students can compare how an entry's wording, category placement, or field availability differs across editions. They can also see the difference between a historical source statement and a present-day fact. The offline app extends this access to settings with unreliable connectivity, while the website's broader tools can support guided exploration. These are plausible uses of the available interfaces, not measured claims about learning outcomes or usage.

For instruction, a good exercise asks for both an analytical view and the original source record. A student might chart an indicator, then inspect two underlying edition pages and explain any mismatch between edition year and estimate year. A second exercise might compare a canonical label with the original labels it gathers. These tasks teach source criticism alongside data manipulation and reduce the risk that attractive visualizations are treated as self-validating.

# Four cases that test the archive's method

## Case 1: a year label is not an estimate year

The final digital edition is the clearest place to see why the three clocks in Chapter 2 matter. A literal search of its 32,594 stored field contents in the April local snapshot finds the text “2025 est.” in 2,423 fields. It also finds “2024 est.” in 4,516 fields, “2023 est.” in 5,683, and “2022 est.” in 4,469. The search finds no “2026 est.” or “2027 est.” tokens in that snapshot. These are **literal token counts**, not a complete classification of every field's observation year. One field can contain several tokens, and the wording can express a date without the exact pattern. The counts are therefore overlapping and should not be summed. The extraction SQL is recorded with the figures.

![Number of 2025-edition fields containing each literal year-plus-estimate token, April local SQLite snapshot. Counts can overlap across years and do not classify all date expressions.](figures/15-final-estimate-tokens.pdf){width=94%}

This distribution is a concrete example of why a 2025 edition is not a table of measurements all made in 2025. The CIA's selected final source included estimates from previous years. A historian can accurately say that the 2025-labeled snapshot *contained* a 2022 estimate; an analyst cannot relabel that number as a 2025 observation merely because it appears on a 2025 page. An export that drops the text qualifier or DateEst field can lose the distinction. A chart with an x-axis labeled only “Factbook year” may then invite a false trend interpretation.

The absence of the exact 2026 or 2027 “est.” token in this one local snapshot supports the narrow statement that these phrases were not present as literal field content under this search rule. It does not prove that no line mentions 2026 in another context, that every 2025 field is up to date, or that the publisher's 2026–27 book is page-identical. The CIA's 4 February 2026 retirement and the archive's January final capture provide the stronger chronology for why the project does not create a distinct digital 2026 or 2027 edition. The commercial book remains a separate artifact with its own bibliographic date.

## Case 2: a legitimate source can require two inputs

The 1996 text edition illustrates that a single year may have a more complex lineage than one filename. The Project Gutenberg text supplied the general edition, but seven country entries were truncated: Venezuela, Armenia, Greece, Luxembourg, Malta, Monaco, and Tuvalu. The project preserved a separate archived CIA original text capture and used it to repair those entries. The raw-source bundle includes both inputs. A researcher who hashes only the Gutenberg file and claims to reconstruct the entire 1996 database will miss the repaired material. [Methodology repair log](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/METHODOLOGY.md); [manifest](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/MANIFEST.json).

The May validator's simplified 1996 repair did not reproduce the production repair's field shape. Its L3 per-year table reports 20,566 re-parsed records versus 21,116 database records, 20,523 matches, 575 keys missing from the reparse, and 41 extra keys. These figures should not be collapsed into “the archive is missing 575 fields.” They describe the validator's reconstruction against the database under its key rule. The published validation narrative attributes the difference to a simplified repair implementation. A new check should run the exact production repair and inspect any remaining differences, preserving the distinction between source absence and comparison-code behavior. [L3 report](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/L3_REPORT.md).

The case suggests a release design: manifest entries should name all source inputs for an edition, identify which files produced rows, and record the repair script and affected entities. The output should retain the repaired field's source locator rather than only a generic “1996” provenance label. When the release is rebuilt, a regression check should compare the seven repaired entries to the archived CIA original, not merely compare the overall 1996 row total. A total can agree even if the wrong fields were included.

## Case 3: duplicate source pages challenge the comparison key

The 2008 archived HTML ZIP contains a duplicate Serbia page. The May rerun generated 30,755 fields for 2008, while its SQLite baseline held 30,643 after deduplication. The L3 output reported 229 content differences associated with Serbia, but the validation report explains that these arise when two source rows share a country-and-field comparison key. The duplicate rows collide and are reported as content differences rather than a clean set of extra source rows. [Validation report](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/VALIDATION.md).

This is a general problem of data grain. A key suitable for querying one normalized row per field may be unsuitable for comparing raw source pages that contain duplicates. A strong source-to-output comparison should first inventory source page identities and row multiplicities, then record the deduplication decision, then compare the canonical rows. It should distinguish an intentional removal from a parser omission. A simple dictionary keyed by country and field can overwrite one duplicate and hide the very condition being tested.

The April local database also has two Serbia 2008 field rows whose parent country ID and category's country ID disagree. Those two rows are a distinct semantic ownership observation, not the same thing as the source duplicate. The mismatch is visible only when the two foreign-key paths are compared. One could have a database with valid references and still attach a field to a category from another row. The report records the exact IDs and limits this finding to the April local snapshot; the current live database was not queried for it.

## Case 4: a publication boundary can produce plausible noise

Zimbabwe's 1998 source entry was followed by back matter. The parser failed to stop at the “NOTES AND DEFINITIONS” marker and absorbed 176 glossary/appendix rows. Some inherited field names and text could appear meaningful in isolation. The September repair removed them, trimmed a contaminated preamble, and kept the two genuine Transnational Issues fields. On a production copy, field rows fell from 1,071,489 to 1,071,313. The live archive displayed the repaired total on 3 October. [Entity audit](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ENTITY_INTEGRITY_ISSUE_38.md).

This is why a field count is not a quality score. The erroneous database had more rows. Removing them made the collection smaller but more faithful to the source's entity boundary. A generic null audit might not flag the glossary rows because they contained nonempty text. A category count might even look healthy. The useful checks are publication-boundary markers, expected genuine fields, absence of glossary headings in the entry, and a source-to-database trace across the transition from the last country to the book's back matter.

Together, the four cases give a practical interpretation of the archive's validation evidence. The source bundle matters because 1996 used multiple inputs; the comparison key matters because 2008 had duplicate source pages; the parser boundary matters because 1998 back matter became fields; and date semantics matter because a final-edition page contains estimates from earlier years. Each case motivates a targeted check. No single aggregate percentage can replace them.

# Limits, uncertainty, and claims policy

## Preservation fidelity is not factual accuracy

The CIA's Factbook entries are source documents. They can contain estimates, editorial selections, terminology, and political classifications that change or are disputed. The archive's goal is to preserve and expose those source documents faithfully enough that a reader can inspect them. A perfect byte match to the CIA source would still not certify that every number was accurate when issued. Conversely, a normalization difference in HTML spacing may not change the substantive value but still needs disclosure when exact wording is claimed.

The report therefore uses “agreement” for a defined source comparison, “correction” for a documented database repair, and “observation” for a live count or feature. It avoids unqualified “100% accurate,” “only archive,” “all fields verified,” and “current world data.” These stronger claims would need evidence the project has not presented. The distinction is especially important in a public executive summary, where a short metric can sound more universal than the test behind it.

## Coverage and comparability

The 36 edition labels are a complete project sequence, but the source within each edition is a selected artifact. The entry roster changes. Categories and field names change. Some 1990s formats blur field and subfield boundaries. The FieldValues parser does not turn every narrative sentence into a reliable number, and a non-null NumericVal can still be unsuitable for comparison if units or dates differ. The charts of row counts explicitly describe database structure, not complete historical coverage of each real-world concept.

Missing values require careful treatment. An absent field may mean the CIA did not publish it in that edition, the entry was omitted from the selected source, the parser did not recognize it, or the field name changed. Those possibilities are not interchangeable. A missing plotted point should remain missing until the analyst identifies the reason. The website and app can help locate candidate records, but neither can infer a substantive zero from absence.

## Provenance and validation limits

The source manifest provides file-level hashes and upstream locations. SourceFragment provides a normalized path from a sub-value toward source text, but the L1 test shows it is often not a verbatim raw-file substring. The L3 parser rerun supports a high degree of source-to-SQLite agreement for the May snapshot, but its comparison uses mixed counting units for residual categories. It was not rerun here against the repaired live database. The final-edition preservation comparison is separate and limited to that edition. These limitations are material and are repeated near the relevant figures and claims rather than hidden in this section alone.

The local SQLite source used for this report was last modified on 8 April 2026 and has a stable SHA-256 recorded in the appendix. It contains 1,071,489 fields and predates the September entity repair. A chart based on it may differ from the current public site even when both are internally correct for their dates. This report did not download a current full production database or rerun the complete raw-source validator. Its local calculations are aggregate read-only queries plus independent arithmetic checks of cited validation numbers.

## Application and distribution limits

The site, data repository, and app are separate release surfaces. A website count can update without a new GitHub data release. A direct-release package can exist before a store approves it. A person may keep an older offline app installed. The report's app feature inventory and 1.4.1 asset list are dated 3 October 2026 and should be refreshed before publication or reuse after a release. The report does not claim store certification or current installation counts.

Website-only OSINT and other CIA collections have their own sources and should not be included in a Factbook completeness metric. Maps bundled in the app are related content with a separate asset count. A future edition of this report could evaluate those collections on their own terms, but their presence in the same product does not expand the CIA Factbook's final dataset.

## Interpretive examples of claims to avoid

“The archive has 1.07 million facts” is convenient but imprecise: the row count is fields, not independently verified facts. “Every Factbook edition is bit-perfect” overextends the final-snapshot comparison and ignores parser normalization. “A 2026–27 book proves a 2027 CIA edition” confuses publisher branding with CIA source chronology. “The app has the whole website offline” ignores separate online collections. “Every country has 36 years” ignores historical entry coverage and identity changes. Each phrase can be replaced with a dated, bounded statement that a reader can verify.

# Stewardship, citation, and next verification

## A stable way to cite the project

The project's concept DOI is [10.5281/zenodo.18884612](https://doi.org/10.5281/zenodo.18884612). It identifies the continuing archive and resolves through versions. For a reproducible analysis, a researcher should also cite the exact database release tag or asset hash, the source edition, entity and original field label, and the access date if using the live service. A version-specific DOI may be appropriate when the analysis explicitly depends on that version, but the concept DOI is the stable general citation for the project. [Repository citation guidance](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025).

The following example format is intentionally descriptive rather than tied to one citation style: “Milkovich, M. CIA World Factbook Archive 1990–2025. Concept DOI 10.5281/zenodo.18884612. Database release [tag/hash], 2025 edition, [historical source entry], [original field label], accessed [date].” Replace bracketed items with the actual record. If the claim comes from the publisher's 2026–27 book, cite that book's ISBN and page instead of treating it as a new archive edition.

For a derived statistic, the citation should travel with the method. State whether the value came from full field text, a FieldValues sub-value, a download-time parser, or a calculation across records. If a cross-year label mapping was used, name the mapping and inspect its original labels. If a chart uses the website, record its filters and date; if it uses an offline app, record the installed dataset revision. A reader needs these details to distinguish a source change from a software change.

## Release evidence that should accompany the next database

The next data release should have a compact evidence package: input manifest and hashes; parser commit and commands; candidate SQLite hash and table counts; corrected source-to-row comparison with a disjoint accounting of all rows; structural and semantic relation checks; a sampled trace from raw source through displayed output; and a list of known unresolved cases. The September repair and the two April-only category ownership mismatches indicate where focused tests should be added. A pass should be reported per check, with the tested candidate's identity.

An app release should name the bundled archive revision, check packages on supported platforms, and keep direct assets and store status separate. A website deployment should verify the live archive totals and sample pages after the deployment, including a corrected historical identity case and the final edition. These are recommendations for a reviewable release process. They are not statements that a new release was made while preparing this report.

## A public reporting rule

Before republishing an executive summary or this longer report, refresh the live website and app-release facts, rerun the candidate-level checks that support any new exact totals, inspect the rendered PDF, and review the claims about the 2026–27 book. The report is currently a local review draft. It does not link itself from the public README or claim that a new edition has been published. The historical March 2026 report remains an unpublished reference because its counts, exclusivity language, and provenance claims were too broad for the evidence now available.

## Closing assessment

The project's central contribution is concrete and inspectable: a 36-edition structured collection, released source files and parsing code, a public research website, and an offline companion app. The May reconstruction, final-snapshot comparison, and September entity repair provide meaningful evidence, each for a defined scope. The most useful next step for a public data-quality claim is a corrected full rerun against the precise current release candidate. Until then, the dated figures and bounded wording in this report describe what has actually been observed and tested.
