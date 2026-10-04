"""Generate inspectable report appendices from recorded evidence and source docs."""

from __future__ import annotations

import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
E = json.loads((HERE / "evidence.json").read_text(encoding="utf-8"))
P = json.loads((HERE / "public_observations.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((REPO / "raw-sources" / "MANIFEST.json").read_text(encoding="utf-8"))


def table(headers: list[str], rows: list[list[object]]) -> str:
    def cell(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")
    return "\n".join(
        ["| " + " | ".join(headers) + " |",
         "| " + " | ".join(["---"] * len(headers)) + " |"] +
        ["| " + " | ".join(cell(c) for c in row) + " |" for row in rows]
    )


def l1_rows() -> list[tuple[int, str, float]]:
    source = (REPO / "raw-sources" / "VALIDATION.md").read_text(encoding="utf-8")
    rows = []
    for line in source.splitlines():
        m = re.match(r"^\| (\d{4}) \| (text|html|json) \| (\d+(?:\.\d+)?)% \|", line)
        if m:
            rows.append((int(m[1]), m[2], float(m[3])))
    assert len(rows) == 36
    return rows


def l3_rows() -> list[dict]:
    source = (REPO / "raw-sources" / "L3_REPORT.md").read_text(encoding="utf-8")
    rows = []
    for line in source.splitlines():
        m = re.match(
            r"^\| (\d{4}) \| (text|html|json) \| ([\d,]+) \| ([\d,]+) \| ([\d,]+) \| ([\d,]+) \| ([\d,]+) \| ([\d,]+) \|",
            line,
        )
        if m:
            rows.append({
                "year": int(m[1]), "source": m[2],
                "reparse": int(m[3].replace(",", "")),
                "db": int(m[4].replace(",", "")),
                "matches": int(m[5].replace(",", "")),
                "content_diffs": int(m[6].replace(",", "")),
                "missing_keys": int(m[7].replace(",", "")),
                "extra_keys": int(m[8].replace(",", "")),
            })
    assert len(rows) == 36
    return rows


def main() -> None:
    r = E["results"]
    annual = {row["year"]: row for row in r["years"]}
    values = {row["year"]: row for row in r["field_values_year"]}
    source = {row["year"]: row["source"] for row in r["year_sources"]}
    sections = []
    add = sections.append
    add(r"""\appendix

# Evidence register and snapshot ledger

The report uses three different data states. The **local chart snapshot** is a read-only SQLite file last modified 8 April 2026. The **May comparison** is the project's reported parser rerun against a 1,071,489-row SQLite baseline. The **live observation** was taken from the public website on 3 October 2026, after a documented September repair. Equal-looking counts between states do not prove byte identity; different counts require their own source explanations. The local aggregate extraction script and its JSON output are distributed with this report so each figure can be rebuilt without reaching the live site.

""")
    add(table(
        ["Evidence state", "Date or cutoff", "Entities / entries / fields", "Use in report"],
        [
            ["Local SQLite chart snapshot", E["database_modified_utc"][:10],
             "284 / 9,535 / 1,071,489", "Figures and annual tables"],
            ["May L3 comparison", "27 May 2026", "1,071,489 DB field rows",
             "Raw-to-database reconstruction evidence"],
            ["September repair audit", "22 September 2026", "1,071,313 fields on production copy",
             "Identity and glossary correction evidence"],
            ["Live archive observation", P["checked_local_date"],
             "285 / 9,535 / 1,071,313", "Current public headline"],
        ],
    ))
    add(f"""

Local SQLite file size: **{E['database_bytes']:,} bytes**. SHA-256: **{E['database_sha256']}**. Its modification timestamp is a filesystem observation, not proof of a release tag. The live entity and field totals came from [the archive page]({P['archive_page']['url']}); the sum of YearCount came from [the public country API]({P['country_api']['url']}). The site displayed 36 editions. A public count is time-sensitive and should be refreshed before a later release or publication.

The SQL for every local aggregate is stored under the **sql** key of evidence.json. It opens SQLite in read-only immutable mode and writes only its aggregate JSON output. The charts are built from that output by make_figures.py; no real-world indicator is modeled in the chart scripts.

# Source inventory and edition lineage

The raw-source manifest is the authoritative file inventory for the reported source bundle. It lists **{MANIFEST['total_files']} files** and **{MANIFEST['total_bytes']:,} bytes**. The table below shows year, file, era, a digest prefix, and whether the file produced database rows. Full SHA-256 values and upstream URLs are in [the manifest](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/MANIFEST.json); a digest prefix alone is not a sufficient integrity check. The corrupt 2001 HTML ZIP remains an archived asset but is not an input to country rows.

""")
    files = sorted(MANIFEST["files"], key=lambda x: (x.get("year", 0), x["filename"]))
    add(table(
        ["Year", "File", "Era", "SHA-256 prefix", "DB rows?"],
        [[x.get("year", ""), x["filename"], x["era"], x["sha256"][:12],
          "yes" if x["produced_db_rows"] else "no"] for x in files],
    ))
    add("""

The table describes released artifacts, not an exhaustive list of every file ever distributed by the CIA or the Wayback Machine. The 1996 source repair requires both the Gutenberg text and the CIA original repair source. For JSON years, the manifest's upstream commits matter more than a branch name that could move. The source timeline figure uses the edition rows actually marked in the local SQLite Countries table.

# Annual archive counts

Each line below describes one local SQLite edition. “Entries” counts Countries rows; “categories” counts CountryCategories rows; “fields” counts CountryFields rows; “labels” counts distinct original FieldName strings in that year. Because these are database records, a change may reflect source editing, extraction, or a later correction. The table is intended for lookup and figure verification, not for inference about the quantity of real-world knowledge.

""")
    add(table(
        ["Year", "Source", "Entries", "Categories", "Fields", "Labels"],
        [[y, source[y], f"{annual[y]['country_years']:,}",
          f"{annual[y]['categories']:,}", f"{annual[y]['fields']:,}",
          f"{annual[y]['field_names']:,}"] for y in sorted(annual)],
    ))
    add(f"""

The annual fields column sums to **{sum(row['fields'] for row in annual.values()):,}**. Its 2025 line has **{annual[2025]['country_years']:,} entries** and **{annual[2025]['fields']:,} fields**. The 2008 field total includes two rows whose CountryID does not agree with their referenced category's CountryID in this local snapshot; the extraction script records both IDs. This semantic relationship is not tested by a simple foreign-key existence check.

# Derived value counts by edition

FieldValues rows are derived from parent fields and are not additional original CIA field rows. “Numeric share” is the percentage of FieldValues rows with non-null NumericVal. “Computed” counts IsComputed = 1. The parser and field formats changed; these are output-coverage measurements rather than independent measures of numeric information in the CIA publication.

""")
    value_rows = [
        [y, f"{values[y]['value_count']:,}",
         f"{100*values[y]['numeric_values']/values[y]['value_count']:.1f}%",
         values[y]["computed_values"]]
        for y in sorted(values)
    ]
    midpoint = len(value_rows) // 2
    table_rows = [value_rows[i] + value_rows[midpoint + i]
                  for i in range(midpoint)]
    latex_rows = []
    for row in table_rows:
        latex_rows.append(" & ".join(str(cell).replace("%", r"\%") for cell in row)
                          + r" \\")
    add("\n\\begin{center}\n\\begingroup\\small\n"
        "\\setlength{\\tabcolsep}{6.5pt}\n"
        "\\begin{tabular}{rrrr@{\\hspace{1.5em}}rrrr}\n\\hline\n"
        "Year & Values & Numeric \\% & Computed & "
        "Year & Values & Numeric \\% & Computed \\\\\n"
        "\\hline\n" + "\n".join(latex_rows) +
        "\n\\hline\n\\end{tabular}\n\\endgroup\n\\end{center}\n")
    add(f"""

The local snapshot has **{r['source_fragment'][0]['total']:,}** FieldValues rows, **{r['source_fragment'][0]['populated']:,}** non-empty SourceFragment values, and **{r['source_fragment'][0]['computed']:,}** rows explicitly marked computed. The fragment-population count is not a verbatim-source match count. The May L1 exact-substring test had a different denominator and purpose.

# Final-edition category detail and field mappings

The 2025 table is a one-edition composition. A category appears in fewer than 260 entries when it does not apply, was not published, or was not represented by this extraction. “Field rows” counts stored fields, not words or verified facts. The sum reconciles to the 2025 field total. The mapping table describes 1,132 distinct original labels in the April snapshot, not usage-weighted field rows.

""")
    add(table(
        ["2025 category", "Field rows", "Entries with category"],
        [[x["category"], f"{x['fields']:,}", x["country_years"]] for x in r["categories_2025"]],
    ))
    add("\n\n" + table(
        ["Mapping type", "Original labels"],
        [[x["mapping_type"].replace("_", " "), x["names"]] for x in r["mapping_types"]],
    ))
    add("""

The category table groups by category title in the 2025 source. It should not be projected across all years without a category crosswalk. The mapping-type table comes from FieldNameMappings; use count, decision quality, and cross-year semantic comparability are separate questions.

# Validation detail by edition

The first table reproduces the May L1 exact-substring hit percentages from the raw-source validation report. Each year had 200 sampled normalized fragments. The second table reproduces the May L3 reported database row and matching-row counts. L3's residual categories use mixed units and are therefore shown only in the source report rather than being recombined into a false partition here. Both tables are historical results for the May comparison, not new October runs.

""")
    add(table(
        ["Year", "Source", "L1 exact hits"],
        [[y, src, f"{pct:.1f}%"] for y, src, pct in l1_rows()],
    ))
    add("\n\n" + table(
        ["Year", "Source", "DB rows", "Matches", "Match / DB"],
        [[x["year"], x["source"], f"{x['db']:,}", f"{x['matches']:,}",
          f"{100*x['matches']/x['db']:.2f}%"] for x in l3_rows()],
    ))
    total_db = sum(x["db"] for x in l3_rows())
    total_match = sum(x["matches"] for x in l3_rows())
    add(f"""

The L3 table's database column sums to **{total_db:,}**, and its matching column to **{total_match:,}**. Division gives **{100*total_match/total_db:.8f}%**, rounded to **{100*total_match/total_db:.2f}%**. The original validation document's 99.94% headline was a calculation error. The residual detail in L3_REPORT.md describes 1996 repair-shape differences, HTML decoding differences, and the 2008 duplicate Serbia source. A corrected validator rerun against a named new database is needed to establish a disjoint residual count.

# App direct-release asset record

The table below is the 3 October 2026 GitHub direct-release asset inventory. A package's presence in that release does not establish its app-store status. The full SHA-256 values are retained in public_observations.json and the [release note]({P['app_release']['url']}); prefixes are shown here only to keep the table readable. The package byte sizes are distinct platform artifacts and should not be compared as an efficiency ranking.

""")
    add(table(
        ["Asset", "Bytes", "SHA-256 prefix"],
        [[x["name"], f"{x['bytes']:,}", x["sha256"][:16]]
         for x in P["app_release"]["assets"]],
    ))
    add("""

The Apps page listed iPhone/iPad, Android, macOS, and Windows access when checked. It described 284 bundled CIA maps and a fully offline Factbook experience. The site and app can have different data revisions. A future report should repeat the direct-release and store-listing checks before updating a public version claim.

# Reproduction and research checklist

To rebuild this report's local aggregate figures, use a SQLite file whose SHA-256 equals the digest in the evidence register. Run extract_evidence.py with an explicit --db path; inspect the generated evidence.json; then run make_figures.py and the PDF builder. The extraction script opens the database read-only and records its SQL and source hash. A different file hash may be a valid newer database, but its figures must be relabeled and revalidated before reuse.

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

""")
    add(table(
        ["Earlier wording or gap", "This report's treatment"],
        [
            ["Only publicly available archive", "Describes concrete features; makes no exclusivity claim."],
            ["100% provenance or universal accuracy", "Separates hashes, parser agreement, final-snapshot comparison, and unresolved residuals."],
            ["281 entities and 1,071,603 fields", "Uses dated live and local counts with explicit snapshot boundaries."],
            ["No companion app", "Includes offline app scope, 1.4.1 direct assets, and distribution limits."],
            ["Version-specific DOI as general citation", "Uses concept DOI and exact release tag when needed."],
            ["2026–27 title omitted", "Explains commercial book label, final CIA 2025 digital edition, and lack of page comparison."],
        ],
    ))
    add("""

For a future data release or stronger current-database parity claim, three questions remain: (1) rerun raw-to-row validation with corrected residual accounting against the intended current database; (2) test the April-only semantic ownership mismatches on a current release candidate; and (3) refresh the live website, app assets, and store listing facts when the report is revised. A page-by-page comparison with the 2026–27 commercial book is necessary if the project wants to claim exact identity with that product. The present report labels its tested snapshots and does not make those stronger claims.

# Definitions and source register

**Edition**: the project's year-labeled source selection. **Snapshot**: a specific captured upstream state or database file. **Entry**: a source profile within one edition. **Entity**: a project canonical identity connecting entries. **Field**: one stored original label and content row. **Sub-value**: a parsed component linked to a field. **Original label**: the field name appearing in source context. **Canonical label**: a mapping for retrieval and comparison. **SourceFragment**: a normalized parser fragment, not necessarily a verbatim raw substring. **Computed value**: a FieldValues row flagged as calculated from source components. **Match rate**: a numerator and denominator under a stated comparison rule.

The links below identify the substantive sources read for this report. The website and release pages are time-sensitive; the repository documents may receive later edits. The evidence JSON fixes the numerical state used to draw this PDF.

""")
    add(table(
        ["Source", "What it supports"],
        [
            ["[CIA retirement notice](https://www.cia.gov/stories/story/spotlighting-the-world-factbook-as-we-bid-a-fond-farewell/)", "4 February 2026 sunset and institutional publication history."],
            ["[Skyhorse 2026–27 book](https://www.skyhorsepublishing.com/9781510786042/the-cia-world-factbook-2026-2027/)", "Commercial title, ISBN, page count, and publisher date."],
            ["[Archive repository](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025)", "Project files, releases, scope, and general citation."],
            ["[Raw-source manifest](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/MANIFEST.json)", "Input files, upstream provenance, hashes, and row-producing status."],
            ["[Methodology](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/METHODOLOGY.md)", "Parsers, mapping, entity resolution, and limitations."],
            ["[ETL pipeline](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ETL_PIPELINE.md)", "Source-era and transformation workflow."],
            ["[L3 report](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/L3_REPORT.md)", "May per-year parser reconstruction numbers."],
            ["[Validation report](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/raw-sources/VALIDATION.md)", "L0–L3 interpretation and the arithmetic erratum."],
            ["[Entity audit](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ENTITY_INTEGRITY_ISSUE_38.md)", "September identity and glossary corrections and limits."],
            ["[Final snapshot verification](https://worldfactbookarchive.org/about)", "Reported 260-code, 32,594-field comparison with another preservation copy."],
            ["[Live archive](https://worldfactbookarchive.org/archive)", "3 October live headline counts."],
            ["[Apps page](https://worldfactbookarchive.org/apps)", "Platform access and offline app scope."],
            ["[App release 1.4.1](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/releases/tag/apps-v1.4.1)", "Direct packages, hashes, and release scope."],
            ["[Concept DOI](https://doi.org/10.5281/zenodo.18884612)", "Continuing project citation."],
        ],
    ))
    add("""

# Final-edition estimate-token audit

The table is a literal case-insensitive search of the 2025 edition's CountryFields.Content in the April local SQLite snapshot. It asks whether each field contains the exact phrase “YYYY est.” for the years shown. A field may contain more than one phrase, so the rows overlap and must not be totaled. A field can also express its source date without this literal phrase. The result supports a narrow but useful point: the final edition includes many estimates dated before its edition label, and this search found no literal 2026 or 2027 estimate token in the tested snapshot.

""")
    add(table(
        ["Literal token year", "2025-edition fields containing token"],
        [[x["estimate_year"], f"{x['fields_with_token']:,}"]
         for x in r["final_estimate_tokens"]],
    ))
    add("""

The presence of a year token is not a verified measurement date for the entire field. Some content contains several related estimates or narrative notes. A calculation that needs the observation date should parse the relevant sub-value or read the full text. The two zero counts are also not a page comparison with Skyhorse's commercial 2026–27 book. The publisher's title, the archive's digital edition label, and the year printed with a statistic remain distinct.

# Detailed September identity correction crosswalk

The September audit named eleven groups of historical edition records attached to the wrong canonical owner. This table is a compact reproduction of that documented crosswalk, with its total of 34 deployed records. The source entry titles are historical labels; the corrected canonical owner is a retrieval link. The audit retained source wording rather than rewriting the entry's political history. [Entity audit](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/blob/main/docs/ENTITY_INTEGRITY_ISSUE_38.md).

""")
    add(table(
        ["Source entry", "Former owner", "Correct owner", "Records"],
        [
            ["Cape Verde", "Canada", "Cabo Verde", 11],
            ["Man, Isle of", "Madagascar", "Isle of Man", 11],
            ["Pacific Islands, Trust Territory of the", "Paraguay", "Palau", 3],
            ["Iraq–Saudi Arabia Neutral Zone", "Iraq", "Separate dissolved entity", 2],
            ["South Georgia and the", "Georgia", "South Georgia and the South Sandwich Islands", 1],
            ["Cocos Islands", "Colombia", "Cocos (Keeling) Islands", 1],
            ["Wake Atoll", "Namibia", "Wake Island", 1],
            ["St. Helena", "Saint Lucia", "Saint Helena", 1],
            ["St. Kitts and Nevis", "Saint Lucia", "Saint Kitts and Nevis", 1],
            ["St. Pierre and Miquelon", "Saint Lucia", "Saint Pierre and Miquelon", 1],
            ["St. Vincent and the Grenadines", "Saint Lucia", "Saint Vincent and the Grenadines", 1],
        ],
    ))
    add("""

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

A public report can be exact only about the artifacts it actually checked. This matrix records the review status of central claims in this report. “Observed” means a read-only check on 3 October 2026; “reported” means the cited project document supplies the result; “not run” means no new test was performed while preparing the report.

""")
    add(table(
        ["Claim or artifact", "Evidence used", "Status in this report"],
        [
            ["Source inventory", "38-file manifest and raw-source guide", "Read and reconciled to manifest totals"],
            ["April chart database", "Read-only SQLite aggregates and SHA-256", "Computed locally"],
            ["May raw-to-row agreement", "L3 report and validator explanation", "Arithmetic checked; validator not rerun"],
            ["Final digital snapshot", "Site's 260-code, 32,594-field comparison", "Project-reported result"],
            ["September entity repair", "Issue 38 audit and live field count", "Audit read; live total observed"],
            ["Current archive headline", "Live archive page and country API", "Observed 3 October 2026"],
            ["App 1.4.1 direct assets", "GitHub release and Apps page", "Observed 3 October 2026"],
            ["App-store versions", "Separate store channels", "Not comprehensively checked"],
            ["2026–27 book equivalence", "Publisher listing and CIA closure date", "Book existence verified; page comparison not run"],
        ],
    ))
    add("""

The most consequential missing check is a corrected L3 rerun against a named current release candidate with disjoint accounting for matched, changed, missing, extra, and deliberately curated rows. That result would let a later public report replace the dated May baseline. A current full-database structural check would also settle whether the April-only cross-table ownership mismatch remains. A book comparison is optional unless exact identity with the commercial title becomes part of the project's public claim.
""")
    add("\n\\clearpage\n")
    output = "\n".join(sections).strip() + "\n"
    (HERE / "appendices.md").write_text(output, encoding="utf-8")
    print(f"Wrote appendices.md ({len(output.split())} words)")


if __name__ == "__main__":
    main()
