"""Build a KOReader-oriented StarDict edition from a reviewed SQLite snapshot.

Each year contains complete country profiles, country/category pages, and
individual country/field entries. This is separate from the existing general
and structured editions so their published behavior is unchanged.
"""

import argparse
import html
import sqlite3
import time
from collections import Counter, OrderedDict
from pathlib import Path

from etl.stardict.build_stardict import _dedup_entries, build_field_headwords, esc


YEARS = range(1990, 2026)
FIELDS_QUERY = """
    SELECT co.CountryID, co.MasterCountryID, co.Name, co.Code,
           cc.CategoryTitle, cf.FieldName, cf.Content,
           cc.CategoryID, cf.FieldID
    FROM Countries co
    JOIN CountryCategories cc ON cc.CountryID = co.CountryID
    JOIN CountryFields cf ON cf.CountryID = co.CountryID
                         AND cf.CategoryID = cc.CategoryID
    WHERE co.Year = ?
    ORDER BY co.CountryID, cc.CategoryID, cf.FieldID
"""


def candidate_aliases(master_id, period_code, masters, iso_owners):
    """Use the edition's code, not a modern successor's canonical code."""
    iso, _ = masters.get(master_id, (None, None))
    result = []
    if iso and iso_owners.get(iso) == master_id:
        result.append(iso)
    fips = period_code.upper() if period_code else None
    if fips and fips not in iso_owners:
        result.append(fips)
    return list(dict.fromkeys(result))


def country_codes(name, master_id, period_code, masters, iso_owners, alias_counts):
    """Skip aliases claimed by multiple historical entities in the same year."""
    result = [name]
    for alias in candidate_aliases(master_id, period_code, masters, iso_owners):
        if alias_counts[alias] == 1:
            result.append(alias)
    return result


def field_html(field_name, content):
    title = html.escape(field_name, quote=False)
    value = esc(content).replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace(" | ", "<br/>").replace("\n", "<br/>")
    return f'<p><b style="color:#b06088">{title}</b><br/>{value}</p>'


def category_html(country, category, fields):
    heading = html.escape(country, quote=False)
    section = html.escape(category, quote=False)
    body = "".join(field_html(name, content) for name, content in fields)
    return f"<h3>{heading}: {section}</h3>{body}"


def build_entries(rows, masters, iso_owners, year):
    """Return StarDict entries and source counts for one year."""
    countries = OrderedDict()
    fields = OrderedDict()
    for country_id, master_id, name, period_code, category, field, content, category_id, _ in rows:
        if not content or not content.strip():
            continue
        country = countries.setdefault(country_id, {
            "name": name, "master_id": master_id, "period_code": period_code,
            "categories": OrderedDict(),
        })
        country["categories"].setdefault(category_id, {
            "name": category, "fields": [],
        })["fields"].append((field, content))
        key = (country_id, field)
        fields.setdefault(key, []).append((category, content))

    alias_counts = Counter(
        alias
        for country in countries.values()
        for alias in candidate_aliases(
            country["master_id"], country["period_code"], masters, iso_owners
        )
    )
    entries = []
    for country_id, country in countries.items():
        name = country["name"]
        codes = country_codes(name, country["master_id"], country["period_code"],
                              masters, iso_owners, alias_counts)
        sections = []
        for category in country["categories"].values():
            title = category["name"]
            body = category_html(name, title, category["fields"])
            sections.append(body)
            entries.append(([f"{code} {title}" for code in codes], body))
        full_body = (
            f"<h2>{html.escape(name, quote=False)}</h2>"
            f"<p>World Factbook {year}</p>" + "".join(sections)
        )
        entries.append((codes, full_body))

    for (country_id, field_name), values in fields.items():
        country = countries[country_id]
        name = country["name"]
        codes = country_codes(name, country["master_id"], country["period_code"],
                              masters, iso_owners, alias_counts)
        title = html.escape(values[0][0], quote=False)
        body = f"<p><i>{html.escape(name, quote=False)}</i> / {title}</p>"
        body += "".join(field_html(field_name, content) for _, content in values)
        entries.append((build_field_headwords(codes, field_name), body))

    return _dedup_entries(entries), len(countries), len(fields)


def write_dictionary(entries, year, output_dir):
    from pyglossary.glossary_v2 import Glossary

    name = f"cia-factbook-{year}-reader"
    dest = output_dir / name
    dest.mkdir(parents=True, exist_ok=True)
    glossary = Glossary()
    glossary.setInfo("title", f"CIA World Factbook {year} (Reader)")
    glossary.setInfo("author", "Central Intelligence Agency")
    glossary.setInfo("description", (
        f"CIA World Factbook {year}: country profiles, category pages, "
        "and individual fields. Offline text edition; no images included. "
        "Source: worldfactbookarchive.org"
    ))
    glossary.setInfo("website", "https://worldfactbookarchive.org/")
    glossary.setInfo("date", str(year))
    for words, definition in entries:
        glossary.addEntry(glossary.newEntry(word=words, defi=definition, defiFormat="h"))
    glossary.write(str(dest / f"{name}.ifo"), formatName="Stardict",
                   dictzip=True, sametypesequence="h")
    return dest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True,
                        help="Reviewed, consistent source snapshot")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--years", type=int, nargs="+", default=list(YEARS))
    args = parser.parse_args()
    if not args.db.is_file() or not set(args.years).issubset(YEARS):
        parser.error("--db must exist and years must be between 1990 and 2025")

    from pyglossary.glossary_v2 import Glossary
    Glossary.init()
    db = sqlite3.connect(args.db.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        masters = {
            row[0]: (row[1], row[2])
            for row in db.execute(
                "SELECT MasterCountryID, ISOAlpha2, CanonicalCode FROM MasterCountries"
            )
        }
        iso_owners = {}
        for master_id, iso, entity_type in db.execute(
            "SELECT MasterCountryID, ISOAlpha2, EntityType FROM MasterCountries "
            "ORDER BY MasterCountryID"
        ):
            if iso and (iso not in iso_owners or entity_type == "sovereign"):
                iso_owners[iso] = master_id
        for year in sorted(set(args.years)):
            start = time.monotonic()
            rows = db.execute(FIELDS_QUERY, (year,)).fetchall()
            if not rows:
                raise ValueError(f"No fields for {year}")
            entries, country_count, field_count = build_entries(
                rows, masters, iso_owners, year
            )
            dest = write_dictionary(entries, year, args.output_dir)
            print(f"{year}: {len(entries)} entries, {country_count} countries, "
                  f"{field_count} country-fields, {time.monotonic()-start:.1f}s, "
                  f"{dest}", flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
