import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pyodbc
import polars as pl

conn = pyodbc.connect(
    'DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=CIA_WorldFactbook;'
    'Trusted_Connection=yes;TrustServerCertificate=yes;'
)
cursor = conn.cursor()

cursor.execute('''
    SELECT c.Year, cc.CategoryTitle, COUNT(cf.FieldID) as FieldCount,
           COUNT(DISTINCT c.CountryID) as CountryCount
    FROM Countries c
    JOIN CountryCategories cc ON c.CountryID = cc.CountryID
    JOIN CountryFields cf ON cc.CategoryID = cf.CategoryID
    WHERE c.Year IN (2023, 2024, 2025)
    GROUP BY c.Year, cc.CategoryTitle
    ORDER BY c.Year, COUNT(cf.FieldID) DESC
''')
rows = cursor.fetchall()

df = pl.DataFrame({
    'Year': [r[0] for r in rows],
    'Category': [r[1] for r in rows],
    'Fields': [r[2] for r in rows],
    'Countries': [r[3] for r in rows],
})

pl.Config.set_tbl_rows(20)
pl.Config.set_fmt_str_lengths(40)

for yr in [2023, 2024, 2025]:
    ydf = df.filter(pl.col('Year') == yr).select(['Category', 'Fields', 'Countries']).sort('Fields', descending=True)
    total = ydf['Fields'].sum()
    print(f'\n{"=" * 60}')
    print(f'  {yr}  |  {ydf.height} categories  |  {total:,} fields')
    print(f'{"=" * 60}')
    print(ydf)

# US spot check
print(f'\n{"=" * 60}')
print(f'  US SPOT CHECK')
print(f'{"=" * 60}')
for yr in [2023, 2024, 2025]:
    cursor.execute('''
        SELECT cc.CategoryTitle, COUNT(cf.FieldID) as fc
        FROM Countries c
        JOIN CountryCategories cc ON c.CountryID = cc.CountryID
        JOIN CountryFields cf ON cc.CategoryID = cf.CategoryID
        WHERE c.Year = ? AND c.Name LIKE '%%United States%%'
        GROUP BY cc.CategoryTitle ORDER BY fc DESC
    ''', yr)
    print(f'\n  {yr} United States:')
    for r in cursor.fetchall():
        print(f'    {r[0]:25s} {r[1]:>3} fields')

# Sample fields for US 2025
cursor.execute('''
    SELECT cc.CategoryTitle, cf.FieldName, LEFT(cf.Content, 80)
    FROM Countries c
    JOIN CountryCategories cc ON c.CountryID = cc.CountryID
    JOIN CountryFields cf ON cc.CategoryID = cf.CategoryID
    WHERE c.Year = 2025 AND c.Name LIKE '%%United States%%'
    ORDER BY cc.CategoryTitle, cf.FieldID
''')
print(f'\n{"=" * 60}')
print(f'  US 2025 - ALL FIELDS')
print(f'{"=" * 60}')
cur_cat = None
for r in cursor.fetchall():
    cat, fname, content = r[0], r[1], r[2]
    if cat != cur_cat:
        cur_cat = cat
        print(f'\n  [{cur_cat}]')
    print(f'    {fname:40s} {content}')

conn.close()
