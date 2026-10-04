\appendix

# Evidence register and snapshot ledger

The report uses three different data states. The **local chart snapshot** is a read-only SQLite file last modified 8 April 2026. The **May comparison** is the project's reported parser rerun against a 1,071,489-row SQLite baseline. The **live observation** was taken from the public website on 3 October 2026, after a documented September repair. Equal-looking counts between states do not prove byte identity; different counts require their own source explanations. The local aggregate extraction script and its JSON output are distributed with this draft so each figure can be rebuilt without reaching the live site.


| Evidence state | Date or cutoff | Entities / entries / fields | Use in report |
| --- | --- | --- | --- |
| Local SQLite chart snapshot | 2026-04-08 | 284 / 9,535 / 1,071,489 | Figures and annual tables |
| May L3 comparison | 27 May 2026 | 1,071,489 DB field rows | Raw-to-database reconstruction evidence |
| September repair audit | 22 September 2026 | 1,071,313 fields on production copy | Identity and glossary correction evidence |
| Live archive observation | 2026-10-03 | 285 / 9,535 / 1,071,313 | Current public headline |


Local SQLite file size: **737,288,192 bytes**. SHA-256: **abf2cfe54614e568f8faa5af40bf6e00c3117767bde72fd11b5b159c3014a74c**. Its modification timestamp is a filesystem observation, not proof of a release tag. The live entity and field totals came from [the archive page](https://worldfactbookarchive.org/archive); the sum of YearCount came from [the public country API](https://worldfactbookarchive.org/api/countries). The site displayed 36 editions. A public count is time-sensitive and should be refreshed before a later release or publication.

The SQL for every local aggregate is stored under the **sql** key of evidence.json. It opens SQLite in read-only immutable mode and writes only its aggregate JSON output. The charts are built from that output by make_figures.py; no real-world indicator is modeled in the chart scripts.

# Source inventory and edition lineage

The raw-source manifest is the authoritative file inventory for the reported source bundle. It lists **38 files** and **2,981,435,015 bytes**. The table below shows year, file, era, a digest prefix, and whether the file produced database rows. Full SHA-256 values and upstream URLs are in [the manifest](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/MANIFEST.json); a digest prefix alone is not a sufficient integrity check. The corrupt 2001 HTML ZIP remains an archived asset but is not an input to country rows.


| Year | File | Era | SHA-256 prefix | DB rows? |
| --- | --- | --- | --- | --- |
| 1990 | 1990.txt | text | 2198e8efd169 | yes |
| 1991 | 1991.txt | text | 67c7b17456ba | yes |
| 1992 | 1992.txt | text | 8af163b427f5 | yes |
| 1993 | 1993.txt | text | f62230e2bc7c | yes |
| 1994 | 1994.txt | text | 257857b3793e | yes |
| 1995 | 1995.txt | text | 2c13ca59829e | yes |
| 1996 | 1996.txt | text | fb62092d4571 | yes |
| 1996 | 1996_cia_original.txt | text-repair | 6cdcc385d46a | yes |
| 1997 | 1997.txt | text | b0eeb2b4794b | yes |
| 1998 | 1998.txt | text | 9d3c50a4109c | yes |
| 1999 | 1999.txt | text | 09b48764bc43 | yes |
| 2000 | factbook-2000.zip | html | b40283357611 | yes |
| 2001 | 2001.txt | text | f6cbc8017e5c | yes |
| 2001 | factbook-2001.zip | html | eea02eeab9df | no |
| 2002 | factbook-2002.zip | html | 237d65dbfc92 | yes |
| 2003 | factbook-2003.zip | html | 30ba1711e581 | yes |
| 2004 | factbook-2004.zip | html | a943cb26ba57 | yes |
| 2005 | factbook-2005.zip | html | 28ac927e0b36 | yes |
| 2006 | factbook-2006.zip | html | b7b7f686583f | yes |
| 2007 | factbook-2007.zip | html | 44a8df069c39 | yes |
| 2008 | factbook-2008.zip | html | 98de53899101 | yes |
| 2009 | factbook-2009.zip | html | f4749024892a | yes |
| 2010 | factbook-2010.zip | html | 39662d79e57c | yes |
| 2011 | factbook-2011.zip | html | 972f05ca0516 | yes |
| 2012 | factbook-2012.zip | html | 5a59df353345 | yes |
| 2013 | factbook-2013.zip | html | 570ebf04ed22 | yes |
| 2014 | factbook-2014.zip | html | 4b4552745616 | yes |
| 2015 | factbook-2015.zip | html | ef715140b9d0 | yes |
| 2016 | factbook-2016.zip | html | b56e2cc53477 | yes |
| 2017 | factbook-2017.zip | html | 88b43600b057 | yes |
| 2018 | factbook-2018.zip | html | 7a635512ab79 | yes |
| 2019 | factbook-2019.zip | html | 807113734875 | yes |
| 2020 | factbook-2020.zip | html | 1f2e4d359924 | yes |
| 2021 | factbook-json-2021.zip | json | d561220e7cb6 | yes |
| 2022 | factbook-json-2022.zip | json | 2ea403e74d5b | yes |
| 2023 | factbook-json-2023.zip | json | c86dbcf763f1 | yes |
| 2024 | factbook-json-2024.zip | json | 361e88582cf7 | yes |
| 2025 | factbook-json-2025.zip | json | 2e355b6cdf14 | yes |


The table describes released artifacts, not an exhaustive list of every file ever distributed by the CIA or the Wayback Machine. The 1996 source repair requires both the Gutenberg text and the CIA original repair source. For JSON years, the manifest's upstream commits matter more than a branch name that could move. The source timeline figure uses the edition rows actually marked in the local SQLite Countries table.

# Annual archive counts

Each line below describes one local SQLite edition. “Entries” counts Countries rows; “categories” counts CountryCategories rows; “fields” counts CountryFields rows; “labels” counts distinct original FieldName strings in that year. Because these are database records, a change may reflect source editing, extraction, or a later correction. The table is intended for lookup and figure verification, not for inference about the quantity of real-world knowledge.


| Year | Source | Entries | Categories | Fields | Labels |
| --- | --- | --- | --- | --- | --- |
| 1990 | text | 249 | 1,482 | 15,750 | 116 |
| 1991 | text | 247 | 1,470 | 14,903 | 91 |
| 1992 | text | 264 | 1,572 | 17,372 | 136 |
| 1993 | text | 266 | 1,586 | 18,509 | 122 |
| 1994 | text | 266 | 1,575 | 28,633 | 518 |
| 1995 | text | 266 | 1,841 | 19,599 | 305 |
| 1996 | text | 266 | 1,573 | 21,116 | 358 |
| 1997 | text | 266 | 2,126 | 23,405 | 144 |
| 1998 | text | 266 | 1,873 | 23,524 | 204 |
| 1999 | text | 266 | 2,166 | 25,178 | 148 |
| 2000 | html | 267 | 2,344 | 25,724 | 119 |
| 2001 | text | 265 | 2,352 | 27,281 | 132 |
| 2002 | html | 268 | 2,378 | 27,430 | 125 |
| 2003 | html | 268 | 2,380 | 28,676 | 134 |
| 2004 | html | 271 | 2,400 | 28,958 | 142 |
| 2005 | html | 271 | 2,400 | 28,728 | 142 |
| 2006 | html | 274 | 2,338 | 28,962 | 144 |
| 2007 | html | 266 | 2,304 | 29,103 | 147 |
| 2008 | html | 262 | 2,308 | 30,643 | 156 |
| 2009 | html | 260 | 2,307 | 30,818 | 154 |
| 2010 | html | 262 | 2,323 | 30,805 | 154 |
| 2011 | html | 263 | 2,326 | 33,635 | 169 |
| 2012 | html | 271 | 2,552 | 35,192 | 181 |
| 2013 | html | 269 | 2,578 | 36,731 | 185 |
| 2014 | html | 268 | 2,578 | 36,680 | 185 |
| 2015 | html | 268 | 2,578 | 36,870 | 186 |
| 2016 | html | 268 | 2,589 | 36,804 | 184 |
| 2017 | html | 268 | 2,602 | 37,046 | 187 |
| 2018 | html | 268 | 2,645 | 37,285 | 185 |
| 2019 | html | 268 | 2,648 | 37,394 | 187 |
| 2020 | html | 268 | 2,673 | 36,687 | 182 |
| 2021 | json | 260 | 2,900 | 39,714 | 191 |
| 2022 | json | 260 | 2,909 | 37,344 | 186 |
| 2023 | json | 260 | 3,003 | 37,558 | 191 |
| 2024 | json | 260 | 2,990 | 34,838 | 183 |
| 2025 | json | 260 | 3,004 | 32,594 | 182 |


The annual fields column sums to **1,071,489**. Its 2025 line has **260 entries** and **32,594 fields**. The 2008 field total includes two rows whose CountryID does not agree with their referenced category's CountryID in this local snapshot; the extraction script records both IDs. This semantic relationship is not tested by a simple foreign-key existence check.

# Derived value counts by edition

FieldValues rows are derived from parent fields and are not additional original CIA field rows. “Numeric share” is the percentage of FieldValues rows with non-null NumericVal. “Computed” counts IsComputed = 1. The parser and field formats changed; these are output-coverage measurements rather than independent measures of numeric information in the CIA publication.


| Year | FieldValues | Numeric share | Computed |
| --- | --- | --- | --- |
| 1990 | 17,731 | 47.9% | 209 |
| 1991 | 17,932 | 48.4% | 206 |
| 1992 | 20,737 | 47.4% | 225 |
| 1993 | 25,840 | 48.1% | 0 |
| 1994 | 27,840 | 46.4% | 0 |
| 1995 | 29,192 | 48.5% | 0 |
| 1996 | 32,055 | 54.3% | 0 |
| 1997 | 35,291 | 55.6% | 0 |
| 1998 | 35,467 | 55.8% | 0 |
| 1999 | 35,437 | 55.8% | 0 |
| 2000 | 36,392 | 54.3% | 0 |
| 2001 | 32,470 | 56.8% | 0 |
| 2002 | 38,620 | 53.0% | 0 |
| 2003 | 40,797 | 54.9% | 0 |
| 2004 | 40,751 | 55.0% | 0 |
| 2005 | 40,717 | 55.5% | 0 |
| 2006 | 41,978 | 56.1% | 0 |
| 2007 | 41,996 | 55.7% | 0 |
| 2008 | 44,815 | 58.3% | 0 |
| 2009 | 53,015 | 65.8% | 0 |
| 2010 | 53,585 | 65.1% | 0 |
| 2011 | 60,169 | 68.3% | 0 |
| 2012 | 62,800 | 69.8% | 0 |
| 2013 | 69,285 | 71.7% | 0 |
| 2014 | 70,289 | 72.0% | 0 |
| 2015 | 64,675 | 66.7% | 0 |
| 2016 | 65,645 | 66.4% | 0 |
| 2017 | 66,022 | 65.9% | 0 |
| 2018 | 66,247 | 66.8% | 0 |
| 2019 | 66,734 | 67.0% | 0 |
| 2020 | 66,579 | 67.2% | 0 |
| 2021 | 73,573 | 66.6% | 0 |
| 2022 | 78,530 | 68.1% | 0 |
| 2023 | 77,843 | 67.9% | 0 |
| 2024 | 74,506 | 65.4% | 0 |
| 2025 | 72,958 | 64.6% | 0 |


The local snapshot has **1,778,669** FieldValues rows, **1,776,960** non-empty SourceFragment values, and **640** rows explicitly marked computed. The fragment-population count is not a verbatim-source match count. The May L1 exact-substring test had a different denominator and purpose.

# Final-edition category detail and field mappings

The 2025 table is a one-edition composition. A category appears in fewer than 260 entries when it does not apply, was not published, or was not represented by this extraction. “Field rows” counts stored fields, not words or verified facts. The sum reconciles to the 2025 field total. The mapping table describes 1,132 distinct original labels in the April snapshot, not usage-weighted field rows.


| 2025 category | Field rows | Entries with category |
| --- | --- | --- |
| People and Society | 7,463 | 258 |
| Economy | 6,406 | 260 |
| Government | 5,636 | 260 |
| Geography | 4,638 | 260 |
| Environment | 2,341 | 260 |
| Energy | 1,432 | 236 |
| Communications | 1,392 | 260 |
| Military and Security | 1,262 | 257 |
| Transportation | 1,141 | 260 |
| Transnational Issues | 277 | 259 |
| Introduction | 261 | 260 |
| Space | 246 | 71 |
| Terrorism | 99 | 103 |


| Mapping type | Original labels |
| --- | --- |
| country specific | 355 |
| noise | 310 |
| identity | 185 |
| rename | 162 |
| dash format | 64 |
| consolidation | 49 |
| manual | 7 |


The category table groups by category title in the 2025 source. It should not be projected across all years without a category crosswalk. The mapping-type table comes from FieldNameMappings; use count, decision quality, and cross-year semantic comparability are separate questions.

# Validation detail by edition

The first table reproduces the May L1 exact-substring hit percentages from the raw-source validation report. Each year had 200 sampled normalized fragments. The second table reproduces the May L3 reported database row and matching-row counts. L3's residual categories use mixed units and are therefore shown only in the source report rather than being recombined into a false partition here. Both tables are historical results for the May comparison, not new October runs.


| Year | Source | L1 exact hits |
| --- | --- | --- |
| 1990 | text | 97.5% |
| 1991 | text | 97.5% |
| 1992 | text | 80.0% |
| 1993 | text | 81.5% |
| 1994 | text | 82.5% |
| 1995 | text | 80.5% |
| 1996 | text | 87.5% |
| 1997 | text | 86.5% |
| 1998 | text | 82.5% |
| 1999 | text | 80.0% |
| 2000 | html | 52.0% |
| 2001 | text | 100.0% |
| 2002 | html | 51.0% |
| 2003 | html | 48.0% |
| 2004 | html | 56.5% |
| 2005 | html | 47.5% |
| 2006 | html | 54.0% |
| 2007 | html | 45.0% |
| 2008 | html | 47.0% |
| 2009 | html | 43.0% |
| 2010 | html | 43.0% |
| 2011 | html | 44.0% |
| 2012 | html | 44.5% |
| 2013 | html | 43.0% |
| 2014 | html | 47.5% |
| 2015 | html | 44.5% |
| 2016 | html | 52.0% |
| 2017 | html | 42.5% |
| 2018 | html | 14.0% |
| 2019 | html | 14.0% |
| 2020 | html | 22.0% |
| 2021 | json | 40.0% |
| 2022 | json | 31.0% |
| 2023 | json | 43.0% |
| 2024 | json | 35.0% |
| 2025 | json | 35.5% |


| Year | Source | DB rows | Matches | Match / DB |
| --- | --- | --- | --- | --- |
| 1990 | text | 15,750 | 15,750 | 100.00% |
| 1991 | text | 14,903 | 14,903 | 100.00% |
| 1992 | text | 17,372 | 17,372 | 100.00% |
| 1993 | text | 18,509 | 18,509 | 100.00% |
| 1994 | text | 28,633 | 28,633 | 100.00% |
| 1995 | text | 19,599 | 19,599 | 100.00% |
| 1996 | text | 21,116 | 20,523 | 97.19% |
| 1997 | text | 23,405 | 23,405 | 100.00% |
| 1998 | text | 23,524 | 23,524 | 100.00% |
| 1999 | text | 25,178 | 25,178 | 100.00% |
| 2000 | html | 25,724 | 25,724 | 100.00% |
| 2001 | text | 27,281 | 27,281 | 100.00% |
| 2002 | html | 27,430 | 27,430 | 100.00% |
| 2003 | html | 28,676 | 28,676 | 100.00% |
| 2004 | html | 28,958 | 28,958 | 100.00% |
| 2005 | html | 28,728 | 28,728 | 100.00% |
| 2006 | html | 28,962 | 28,960 | 99.99% |
| 2007 | html | 29,103 | 29,102 | 100.00% |
| 2008 | html | 30,643 | 30,526 | 99.62% |
| 2009 | html | 30,818 | 30,815 | 99.99% |
| 2010 | html | 30,805 | 30,801 | 99.99% |
| 2011 | html | 33,635 | 33,635 | 100.00% |
| 2012 | html | 35,192 | 35,192 | 100.00% |
| 2013 | html | 36,731 | 36,731 | 100.00% |
| 2014 | html | 36,680 | 36,680 | 100.00% |
| 2015 | html | 36,870 | 36,861 | 99.98% |
| 2016 | html | 36,804 | 36,798 | 99.98% |
| 2017 | html | 37,046 | 37,039 | 99.98% |
| 2018 | html | 37,285 | 37,285 | 100.00% |
| 2019 | html | 37,394 | 37,394 | 100.00% |
| 2020 | html | 36,687 | 36,687 | 100.00% |
| 2021 | json | 39,714 | 39,714 | 100.00% |
| 2022 | json | 37,344 | 37,344 | 100.00% |
| 2023 | json | 37,558 | 37,558 | 100.00% |
| 2024 | json | 34,838 | 34,838 | 100.00% |
| 2025 | json | 32,594 | 32,594 | 100.00% |


The L3 table's database column sums to **1,071,489**, and its matching column to **1,070,747**. Division gives **99.93075057%**, rounded to **99.93%**. The original validation document's 99.94% headline was a calculation error. The residual detail in L3_REPORT.md describes 1996 repair-shape differences, HTML decoding differences, and the 2008 duplicate Serbia source. A corrected validator rerun against a named new database is needed to establish a disjoint residual count.

# App direct-release asset record

The table below is the 3 October 2026 GitHub direct-release asset inventory. A package's presence in that release does not establish its app-store status. The full SHA-256 values are retained in public_observations.json and the [release note](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/releases/tag/apps-v1.4.1); prefixes are shown here only to keep the table readable. The package byte sizes are distinct platform artifacts and should not be compared as an efficiency ranking.


| Asset | Bytes | SHA-256 prefix |
| --- | --- | --- |
| WorldFactbookArchive-1.4.1+63-android.apk | 510,272,121 | 8e02963c1709b0db |
| WorldFactbookArchive-1.4.1+63-windows-x64.zip | 433,574,304 | 8ee5c3a9d2536995 |
| WorldFactbookArchive-1.4.1+63-windows-x64.msix | 463,187,146 | 57b1a9c9cb4a1bb1 |
| World-Factbook-Archive-1.4.1-macOS.dmg | 455,933,203 | b74faf4dc434a382 |


The Apps page listed iPhone/iPad, Android, macOS, and Windows access when checked. It described 284 bundled CIA maps and a fully offline Factbook experience. The site and app can have different data revisions. A future report should repeat the direct-release and store-listing checks before updating a public version claim.

# Reproduction and research checklist

To rebuild this draft's local aggregate figures, use a SQLite file whose SHA-256 equals the digest in the evidence register. Run extract_evidence.py with an explicit --db path; inspect the generated evidence.json; then run make_figures.py and the PDF builder. The extraction script opens the database read-only and records its SQL and source hash. A different file hash may be a valid newer database, but its figures must be relabeled and revalidated before reuse.

~~~text
python docs/report_full_2026/extract_evidence.py --db PATH_TO_LOCAL_FACTBOOK_DB
python docs/report_full_2026/make_figures.py
python docs/report_full_2026/make_appendices.py
python docs/report_full_2026/build_full_report.py
~~~

For a field-level claim, record these items: edition label; source file and hash; source entry title and code; original category and field label; full source wording; database release or app dataset revision; estimate year and units; transformation or mapping rule if used; and access date. For a multi-entity chart, add the population rule, exclusions, SQL, parser version, denominator, and treatment of missing values. If a statistic comes from a publisher's 2026–27 book, cite that book's page and ISBN and do not silently insert it as a new CIA digital edition.

The research trail should be recoverable in reverse. A reader starts from a displayed claim, opens the parent field and edition, checks a source file named by the manifest, and resolves any normalization through parser rules or a repair note. The reverse path matters because a chart is only a convenient summary of its source rows.

# Claim revisions and remaining verification

The unpublished March 2026 report supplied a broad structure for this replacement but is not used as authority for current counts or validation. The table below identifies material language changes so reviewers can see why the new report is more precise.


| Earlier wording or gap | This report's treatment |
| --- | --- |
| Only publicly available archive | Describes concrete features; makes no exclusivity claim. |
| 100% provenance or universal accuracy | Separates hashes, parser agreement, final-snapshot comparison, and unresolved residuals. |
| 281 entities and 1,071,603 fields | Uses dated live and local counts with explicit snapshot boundaries. |
| No companion app | Includes offline app scope, 1.4.1 direct assets, and distribution limits. |
| Version-specific DOI as general citation | Uses concept DOI and exact release tag when needed. |
| 2026–27 title omitted | Explains commercial book label, final CIA 2025 digital edition, and lack of page comparison. |


Before this draft is published or treated as a release note, three questions remain: (1) rerun raw-to-row validation with corrected residual accounting against the intended current database; (2) test the April-only semantic ownership mismatches on a current release candidate; and (3) refresh the live website, app assets, and store listing facts immediately before publication. A page-by-page comparison with the 2026–27 commercial book is only necessary if the project wants to claim exact identity with that product. These are bounded tasks, not reasons to discard the established preservation evidence.

# Definitions and source register

**Edition**: the project's year-labeled source selection. **Snapshot**: a specific captured upstream state or database file. **Entry**: a source profile within one edition. **Entity**: a project canonical identity connecting entries. **Field**: one stored original label and content row. **Sub-value**: a parsed component linked to a field. **Original label**: the field name appearing in source context. **Canonical label**: a mapping for retrieval and comparison. **SourceFragment**: a normalized parser fragment, not necessarily a verbatim raw substring. **Computed value**: a FieldValues row flagged as calculated from source components. **Match rate**: a numerator and denominator under a stated comparison rule.

The links below identify the substantive sources read for this draft. The website and release pages are time-sensitive; the repository documents may receive later edits. The evidence JSON fixes the numerical state used to draw this PDF.


| Source | What it supports |
| --- | --- |
| [CIA retirement notice](https://www.cia.gov/stories/story/spotlighting-the-world-factbook-as-we-bid-a-fond-farewell/) | 4 February 2026 sunset and institutional publication history. |
| [Skyhorse 2026–27 book](https://www.skyhorsepublishing.com/9781510786042/the-cia-world-factbook-2026-2027/) | Commercial title, ISBN, page count, and publisher date. |
| [Archive repository](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025) | Project files, releases, scope, and general citation. |
| [Raw-source manifest](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/MANIFEST.json) | Input files, upstream provenance, hashes, and row-producing status. |
| [Methodology](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/METHODOLOGY.md) | Parsers, mapping, entity resolution, and limitations. |
| [ETL pipeline](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ETL_PIPELINE.md) | Source-era and transformation workflow. |
| [L3 report](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/L3_REPORT.md) | May per-year parser reconstruction numbers. |
| [Validation report](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/VALIDATION.md) | L0–L3 interpretation and the arithmetic erratum. |
| [Entity audit](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ENTITY_INTEGRITY_ISSUE_38.md) | September identity and glossary corrections and limits. |
| [Final snapshot verification](https://worldfactbookarchive.org/about) | Reported 260-code, 32,594-field comparison with another preservation copy. |
| [Live archive](https://worldfactbookarchive.org/archive) | 3 October live headline counts. |
| [Apps page](https://worldfactbookarchive.org/apps) | Platform access and offline app scope. |
| [App release 1.4.1](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/releases/tag/apps-v1.4.1) | Direct packages, hashes, and release scope. |
| [Concept DOI](https://doi.org/10.5281/zenodo.18884612) | Continuing project citation. |


# Final-edition estimate-token audit

The table is a literal case-insensitive search of the 2025 edition's CountryFields.Content in the April local SQLite snapshot. It asks whether each field contains the exact phrase “YYYY est.” for the years shown. A field may contain more than one phrase, so the rows overlap and must not be totaled. A field can also express its source date without this literal phrase. The result supports a narrow but useful point: the final edition includes many estimates dated before its edition label, and this search found no literal 2026 or 2027 estimate token in the tested snapshot.


| Literal token year | 2025-edition fields containing token |
| --- | --- |
| 2018 | 235 |
| 2019 | 667 |
| 2020 | 779 |
| 2021 | 1,613 |
| 2022 | 4,469 |
| 2023 | 5,683 |
| 2024 | 4,516 |
| 2025 | 2,423 |
| 2026 | 0 |
| 2027 | 0 |


The presence of a year token is not a verified measurement date for the entire field. Some content contains several related estimates or narrative notes. A calculation that needs the observation date should parse the relevant sub-value or read the full text. The two zero counts are also not a page comparison with Skyhorse's commercial 2026–27 book. The publisher's title, the archive's digital edition label, and the year printed with a statistic remain distinct.

# Detailed September identity correction crosswalk

The September audit named eleven groups of historical edition records attached to the wrong canonical owner. This table is a compact reproduction of that documented crosswalk, with its total of 34 deployed records. The source entry titles are historical labels; the corrected canonical owner is a retrieval link. The audit retained source wording rather than rewriting the entry's political history. [Entity audit](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ENTITY_INTEGRITY_ISSUE_38.md).


| Source entry | Former owner | Correct owner | Records |
| --- | --- | --- | --- |
| Cape Verde | Canada | Cabo Verde | 11 |
| Man, Isle of | Madagascar | Isle of Man | 11 |
| Pacific Islands, Trust Territory of the | Paraguay | Palau | 3 |
| Iraq–Saudi Arabia Neutral Zone | Iraq | Separate dissolved entity | 2 |
| South Georgia and the | Georgia | South Georgia and the South Sandwich Islands | 1 |
| Cocos Islands | Colombia | Cocos (Keeling) Islands | 1 |
| Wake Atoll | Namibia | Wake Island | 1 |
| St. Helena | Saint Lucia | Saint Helena | 1 |
| St. Kitts and Nevis | Saint Lucia | Saint Kitts and Nevis | 1 |
| St. Pierre and Miquelon | Saint Lucia | Saint Pierre and Miquelon | 1 |
| St. Vincent and the Grenadines | Saint Lucia | Saint Vincent and the Grenadines | 1 |


The same audit corrected four classification cases: Georgia and Zimbabwe to sovereign, Cook Islands and Niue to freely associated. It separately removed 176 Zimbabwe 1998 glossary rows. Those are different operations: reassignment of a country-year owner, change of a canonical classification, and deletion of parsed non-entry content. Each should have a separate test and change record. A field row's original content should not be modified merely because its canonical owner link was wrong.

# SQL examples and integrity contracts

The following queries illustrate the units behind the report. They are for a SQLite copy of the archive schema. They do not silently coerce a source text field into a numerical measurement. Replace the sample year and field only after inspecting the relevant schema and source edition. The complete extraction SQL used for the figures is stored in evidence.json and the extraction script.

To view the original field context for one edition, retain the entry's source name, category title, original field label, and full content:

~~~sql
SELECT c.Year, c.Name AS SourceEntry, c.Code AS SourceCode,
       cc.CategoryTitle, cf.FieldName AS OriginalFieldName, cf.Content
FROM Countries c
JOIN CountryCategories cc ON cc.CountryID = c.CountryID
JOIN CountryFields cf ON cf.CategoryID = cc.CategoryID
WHERE c.Year = 2025 AND c.Name = 'Afghanistan'
ORDER BY cc.CategoryID, cf.FieldID;
~~~

This join follows the category relationship. It will omit a field whose CountryID and category owner disagree; that is one reason to run a separate semantic check. It also returns full content rather than an assumed numeric first token. A country-name filter is useful for a human lookup but a reproducible analysis should record the source CountryID or an exact code and edition.

To detect cross-table ownership mismatches that ordinary foreign-key existence checks can miss:

~~~sql
SELECT cf.FieldID, cf.CountryID AS FieldCountryID,
       cc.CountryID AS CategoryCountryID, cf.FieldName
FROM CountryFields cf
JOIN CountryCategories cc ON cc.CategoryID = cf.CategoryID
WHERE cf.CountryID <> cc.CountryID
ORDER BY cf.FieldID;
~~~

This query returned two Serbia 2008 rows in the April local snapshot. It has not been run here on the repaired live database. A release-candidate test should assert its expected result on that exact candidate and investigate nonzero rows before interpreting country-level exports.

For an entity history, count distinct edition years as well as raw linked rows:

~~~sql
SELECT mc.CanonicalName,
       COUNT(DISTINCT c.Year) AS DistinctEditionYears,
       COUNT(c.CountryID) AS LinkedEntryRows
FROM MasterCountries mc
LEFT JOIN Countries c ON c.MasterCountryID = mc.MasterCountryID
GROUP BY mc.MasterCountryID, mc.CanonicalName
ORDER BY DistinctEditionYears DESC, mc.CanonicalName;
~~~

The two counts can differ where multiple entry rows were linked to one canonical entity in a year. In the pre-repair local snapshot, that condition occurs for several entities. A longitudinal indicator query must choose one source row per intended entity-year or explain why more than one is legitimate. Counting raw rows as “years of coverage” would be an error.

Finally, a field-name mapping should preserve both the original and canonical label:

~~~sql
SELECT c.Year, c.Name, cc.CategoryTitle,
       cf.FieldName AS OriginalFieldName, fm.CanonicalName,
       fm.MappingType, fm.IsNoise, cf.Content
FROM CountryFields cf
JOIN Countries c ON c.CountryID = cf.CountryID
JOIN CountryCategories cc ON cc.CategoryID = cf.CategoryID
LEFT JOIN FieldNameMappings fm ON fm.OriginalName = cf.FieldName
WHERE c.Year BETWEEN 1990 AND 2025
  AND fm.CanonicalName = 'Population'
ORDER BY c.Year, c.Name;
~~~

This is a retrieval example, not a ready-made population time series. The analyst must still inspect source text, estimate years, units, duplicate rows, noise classification, and the chosen cohort. A case-sensitive mapping may behave differently in SQL Server. The source repository's field-evolution and methodology notes document those differences.

# Public release evidence matrix

A public report can be exact only about the artifacts it actually checked. This matrix records the review status of central claims in this draft. “Observed” means a read-only check on 3 October 2026; “reported” means the cited project document supplies the result; “not run” means no new test was performed while preparing the report.


| Claim or artifact | Evidence used | Status in this draft |
| --- | --- | --- |
| Source inventory | 38-file manifest and raw-source guide | Read and reconciled to manifest totals |
| April chart database | Read-only SQLite aggregates and SHA-256 | Computed locally |
| May raw-to-row agreement | L3 report and validator explanation | Arithmetic checked; validator not rerun |
| Final digital snapshot | Site's 260-code, 32,594-field comparison | Project-reported result |
| September entity repair | Issue 38 audit and live field count | Audit read; live total observed |
| Current archive headline | Live archive page and country API | Observed 3 October 2026 |
| App 1.4.1 direct assets | GitHub release and Apps page | Observed 3 October 2026 |
| App-store versions | Separate store channels | Not comprehensively checked |
| 2026–27 book equivalence | Publisher listing and CIA closure date | Book existence verified; page comparison not run |


The most consequential missing check is a corrected L3 rerun against a named current release candidate with disjoint accounting for matched, changed, missing, extra, and deliberately curated rows. That result would let a later public report replace the dated May baseline. A current full-database structural check would also settle whether the April-only cross-table ownership mismatch remains. A book comparison is optional unless exact identity with the commercial title becomes part of the project's public claim.
