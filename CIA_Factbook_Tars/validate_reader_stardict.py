"""Validate all reader-edition StarDict files against the source snapshot."""

import argparse
import gzip
import sqlite3
import struct
from pathlib import Path

from etl.stardict.build_reader_stardict import FIELDS_QUERY, build_entries


def read_index(path, dictionary_size):
    data = path.read_bytes()
    result = {}
    pos = 0
    while pos < len(data):
        end = data.index(b"\0", pos)
        if end + 9 > len(data):
            raise ValueError(f"Truncated index: {path}")
        word = data[pos:end].decode("utf-8")
        offset, size = struct.unpack_from(">II", data, end + 1)
        if not word or not size or offset + size > dictionary_size or word in result:
            raise ValueError(f"Invalid headword or offset: {word!r} in {path}")
        result[word] = (offset, size)
        pos = end + 9
    return result


def read_synonyms(path, words):
    data = path.read_bytes()
    result = {}
    pos = 0
    while pos < len(data):
        end = data.index(b"\0", pos)
        if end + 5 > len(data):
            raise ValueError(f"Truncated synonyms: {path}")
        word = data[pos:end].decode("utf-8")
        index = struct.unpack_from(">I", data, end + 1)[0]
        if not word or index >= len(words) or word in result:
            raise ValueError(f"Invalid synonym: {word!r} in {path}")
        result[word] = words[index]
        pos = end + 5
    return result


def validate_year(db, root, year, roundtrip=False):
    name = f"cia-factbook-{year}-reader"
    directory = root / name
    paths = {suffix: directory / f"{name}.{suffix}"
             for suffix in ("ifo", "idx", "dict.dz", "syn")}
    for path in paths.values():
        if not path.is_file():
            raise ValueError(f"Missing {path}")
    metadata = dict(line.split("=", 1) for line in
                    paths["ifo"].read_text(encoding="utf-8").splitlines()
                    if "=" in line)
    if metadata.get("sametypesequence") != "h":
        raise ValueError(f"Unexpected type sequence in {name}")
    definitions = gzip.decompress(paths["dict.dz"].read_bytes())
    if b"\xef\xbf\xbd" in definitions:
        raise ValueError(f"Replacement character in {name}")
    index = read_index(paths["idx"], len(definitions))
    synonyms = read_synonyms(paths["syn"], list(index))
    if int(metadata["wordcount"]) != len(index):
        raise ValueError(f"Word count mismatch in {name}")
    if int(metadata["idxfilesize"]) != paths["idx"].stat().st_size:
        raise ValueError(f"Index size mismatch in {name}")
    if int(metadata.get("synwordcount", 0)) != len(synonyms):
        raise ValueError(f"Synonym count mismatch in {name}")

    masters = {
        master_id: (iso, canonical)
        for master_id, iso, canonical in db.execute(
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
    rows = db.execute(FIELDS_QUERY, (year,)).fetchall()
    entries, country_count, _ = build_entries(rows, masters, iso_owners, year)
    expected = {words[0] for words, _ in entries}
    if len(expected) != len(entries) or set(index) != expected:
        missing = sorted(expected - set(index))[:5]
        extra = sorted(set(index) - expected)[:5]
        raise ValueError(f"Headword mismatch in {name}: missing={missing}, extra={extra}")

    expected_aliases = {}
    for words, body in entries:
        primary = words[0]
        start, size = index[primary]
        if definitions[start:start + size] != body.encode("utf-8"):
            raise ValueError(f"Definition differs from source: {primary} in {name}")
        for alias in words[1:]:
            if alias in index or alias in expected_aliases:
                raise ValueError(f"Ambiguous alias: {alias} in {name}")
            expected_aliases[alias] = primary
    if synonyms != expected_aliases:
        missing = sorted(expected_aliases.keys() - synonyms.keys())[:5]
        extra = sorted(synonyms.keys() - expected_aliases.keys())[:5]
        wrong = [word for word in synonyms.keys() & expected_aliases.keys()
                 if synonyms[word] != expected_aliases[word]][:5]
        raise ValueError(f"Alias mismatch in {name}: missing={missing}, "
                         f"extra={extra}, wrong={wrong}")
    if b"<img" in definitions:
        raise ValueError(f"Unbundled image reference in {name}")
    if roundtrip:
        from pyglossary.glossary_v2 import Glossary

        glossary = Glossary()
        glossary.directRead(str(paths["ifo"]))
        try:
            count = 0
            for entry in glossary:
                if not entry.l_term:
                    continue
                primary = entry.l_term[0]
                if primary not in index or entry.defiFormat != "h":
                    raise ValueError(f"Reader rejected entry: {primary} in {name}")
                start, size = index[primary]
                if entry.defi.encode("utf-8") != definitions[start:start + size]:
                    raise ValueError(f"Reader changed definition: {primary} in {name}")
                count += 1
            if count != len(index):
                raise ValueError(f"Reader count mismatch: {count} in {name}")
        finally:
            glossary.clear()
    return len(index), len(synonyms), country_count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--dict-dir", type=Path, required=True)
    parser.add_argument("--years", type=int, nargs="+", default=list(range(1990, 2026)))
    parser.add_argument("--roundtrip", action="store_true",
                        help="Also read every entry back through PyGlossary")
    args = parser.parse_args()
    if args.roundtrip:
        from pyglossary.glossary_v2 import Glossary

        Glossary.init()
    with sqlite3.connect(args.db.resolve().as_uri() + "?mode=ro", uri=True) as db:
        total = 0
        for year in sorted(set(args.years)):
            words, aliases, countries = validate_year(
                db, args.dict_dir, year, roundtrip=args.roundtrip
            )
            total += words
            print(f"{year}: PASS, {words} entries, {aliases} aliases, "
                  f"{countries} countries", flush=True)
    print(f"PASS: {len(set(args.years))} dictionaries, {total} entries")


if __name__ == "__main__":
    main()
