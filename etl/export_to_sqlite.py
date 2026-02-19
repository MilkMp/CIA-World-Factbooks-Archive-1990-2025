"""
Export CIA_WorldFactbook from SQL Server to SQLite.

Reads all 5 tables from the local SQL Server instance and writes them
to a single SQLite .db file suitable for deployment (read-only webapp).

Usage:
    python export_to_sqlite.py [--output path/to/factbook.db]
"""

import argparse
import os
import sqlite3
import time

import pyodbc

CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;DATABASE=CIA_WorldFactbook;"
    "Trusted_Connection=yes;TrustServerCertificate=yes;"
)

DEFAULT_OUTPUT = os.path.join(os.path.dirname(__file__), "data", "factbook.db")

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
"""

TABLES = [
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
    """Copy a table from SQL Server to SQLite."""
    t0 = time.time()
    ms_cursor.execute(select_sql)
    rows = ms_cursor.fetchall()
    lite_conn.executemany(insert_sql, [tuple(r) for r in rows])
    lite_conn.commit()
    elapsed = time.time() - t0
    print(f"  {name}: {len(rows):,} rows ({elapsed:.1f}s)")
    return len(rows)


def copy_fields(ms_cursor, lite_conn):
    """Copy CountryFields in batches (largest table)."""
    t0 = time.time()
    total = 0

    ms_cursor.execute(
        "SELECT FieldID, CategoryID, CountryID, FieldName, Content "
        "FROM CountryFields ORDER BY FieldID"
    )

    while True:
        rows = ms_cursor.fetchmany(BATCH_SIZE)
        if not rows:
            break
        lite_conn.executemany(
            "INSERT INTO CountryFields VALUES (?,?,?,?,?)",
            [tuple(r) for r in rows],
        )
        lite_conn.commit()
        total += len(rows)
        print(f"  CountryFields: {total:,} rows...", end="\r")

    elapsed = time.time() - t0
    print(f"  CountryFields: {total:,} rows ({elapsed:.1f}s)")
    return total


def main():
    parser = argparse.ArgumentParser(description="Export CIA_WorldFactbook to SQLite")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output .db path")
    args = parser.parse_args()

    output = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output), exist_ok=True)

    if os.path.exists(output):
        os.remove(output)
        print(f"Removed existing {output}")

    print("Connecting to SQL Server...")
    ms = pyodbc.connect(CONN_STR)
    mc = ms.cursor()

    print(f"Creating SQLite database at {output}")
    lite = sqlite3.connect(output)

    # Performance pragmas for bulk insert
    lite.execute("PRAGMA journal_mode=WAL")
    lite.execute("PRAGMA synchronous=OFF")
    lite.execute("PRAGMA cache_size=-512000")
    lite.execute("PRAGMA temp_store=MEMORY")

    # Create schema (no indexes yet — faster bulk load)
    print("Creating tables...")
    lite.executescript(SCHEMA)

    # Copy small tables
    print("Copying tables...")
    for name, select_sql, insert_sql in TABLES:
        copy_table(mc, lite, name, select_sql, insert_sql)

    # Copy CountryFields (1M+ rows) in batches
    copy_fields(mc, lite)

    # Create indexes after data load
    print("Creating indexes...")
    lite.executescript(INDEXES)
    lite.commit()

    # Full-text search index
    print("Creating FTS5 full-text search index...")
    lite.execute("""
        CREATE VIRTUAL TABLE CountryFieldsFTS USING fts5(
            Content,
            content='CountryFields',
            content_rowid='FieldID'
        )
    """)
    lite.execute("""
        INSERT INTO CountryFieldsFTS(rowid, Content)
        SELECT FieldID, Content FROM CountryFields
    """)
    lite.commit()
    print("  FTS5 index built.")

    # Compact
    print("Vacuuming...")
    lite.execute("PRAGMA journal_mode=DELETE")
    lite.execute("VACUUM")
    lite.close()
    ms.close()

    size_mb = os.path.getsize(output) / (1024 * 1024)
    print(f"\nDone. SQLite database: {size_mb:.1f} MB at {output}")


if __name__ == "__main__":
    main()
