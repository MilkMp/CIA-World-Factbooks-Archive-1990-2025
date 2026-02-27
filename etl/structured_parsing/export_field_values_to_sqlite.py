"""
Export FieldValues + reference tables to a SEPARATE SQLite database.
Does NOT modify the existing factbook.db — creates a new file.

Reads from:
  - CIA_WorldFactbook (reference tables: MasterCountries, Countries,
    CountryCategories, CountryFields metadata, FieldNameMappings)
  - CIA_WorldFactbook_Extended_Sub_Topics (FieldValues)

Writes to: data/factbook_field_values.db

The result is a self-contained database where you can query
FieldValues all the way back to country name, year, and canonical
field name without needing the main factbook.db.

Usage:
    python etl/structured_parsing/export_field_values_to_sqlite.py [--output path]
"""

import argparse
import os
import sqlite3
import time

import pyodbc

CONN_STR_SOURCE = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;DATABASE=CIA_WorldFactbook;"
    "Trusted_Connection=yes;TrustServerCertificate=yes;"
)
CONN_STR_TARGET = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;DATABASE=CIA_WorldFactbook_Extended_Sub_Topics;"
    "Trusted_Connection=yes;TrustServerCertificate=yes;"
)

DEFAULT_OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "factbook_field_values.db"
)

SCHEMA = """
CREATE TABLE MasterCountries (
    MasterCountryID INTEGER PRIMARY KEY,
    CanonicalCode TEXT NOT NULL,
    CanonicalName TEXT NOT NULL,
    ISOAlpha2 TEXT,
    EntityType TEXT,
    AdministeringMasterCountryID INTEGER REFERENCES MasterCountries(MasterCountryID)
);

CREATE TABLE Countries (
    CountryID INTEGER PRIMARY KEY,
    Year INTEGER NOT NULL,
    Code TEXT NOT NULL,
    Name TEXT NOT NULL,
    Source TEXT DEFAULT 'html',
    MasterCountryID INTEGER REFERENCES MasterCountries(MasterCountryID)
);

CREATE TABLE CountryCategories (
    CategoryID INTEGER PRIMARY KEY,
    CountryID INTEGER NOT NULL REFERENCES Countries(CountryID),
    CategoryTitle TEXT
);

CREATE TABLE CountryFields (
    FieldID INTEGER PRIMARY KEY,
    CategoryID INTEGER NOT NULL REFERENCES CountryCategories(CategoryID),
    CountryID INTEGER NOT NULL REFERENCES Countries(CountryID),
    FieldName TEXT,
    Content TEXT
);

CREATE TABLE FieldNameMappings (
    MappingID INTEGER PRIMARY KEY,
    OriginalName TEXT NOT NULL UNIQUE,
    CanonicalName TEXT NOT NULL,
    MappingType TEXT NOT NULL,
    ConsolidatedTo TEXT,
    IsNoise INTEGER NOT NULL DEFAULT 0,
    FirstYear INTEGER,
    LastYear INTEGER,
    UseCount INTEGER,
    Notes TEXT
);

CREATE TABLE FieldValues (
    ValueID     INTEGER PRIMARY KEY,
    FieldID     INTEGER NOT NULL REFERENCES CountryFields(FieldID),
    SubField    TEXT NOT NULL,
    NumericVal  REAL,
    Units       TEXT,
    TextVal     TEXT,
    DateEst     TEXT,
    Rank        INTEGER
);
"""

INDEXES = """
CREATE INDEX IX_Countries_Year ON Countries(Year);
CREATE INDEX IX_Countries_Code ON Countries(Code);
CREATE INDEX IX_Countries_MasterCountryID ON Countries(MasterCountryID);
CREATE INDEX IX_Categories_Country ON CountryCategories(CountryID);
CREATE INDEX IX_Fields_Category ON CountryFields(CategoryID);
CREATE INDEX IX_Fields_Country ON CountryFields(CountryID);
CREATE INDEX IX_Fields_FieldName ON CountryFields(FieldName);
CREATE INDEX IX_FieldNameMappings_CanonicalName ON FieldNameMappings(CanonicalName);
CREATE INDEX IX_FieldNameMappings_IsNoise ON FieldNameMappings(IsNoise);
CREATE INDEX IX_FV_FieldID   ON FieldValues(FieldID);
CREATE INDEX IX_FV_SubField  ON FieldValues(SubField);
CREATE INDEX IX_FV_Numeric   ON FieldValues(NumericVal) WHERE NumericVal IS NOT NULL;
"""

# Reference tables (small — load all at once)
REF_TABLES = [
    (
        "MasterCountries",
        "SELECT MasterCountryID, CanonicalCode, CanonicalName, ISOAlpha2, EntityType, AdministeringMasterCountryID FROM MasterCountries",
        "INSERT INTO MasterCountries VALUES (?,?,?,?,?,?)",
    ),
    (
        "Countries",
        "SELECT CountryID, Year, Code, Name, Source, MasterCountryID FROM Countries",
        "INSERT INTO Countries VALUES (?,?,?,?,?,?)",
    ),
    (
        "CountryCategories",
        "SELECT CategoryID, CountryID, CategoryTitle FROM CountryCategories",
        "INSERT INTO CountryCategories VALUES (?,?,?)",
    ),
    (
        "FieldNameMappings",
        "SELECT MappingID, OriginalName, CanonicalName, MappingType, ConsolidatedTo, IsNoise, FirstYear, LastYear, UseCount, Notes FROM FieldNameMappings",
        "INSERT INTO FieldNameMappings VALUES (?,?,?,?,?,?,?,?,?,?)",
    ),
]

BATCH_SIZE = 50_000


def copy_table(ms_cursor, lite_conn, name, select_sql, insert_sql):
    """Copy a small reference table from SQL Server to SQLite."""
    t0 = time.time()
    ms_cursor.execute(select_sql)
    rows = ms_cursor.fetchall()
    lite_conn.executemany(insert_sql, [tuple(r) for r in rows])
    lite_conn.commit()
    elapsed = time.time() - t0
    print(f"  {name}: {len(rows):,} rows ({elapsed:.1f}s)")
    return len(rows)


def copy_batched(ms_cursor, lite_conn, name, select_sql, insert_sql, total_hint=0):
    """Copy a large table in batches with progress."""
    t0 = time.time()
    copied = 0

    ms_cursor.execute(select_sql)

    while True:
        rows = ms_cursor.fetchmany(BATCH_SIZE)
        if not rows:
            break
        lite_conn.executemany(insert_sql, [tuple(r) for r in rows])
        lite_conn.commit()
        copied += len(rows)
        if total_hint > 0:
            pct = copied / total_hint * 100
            elapsed = time.time() - t0
            print(f"  {name}: {copied:>12,} / {total_hint:,} ({pct:.0f}%)  [{elapsed:.0f}s]",
                  end="\r")

    elapsed = time.time() - t0
    print(f"  {name}: {copied:,} rows ({elapsed:.1f}s)                    ")
    return copied


def main():
    parser = argparse.ArgumentParser(
        description="Export FieldValues + reference tables to SQLite"
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output .db path")
    args = parser.parse_args()

    output = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output), exist_ok=True)

    if os.path.exists(output):
        os.remove(output)
        print(f"Removed existing {output}")

    print("Connecting to SQL Server...")
    ms_src = pyodbc.connect(CONN_STR_SOURCE)
    ms_tgt = pyodbc.connect(CONN_STR_TARGET)
    mc_src = ms_src.cursor()
    mc_tgt = ms_tgt.cursor()

    # Get counts for progress
    cf_count = mc_src.execute("SELECT COUNT(*) FROM CountryFields").fetchone()[0]
    fv_count = mc_tgt.execute("SELECT COUNT(*) FROM FieldValues").fetchone()[0]
    print(f"CountryFields to export: {cf_count:,}")
    print(f"FieldValues to export:   {fv_count:,}")

    print(f"\nCreating SQLite database at {output}")
    lite = sqlite3.connect(output)

    # Performance pragmas for bulk insert
    lite.execute("PRAGMA journal_mode=WAL")
    lite.execute("PRAGMA synchronous=OFF")
    lite.execute("PRAGMA cache_size=-512000")
    lite.execute("PRAGMA temp_store=MEMORY")

    # Create schema (no indexes yet — faster bulk load)
    print("Creating tables...")
    lite.executescript(SCHEMA)

    # Copy reference tables (small)
    print("\nCopying reference tables from CIA_WorldFactbook...")
    for name, select_sql, insert_sql in REF_TABLES:
        copy_table(mc_src, lite, name, select_sql, insert_sql)

    # Copy CountryFields (1M+ rows) in batches
    print("\nCopying CountryFields...")
    copy_batched(
        mc_src, lite,
        "CountryFields",
        "SELECT FieldID, CategoryID, CountryID, FieldName, Content "
        "FROM CountryFields ORDER BY FieldID",
        "INSERT INTO CountryFields VALUES (?,?,?,?,?)",
        total_hint=cf_count,
    )

    # Copy FieldValues (1.4M+ rows) in batches
    print("\nCopying FieldValues from CIA_WorldFactbook_Extended_Sub_Topics...")
    copy_batched(
        mc_tgt, lite,
        "FieldValues",
        "SELECT ValueID, FieldID, SubField, NumericVal, Units, TextVal, DateEst, Rank "
        "FROM FieldValues ORDER BY ValueID",
        "INSERT INTO FieldValues VALUES (?,?,?,?,?,?,?,?)",
        total_hint=fv_count,
    )

    # Create indexes after bulk load
    print("\nCreating indexes...")
    t1 = time.time()
    lite.executescript(INDEXES)
    lite.commit()
    print(f"  Indexes built ({time.time() - t1:.1f}s)")

    # Compact
    print("Vacuuming...")
    lite.execute("PRAGMA journal_mode=DELETE")
    lite.execute("VACUUM")
    lite.close()
    ms_src.close()
    ms_tgt.close()

    size_mb = os.path.getsize(output) / (1024 * 1024)
    print(f"\nDone. SQLite database: {size_mb:.1f} MB at {output}")
    print(f"  Tables: MasterCountries, Countries, CountryCategories,")
    print(f"          CountryFields, FieldNameMappings, FieldValues")


if __name__ == "__main__":
    main()
