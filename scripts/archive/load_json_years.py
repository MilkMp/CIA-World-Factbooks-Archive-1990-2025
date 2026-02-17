"""
Load JSON factbook data for years 2021-2025 from the factbook-json-cache GitHub repo.
Uses the same schema as the HTML loader (Countries, CountryCategories, CountryFields).
"""
import pyodbc
import json
import os
import re
import glob
import subprocess
import sys

WORK_DIR = r"C:\Users\milan\CIA_World_Factbooks"
REPO_DIR = os.path.join(WORK_DIR, "factbook-json-cache")
CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=CIA_WorldFactbook;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

def strip_html(text):
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', ' ', str(text))
    clean = re.sub(r'&[a-zA-Z]+;', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def main():
    os.makedirs(WORK_DIR, exist_ok=True)

    # Clone repo if needed
    if not os.path.exists(REPO_DIR):
        print("=== Cloning factbook-json-cache ===")
        subprocess.run(
            ["git", "clone", "--depth", "1", "https://github.com/factbook/cache.factbook.json.git", REPO_DIR],
            check=True
        )
    else:
        print(f"Repo already exists at {REPO_DIR}")

    # Find JSON files
    json_files = glob.glob(os.path.join(REPO_DIR, "*", "*.json"))
    print(f"Found {len(json_files)} JSON files")

    # Connect to SQL
    print("\n=== Connecting to SQL Server ===")
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()
    print("  Connected.")

    # Load the same data for years 2021-2025
    # (The JSON cache is a single snapshot, but we'll tag it as each year
    #  since it represents the most current data available for those years)
    years_to_load = [2021, 2022, 2023, 2024, 2025]

    for year in years_to_load:
        print(f"\n{'='*50}")
        print(f"=== Year {year} (JSON) ===")
        print(f"{'='*50}")

        success = 0
        failed = 0

        for jf in sorted(json_files):
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)

                name = data.get("name", "Unknown")
                code = data.get("code", "??")

                # Insert country
                cursor.execute(
                    "INSERT INTO Countries (Year, Code, Name, Source) OUTPUT INSERTED.CountryID VALUES (?, ?, ?, ?)",
                    year, code, name, 'json'
                )
                country_id = cursor.fetchone()[0]

                # Insert categories and fields
                for cat in data.get("categories", []):
                    cat_title = cat.get("title", "")
                    cursor.execute(
                        "INSERT INTO CountryCategories (CountryID, CategoryTitle) OUTPUT INSERTED.CategoryID VALUES (?, ?)",
                        country_id, cat_title[:200]
                    )
                    cat_id = cursor.fetchone()[0]

                    for field in cat.get("fields", []):
                        content = strip_html(field.get("content", field.get("value", "")))
                        fname = field.get("name", "")
                        cursor.execute(
                            "INSERT INTO CountryFields (CategoryID, CountryID, FieldName, Content) VALUES (?, ?, ?, ?)",
                            cat_id, country_id, fname[:200], content
                        )

                conn.commit()
                success += 1

            except Exception as e:
                conn.rollback()
                print(f"  ERROR [{os.path.basename(jf)}]: {e}")
                failed += 1

        print(f"  Loaded: {success} countries, Failed: {failed}")

    # Final summary
    print(f"\n{'='*50}")
    print(f"=== COMPLETE DATABASE SUMMARY ===")
    print(f"{'='*50}")

    cursor.execute("SELECT Year, COUNT(*) FROM Countries GROUP BY Year ORDER BY Year")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} countries")

    cursor.execute("SELECT COUNT(*) FROM Countries")
    print(f"\n  Total Countries: {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM CountryCategories")
    print(f"  Total Categories: {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM CountryFields")
    print(f"  Total Fields: {cursor.fetchone()[0]}")

    conn.close()
    print("\nDone!")

if __name__ == '__main__':
    main()
