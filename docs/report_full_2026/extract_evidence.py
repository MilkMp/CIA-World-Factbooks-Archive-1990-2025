"""Extract bounded, aggregate evidence for the October 2026 project report.

The database is opened read-only. Run with a named SQLite snapshot:

    python docs/report_full_2026/extract_evidence.py --db PATH/TO/factbook.db

The output records the source file hash and exact SQL for each aggregate. It is
deliberately an older local snapshot; the report labels it separately from
the live archive after the September 2026 entity repair.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


QUERIES = {
    "tables": """
        SELECT 'MasterCountries' AS name, COUNT(*) AS n FROM MasterCountries
        UNION ALL SELECT 'Countries', COUNT(*) FROM Countries
        UNION ALL SELECT 'CountryCategories', COUNT(*) FROM CountryCategories
        UNION ALL SELECT 'CountryFields', COUNT(*) FROM CountryFields
        UNION ALL SELECT 'FieldNameMappings', COUNT(*) FROM FieldNameMappings
        UNION ALL SELECT 'FieldValues', COUNT(*) FROM FieldValues
    """,
    "years": """
        WITH cy AS (SELECT Year AS year, COUNT(*) AS country_years
                    FROM Countries GROUP BY Year),
             cat AS (SELECT c.Year AS year, COUNT(*) AS categories
                     FROM CountryCategories cc JOIN Countries c ON c.CountryID=cc.CountryID
                     GROUP BY c.Year),
             fld AS (SELECT c.Year AS year, COUNT(*) AS fields,
                            COUNT(DISTINCT cf.FieldName) AS field_names
                     FROM CountryFields cf JOIN Countries c ON c.CountryID=cf.CountryID
                     GROUP BY c.Year)
        SELECT cy.year,cy.country_years,cat.categories,fld.fields,fld.field_names
        FROM cy LEFT JOIN cat USING(year) LEFT JOIN fld USING(year)
        ORDER BY cy.year
    """,
    "year_sources": """
        SELECT Year AS year, Source AS source, COUNT(*) AS country_years
        FROM Countries GROUP BY Year, Source ORDER BY Year, Source
    """,
    "field_quantiles_input": """
        SELECT c.Year AS year, c.CountryID AS country_id,
               COUNT(cf.FieldID) AS fields
        FROM Countries c
        LEFT JOIN CountryFields cf ON cf.CountryID=c.CountryID
        GROUP BY c.Year,c.CountryID ORDER BY c.Year,c.CountryID
    """,
    "entity_years": """
        SELECT mc.MasterCountryID AS entity_id,
               mc.CanonicalName AS entity_name,
               mc.EntityType AS entity_type,
               COUNT(DISTINCT c.Year) AS editions,
               COUNT(c.CountryID) AS records,
               MIN(c.Year) AS first_year, MAX(c.Year) AS last_year
        FROM MasterCountries mc
        LEFT JOIN Countries c ON c.MasterCountryID=mc.MasterCountryID
        GROUP BY mc.MasterCountryID ORDER BY mc.MasterCountryID
    """,
    "categories_2025": """
        SELECT cc.CategoryTitle AS category, COUNT(cf.FieldID) AS fields,
               COUNT(DISTINCT c.CountryID) AS country_years
        FROM Countries c
        JOIN CountryCategories cc ON cc.CountryID=c.CountryID
        LEFT JOIN CountryFields cf ON cf.CategoryID=cc.CategoryID
        WHERE c.Year=2025
        GROUP BY cc.CategoryTitle ORDER BY fields DESC
    """,
    "mapping_types": """
        SELECT MappingType AS mapping_type, COUNT(*) AS names,
               SUM(COALESCE(UseCount,0)) AS documented_uses
        FROM FieldNameMappings GROUP BY MappingType ORDER BY names DESC
    """,
    "field_values_year": """
        SELECT c.Year AS year, COUNT(fv.ValueID) AS value_count,
               SUM(CASE WHEN fv.NumericVal IS NOT NULL THEN 1 ELSE 0 END) AS numeric_values,
               SUM(CASE WHEN fv.IsComputed=1 THEN 1 ELSE 0 END) AS computed_values,
               COUNT(DISTINCT fv.FieldID) AS parent_fields
        FROM Countries c
        JOIN CountryFields cf ON cf.CountryID=c.CountryID
        LEFT JOIN FieldValues fv ON fv.FieldID=cf.FieldID
        GROUP BY c.Year ORDER BY c.Year
    """,
    "entity_types": """
        SELECT COALESCE(EntityType,'unknown') AS entity_type, COUNT(*) AS n
        FROM MasterCountries GROUP BY COALESCE(EntityType,'unknown') ORDER BY n DESC
    """,
    "top_canonical_names": """
        SELECT fm.CanonicalName AS name, SUM(COALESCE(fm.UseCount,0)) AS documented_uses,
               COUNT(*) AS original_names
        FROM FieldNameMappings fm
        WHERE fm.IsNoise=0
        GROUP BY fm.CanonicalName ORDER BY documented_uses DESC LIMIT 25
    """,
    "source_fragment": """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN SourceFragment IS NOT NULL AND TRIM(SourceFragment)!='' THEN 1 ELSE 0 END) AS populated,
               SUM(CASE WHEN IsComputed=1 THEN 1 ELSE 0 END) AS computed
        FROM FieldValues
    """,
    "category_country_mismatch": """
        SELECT c.Year AS year, c.Name AS country, cf.FieldID AS field_id,
               cf.FieldName AS field_name, cf.CountryID AS field_country_id,
               cc.CountryID AS category_country_id
        FROM CountryFields cf
        JOIN Countries c ON c.CountryID=cf.CountryID
        JOIN CountryCategories cc ON cc.CategoryID=cf.CategoryID
        WHERE cc.CountryID!=cf.CountryID ORDER BY cf.FieldID
    """,
    "unlinked_country_years": """
        SELECT Year AS year, Name AS country, CountryID AS country_id
        FROM Countries WHERE MasterCountryID IS NULL ORDER BY Year, CountryID
    """,
}

QUERIES["final_estimate_tokens"] = (
    "WITH final AS (SELECT LOWER(cf.Content) AS content "
    "FROM CountryFields cf JOIN Countries c ON c.CountryID=cf.CountryID "
    "WHERE c.Year=2025) "
    + " UNION ALL ".join(
        f"SELECT {year} AS estimate_year, "
        f"SUM(CASE WHEN INSTR(content, '{year} est.')>0 THEN 1 ELSE 0 END) "
        f"AS fields_with_token FROM final"
        for year in range(2018, 2028)
    )
)


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("evidence.json"))
    args = parser.parse_args()
    db = args.db.resolve(strict=True)
    uri = db.as_uri() + "?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    results = {}
    for name, sql in QUERIES.items():
        results[name] = [dict(row) for row in connection.execute(sql)]
    connection.close()
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "database_sha256": file_hash(db),
        "database_bytes": db.stat().st_size,
        "database_modified_utc": datetime.fromtimestamp(db.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
        "source_note": "Local SQLite snapshot; aggregate charts are not the later live post-repair database.",
        "sql": QUERIES,
        "results": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.out} from {db.name} ({len(results)} aggregate queries)")


if __name__ == "__main__":
    main()
