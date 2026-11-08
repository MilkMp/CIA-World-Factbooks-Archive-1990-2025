"""Validate and package reader-edition dictionaries as reproducible tarballs."""

import argparse
import gzip
import hashlib
import json
import sqlite3
import tarfile
from pathlib import Path

from etl.stardict.validate_reader_stardict import validate_year


YEARS = range(1990, 2026)
SUFFIXES = ("ifo", "idx", "dict.dz", "syn")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package_year(dict_dir, output_dir, year):
    name = f"cia-factbook-{year}-reader"
    source_dir = dict_dir / name
    archive = output_dir / f"{name}.tar.gz"
    if archive.exists():
        raise FileExistsError(f"Refusing to replace existing archive: {archive}")
    files = [source_dir / f"{name}.{suffix}" for suffix in SUFFIXES]
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path)

    temporary = output_dir / f"{name}.tar.gz.tmp"
    if temporary.exists():
        raise FileExistsError(f"Refusing to replace existing temporary file: {temporary}")
    try:
        with temporary.open("wb") as output:
            with gzip.GzipFile(filename="", mode="wb", fileobj=output,
                               compresslevel=9, mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w|",
                                  format=tarfile.USTAR_FORMAT) as tar:
                    directory = tarfile.TarInfo(name + "/")
                    directory.type = tarfile.DIRTYPE
                    directory.mode = 0o755
                    tar.addfile(directory)
                    for path in files:
                        info = tarfile.TarInfo(f"{name}/{path.name}")
                        info.size = path.stat().st_size
                        info.mode = 0o644
                        with path.open("rb") as source:
                            tar.addfile(info, source)

        with tarfile.open(temporary, "r:gz") as tar:
            expected_names = [name] + [f"{name}/{p.name}" for p in files]
            if [member.name.rstrip("/") for member in tar.getmembers()] != expected_names:
                raise ValueError(f"Unexpected archive contents: {temporary}")
            for path in files:
                member = tar.extractfile(f"{name}/{path.name}")
                if member is None or member.read() != path.read_bytes():
                    raise ValueError(f"Archive content differs: {path}")
        temporary.replace(archive)
    finally:
        if temporary.exists():
            temporary.unlink()
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--dict-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--years", type=int, nargs="+", default=list(YEARS))
    args = parser.parse_args()
    if not args.db.is_file() or not set(args.years).issubset(YEARS):
        parser.error("--db must exist and years must be between 1990 and 2025")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "reader-manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"Refusing to replace existing manifest: {manifest_path}")

    with sqlite3.connect(args.db.resolve().as_uri() + "?mode=ro", uri=True) as db:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Source database failed SQLite quick_check")
        source_hash = sha256(args.db)
        records = []
        for year in sorted(set(args.years)):
            words, aliases, countries = validate_year(db, args.dict_dir, year)
            archive = package_year(args.dict_dir, args.output_dir, year)
            record = {
                "year": year,
                "filename": archive.name,
                "bytes": archive.stat().st_size,
                "sha256": sha256(archive),
                "headwords": words,
                "aliases": aliases,
                "countries": countries,
            }
            records.append(record)
            print(f"{year}: {words} headwords, {archive.stat().st_size:,} bytes, "
                  f"SHA256 {record['sha256']}", flush=True)

    manifest = {
        "edition": "reader",
        "years": [record["year"] for record in records],
        "source_db_sha256": source_hash,
        "source_db_bytes": args.db.stat().st_size,
        "images_bundled": False,
        "archives": records,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: {len(records)} verified archives, manifest at {manifest_path}")


if __name__ == "__main__":
    main()
