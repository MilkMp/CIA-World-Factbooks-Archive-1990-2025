"""
Export CIA_WorldFactbook data as SQL INSERT scripts for GitHub.

Small tables → single .sql files
CountryFields → split by year → .sql.gz files
"""
import pyodbc
import gzip
import os
import sys
import time

CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=CIA_WorldFactbook;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

REPO_DIR = r"C:\Users\milan\CIA-World-Factbooks-Archive-1990-2025\data"
BATCH_SIZE = 1000  # rows per INSERT statement


def escape_sql(val):
    """Escape a value for SQL INSERT."""
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, (int, float)):
        return str(val)
    s = str(val).replace("'", "''")
    return f"N'{s}'"


def export_table(cursor, table_name, columns, filename, order_by=None, where=None):
    """Export a table to a SQL INSERT file."""
    filepath = os.path.join(REPO_DIR, filename)
    col_names = ", ".join(columns)
    col_list = ", ".join(f"[{c}]" for c in columns)

    query = f"SELECT {col_list} FROM {table_name}"
    if where:
        query += f" WHERE {where}"
    if order_by:
        query += f" ORDER BY {order_by}"

    cursor.execute(query)
    rows = cursor.fetchall()
    total = len(rows)

    # Determine if table has identity column
    has_identity = columns[0].endswith("ID") and columns[0] in (
        "MasterCountryID", "CountryID", "CategoryID", "FieldID", "MappingID"
    )

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"-- {table_name}: {total:,} rows\n")
        f.write(f"-- Exported from CIA_WorldFactbook archive\n\n")

        if has_identity:
            f.write(f"SET IDENTITY_INSERT {table_name} ON;\nGO\n\n")

        for i in range(0, total, BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            f.write(f"INSERT INTO {table_name} ({col_names})\nVALUES\n")
            value_lines = []
            for row in batch:
                vals = ", ".join(escape_sql(v) for v in row)
                value_lines.append(f"  ({vals})")
            f.write(",\n".join(value_lines))
            f.write(";\nGO\n\n")

        if has_identity:
            f.write(f"SET IDENTITY_INSERT {table_name} OFF;\nGO\n")

    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"  {filename}: {total:,} rows, {size_mb:.1f} MB")
    return total


def export_fields_by_year(cursor, conn):
    """Export CountryFields split by year into gzipped SQL files."""
    fields_dir = os.path.join(REPO_DIR, "fields")
    os.makedirs(fields_dir, exist_ok=True)

    # Get year list
    cursor.execute("""
        SELECT DISTINCT c.Year
        FROM Countries c
        JOIN CountryFields cf ON c.CountryID = cf.CountryID
        ORDER BY c.Year
    """)
    years = [row[0] for row in cursor.fetchall()]
    print(f"\n  Exporting CountryFields for {len(years)} years...")

    total_rows = 0
    total_size = 0

    for year in years:
        start = time.time()
        cursor.execute("""
            SELECT cf.FieldID, cf.CategoryID, cf.CountryID, cf.FieldName, cf.Content
            FROM CountryFields cf
            JOIN Countries c ON cf.CountryID = c.CountryID
            WHERE c.Year = ?
            ORDER BY cf.FieldID
        """, year)
        rows = cursor.fetchall()
        count = len(rows)

        filename = f"country_fields_{year}.sql.gz"
        filepath = os.path.join(fields_dir, filename)

        columns = ["FieldID", "CategoryID", "CountryID", "FieldName", "Content"]
        col_names = ", ".join(columns)

        with gzip.open(filepath, 'wt', encoding='utf-8', compresslevel=9) as f:
            f.write(f"-- CountryFields for year {year}: {count:,} rows\n")
            f.write(f"-- Exported from CIA_WorldFactbook archive\n\n")
            f.write("SET IDENTITY_INSERT CountryFields ON;\nGO\n\n")

            for i in range(0, count, BATCH_SIZE):
                batch = rows[i:i + BATCH_SIZE]
                f.write(f"INSERT INTO CountryFields ({col_names})\nVALUES\n")
                value_lines = []
                for row in batch:
                    vals = ", ".join(escape_sql(v) for v in row)
                    value_lines.append(f"  ({vals})")
                f.write(",\n".join(value_lines))
                f.write(";\nGO\n\n")

            f.write("SET IDENTITY_INSERT CountryFields OFF;\nGO\n")

        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        elapsed = time.time() - start
        total_rows += count
        total_size += os.path.getsize(filepath)
        print(f"    {year}: {count:,} rows -> {filename} ({size_mb:.1f} MB, {elapsed:.1f}s)")

    print(f"\n  Total: {total_rows:,} rows, {total_size / (1024*1024):.1f} MB compressed")
    return total_rows


def main():
    print("=" * 60)
    print("CIA FACTBOOK ARCHIVE — DATA EXPORT")
    print("=" * 60)

    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()
    print("Connected to database.\n")

    # 1. MasterCountries
    print("Exporting MasterCountries...")
    export_table(cursor, "MasterCountries",
                 ["MasterCountryID", "CanonicalCode", "CanonicalName", "ISOAlpha2", "EntityType", "AdministeringMasterCountryID"],
                 "master_countries.sql",
                 order_by="MasterCountryID")

    # 2. Countries
    print("\nExporting Countries...")
    export_table(cursor, "Countries",
                 ["CountryID", "Year", "Code", "Name", "Source", "MasterCountryID"],
                 "countries.sql",
                 order_by="CountryID")

    # 3. CountryCategories
    print("\nExporting CountryCategories...")
    export_table(cursor, "CountryCategories",
                 ["CategoryID", "CountryID", "CategoryTitle"],
                 "categories.sql",
                 order_by="CategoryID")

    # 4. FieldNameMappings
    print("\nExporting FieldNameMappings...")
    export_table(cursor, "FieldNameMappings",
                 ["MappingID", "OriginalName", "CanonicalName", "MappingType", "ConsolidatedTo", "IsNoise", "FirstYear", "LastYear", "UseCount", "Notes"],
                 "field_name_mappings.sql",
                 order_by="MappingID")

    # 5. CountryFields by year
    print("\nExporting CountryFields (by year, gzipped)...")
    export_fields_by_year(cursor, conn)

    cursor.close()
    conn.close()

    # Summary
    print(f"\n{'=' * 60}")
    print("EXPORT COMPLETE")
    print(f"{'=' * 60}")
    print(f"Output directory: {REPO_DIR}")

    # File sizes
    total = 0
    for root, dirs, files in os.walk(REPO_DIR):
        for f in sorted(files):
            fp = os.path.join(root, f)
            size = os.path.getsize(fp)
            total += size
            rel = os.path.relpath(fp, REPO_DIR)
            print(f"  {rel}: {size / (1024*1024):.1f} MB")
    print(f"\n  TOTAL: {total / (1024*1024):.1f} MB")


if __name__ == "__main__":
    main()
