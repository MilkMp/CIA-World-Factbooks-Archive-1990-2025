# Entity classification and legacy identity audit — issue 38

Audit date: 22 September 2026. Related issue: [#38](https://github.com/MilkMp/CIA-World-Factbooks-Archive-1990-2025/issues/38).

## Findings and corrections

Georgia and Zimbabwe are sovereign states. The deployed database incorrectly
classified both as territories, although the published master reference already
classified them as sovereign. This was an import/classification problem, not a
change to their political status.

The audit checked all 284 deployed master entities, all 9,535 edition records,
the legacy text-name differences, dependency fields attached to sovereign states,
and all 193 UN members against the official member list. Georgia and Zimbabwe
were the only UN members incorrectly labeled `territory`. The archive uses
`freely_associated` for the Marshall Islands, Micronesia and Palau; this category
does not imply that these UN member states are dependencies.

Cook Islands and Niue were also incorrectly labeled `territory`. Their 2025
Factbook dependency fields explicitly describe free association with New Zealand.
They now use the existing `freely_associated` category.

The production repair corrects these historical edition links:

| Source entry | Incorrect owner | Correct owner | Editions |
|---|---|---|---:|
| Cape Verde | Canada | Cabo Verde | 11 (1990–1999, 2001) |
| Man, Isle of | Madagascar | Isle of Man | 11 (1990–1999, 2001) |
| Pacific Islands, Trust Territory of the | Paraguay | Palau | 3 (1990–1992) |
| Iraq–Saudi Arabia Neutral Zone | Iraq | Separate dissolved entity, IY | 2 (1990–1991) |
| South Georgia and the | Georgia | South Georgia and the South Sandwich Islands | 1 (1997) |
| Cocos Islands | Colombia | Cocos (Keeling) Islands | 1 (1992) |
| Wake Atoll | Namibia | Wake Island | 1 (1999) |
| St. Helena | Saint Lucia | Saint Helena | 1 (1990) |
| St. Kitts and Nevis | Saint Lucia | Saint Kitts and Nevis | 1 (1990) |
| St. Pierre and Miquelon | Saint Lucia | Saint Pierre and Miquelon | 1 (1990) |
| St. Vincent and the Grenadines | Saint Lucia | Saint Vincent and the Grenadines | 1 (1990) |

Total: 34 deployed edition records. The public exports require 35 identity/code
normalizations, including the SQL dump's missing Saint Lucia link. Some public
CSV links had already been corrected while their short codes or SQL counterparts
had not. Repairs resolve each dataset's IDs independently.

The Palau records explicitly identify Palauan nationality, Koror as the capital,
and Palau as the remaining polity under the trusteeship. Their historical titles
and government text are retained. The neutral zone's joint administration is
retained under its own historical entity instead of being treated as Iraq.

The 1998 Zimbabwe entry also contains 176 glossary/appendix rows and a glossary
preamble appended to its authentic Illicit drugs field. The live repair removes
the 176 rows, trims that preamble, and removes 153 derived values associated with
the contaminated fields. It preserves both genuine Transnational Issues fields.
The earlier public-dump repair already removed those 176 rows; this correction
also removes the remaining preamble.

## Causes and prevention

- The text loader used substring matching and a guessed two-letter code to
  recover old country links. Both can identify a different country. Reviewed
  exact aliases now resolve names; unknown names stop the import before deletion.
- The 1997 source itself abbreviates the South Georgia section marker to
  `South Georgia and the`. Its Government field supplies the full identity.
- The at-sign parser treated Zimbabwe as extending through the book's back
  matter. It now stops at `@NOTES AND DEFINITIONS`.
- The classifier independently searched all years for the last dependency and
  government fields. It now reads both from the latest edition, rejects glossary
  definitions as evidence, and checks free association before territory keywords.
- Reviewed overrides cover the four corrected classifications. A UN-member
  reference and regression checks guard against missing/misclassified members.

## Validation and limits

The repair is dry-run by default, requires a new full SQLite backup to apply,
and runs in a transaction. It refuses conflicting identities, duplicate target
editions, or unexpected glossary contents. Tests cover alias ambiguity, back-matter
boundaries, field preservation, search-index cleanup and repeat execution.

On a copy of production: 1,071,489 fields become 1,071,313; valid historical fields
retain their IDs and content except the one glossary tail. SQLite quick-check
passes and rerunning the plan produces no changes. The database already had 165
foreign-key violations; this patch introduces none and does not attempt an
unrelated general cleanup. Existing Germany/Yemen predecessor groupings and empty
legacy aliases are outside this correction. This is not a verification of every
individual historical statistic or a redesign of the archive's political taxonomy.

## Sources and reproduction

- [United Nations member states](https://www.un.org/about-us/member-states),
  retrieved 22 September 2026. `data/lookup_tables/un_member_classifications.csv`
  records all 193 ISO identities and their expected archive categories.
- [Georgia admission resolution](https://digitallibrary.un.org/record/150203?ln=en)
  and [Zimbabwe admission resolution](https://digitallibrary.un.org/record/616920?ln=en).
- New Zealand Ministry of Foreign Affairs:
  [Cook Islands](https://www.mfat.govt.nz/en/countries-and-regions/australia-and-pacific/cook-islands)
  and [Niue](https://www.mfat.govt.nz/en/countries-and-regions/australia-and-pacific/niue).
- CIA Factbook text: [1990](https://www.gutenberg.org/ebooks/14),
  [1997](https://www.gutenberg.org/ebooks/1662),
  [1998](https://www.gutenberg.org/ebooks/2016). Country-name, nationality,
  capital and dependency fields support the record-level identity corrections.
- [Library of Congress country codes](https://www.loc.gov/marc/countries/countries_code.html)
  lists IY for the Iraq–Saudi Arabia Neutral Zone; it has no modern ISO assignment here.

```sh
python -m unittest discover -s tests -p '*_test.py'
python scripts/repair_entity_integrity.py /path/to/factbook.db
python scripts/repair_entity_integrity.py /path/to/factbook.db --apply --backup /path/to/new-backup.db
python scripts/repair_entity_exports.py
```

After a live repair, refresh the application's query cache/read connection and
invalidate cached public HTML before verifying the public pages.
