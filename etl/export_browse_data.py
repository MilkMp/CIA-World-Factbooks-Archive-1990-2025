"""Export entity list and year summary as JSON for GitHub Pages static browse."""
import json
import pyodbc

CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;DATABASE=CIA_WorldFactbook;"
    "Trusted_Connection=yes;TrustServerCertificate=yes;"
)

conn = pyodbc.connect(CONN_STR)
cursor = conn.cursor()

# --- Entity list (281 rows) ---
cursor.execute("""
    SELECT mc.CanonicalName, mc.CanonicalCode, mc.ISOAlpha2, mc.EntityType,
           MIN(c.Year) AS FirstYear, MAX(c.Year) AS LastYear,
           COUNT(DISTINCT c.Year) AS YearsCovered,
           ISNULL(SUM(fc.Fields), 0) AS TotalFields
    FROM MasterCountries mc
    JOIN Countries c ON mc.MasterCountryID = c.MasterCountryID
    LEFT JOIN (
        SELECT CountryID, COUNT(*) AS Fields FROM CountryFields GROUP BY CountryID
    ) fc ON c.CountryID = fc.CountryID
    GROUP BY mc.CanonicalName, mc.CanonicalCode, mc.ISOAlpha2, mc.EntityType
    ORDER BY mc.CanonicalName
""")
entities = []
for row in cursor.fetchall():
    entities.append({
        "name": row.CanonicalName,
        "fips": row.CanonicalCode,
        "iso2": row.ISOAlpha2 or "",
        "type": row.EntityType or "unknown",
        "first": row.FirstYear,
        "last": row.LastYear,
        "years": row.YearsCovered,
        "fields": row.TotalFields,
    })

# --- Year summary (36 rows) ---
cursor.execute("""
    SELECT c.Year, c.Source,
           COUNT(DISTINCT c.CountryID) AS Countries,
           COUNT(cf.FieldID) AS Fields
    FROM Countries c
    LEFT JOIN CountryFields cf ON c.CountryID = cf.CountryID
    GROUP BY c.Year, c.Source
    ORDER BY c.Year
""")
years = []
for row in cursor.fetchall():
    years.append({
        "year": row.Year,
        "source": row.Source,
        "countries": row.Countries,
        "fields": row.Fields,
    })

conn.close()

print(f"Entities: {len(entities)}")
print(f"Years: {len(years)}")

# Output as JSON
data = {"entities": entities, "years": years}
print(json.dumps(data, indent=2))
