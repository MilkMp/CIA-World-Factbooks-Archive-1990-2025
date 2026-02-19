"""Analysis routes: global trends, field explorer, quiz game."""
import random
from collections import defaultdict
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from webapp.database import sql, sql_one
from webapp.parsers import (
    extract_number, extract_pct_gdp, extract_pct,
    extract_gdp_percap, parse_life_exp, extract_growth_rate,
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


def _latest_year():
    row = sql_one("SELECT MAX(Year) AS yr FROM Countries")
    return row['yr'] if row and row['yr'] else 2025

ANALYSIS_YEAR = _latest_year()


# ══════════════════════════════════════════════════════════════════════
#  FEATURE: GLOBAL TRENDS
# ══════════════════════════════════════════════════════════════════════

TRENDS_INDICATORS = {
    'population':   ('Population', extract_number, 'sum',
                     'World Population', '{:,.0f}'),
    'life_exp':     ('Life expectancy at birth', parse_life_exp, 'mean',
                     'Avg. Life Expectancy', '{:.1f} yrs'),
    'gdp_percap':   ('Real GDP per capita', extract_gdp_percap, 'mean',
                     'Avg. GDP per Capita', '${:,}'),
    'internet_pct': ('Internet users', extract_pct, 'mean',
                     'Avg. Internet Users', '{:.1f}%'),
    'mil_pct_gdp':  ('Military expenditures', extract_pct_gdp, 'mean',
                     'Avg. Military % GDP', '{:.2f}%'),
    'pop_growth':   ('Population growth rate', extract_growth_rate, 'mean',
                     'Avg. Pop. Growth', '{:.2f}%'),
}

TRENDS_COLORS = {
    'population':   '#4C90F0',
    'life_exp':     '#32A467',
    'gdp_percap':   '#F0B726',
    'internet_pct': '#C274C2',
    'mil_pct_gdp':  '#CD4246',
    'pop_growth':   '#2D72D2',
}

MIN_COUNTRIES_PER_YEAR = 20


def _compute_trends():
    """Aggregate indicator values across all sovereign countries per year."""
    results = {}

    for key, (field_name, parser, agg, label, fmt) in TRENDS_INDICATORS.items():
        rows = sql("""
            SELECT c.Year, cf.Content
            FROM CountryFields cf
            JOIN Countries c ON cf.CountryID = c.CountryID
            JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
            JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
            WHERE fm.CanonicalName = ? AND fm.IsNoise = 0
              AND mc.EntityType = 'sovereign'
            ORDER BY c.Year
        """, [field_name])

        by_year = defaultdict(list)
        for r in rows:
            val = parser(r['Content'])
            if val is not None:
                by_year[r['Year']].append(val)

        series = []
        for year in sorted(by_year.keys()):
            vals = by_year[year]
            if len(vals) < MIN_COUNTRIES_PER_YEAR:
                continue
            if agg == 'sum':
                value = sum(vals)
            else:
                value = sum(vals) / len(vals)
            series.append({'year': year, 'value': round(value, 2), 'n': len(vals)})

        results[key] = series

    return results


@router.get("/analysis/trends")
async def trends_page(request: Request):
    trends = _compute_trends()

    # Current year KPIs
    kpis = {}
    for key, series in trends.items():
        if series:
            latest = series[-1]
            kpis[key] = latest['value']
        else:
            kpis[key] = None

    return templates.TemplateResponse("analysis/trends.html", {
        "request": request,
        "trends": trends,
        "kpis": kpis,
        "indicators": {k: (v[3], v[4]) for k, v in TRENDS_INDICATORS.items()},
        "colors": TRENDS_COLORS,
    })


@router.get("/api/analysis/trends")
async def api_trends():
    return _compute_trends()


# ══════════════════════════════════════════════════════════════════════
#  FEATURE: FIELD EXPLORER
# ══════════════════════════════════════════════════════════════════════

@router.get("/analysis/fields")
async def field_explorer_page(request: Request):
    fields = sql("""
        SELECT CanonicalName,
               COUNT(*) AS Variants,
               MIN(FirstYear) AS FirstYear,
               MAX(LastYear) AS LastYear,
               SUM(UseCount) AS TotalUses
        FROM FieldNameMappings WHERE IsNoise = 0
        GROUP BY CanonicalName
        ORDER BY CanonicalName
    """)

    total_variants = sql_one(
        "SELECT COUNT(*) AS cnt FROM FieldNameMappings WHERE IsNoise = 0"
    )

    return templates.TemplateResponse("analysis/field_explorer.html", {
        "request": request,
        "fields": fields,
        "total_canonical": len(fields),
        "total_variants": total_variants['cnt'] if total_variants else 0,
    })


@router.get("/api/analysis/field-explorer")
async def api_field_list():
    return sql("""
        SELECT CanonicalName,
               COUNT(*) AS Variants,
               MIN(FirstYear) AS FirstYear,
               MAX(LastYear) AS LastYear,
               SUM(UseCount) AS TotalUses
        FROM FieldNameMappings WHERE IsNoise = 0
        GROUP BY CanonicalName
        ORDER BY CanonicalName
    """)


@router.get("/api/analysis/field-explorer/{name:path}")
async def api_field_detail(name: str):
    # Coverage by year
    coverage = sql("""
        SELECT c.Year, COUNT(DISTINCT c.MasterCountryID) AS Countries
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE fm.CanonicalName = ? AND fm.IsNoise = 0
        GROUP BY c.Year ORDER BY c.Year
    """, [name])

    # Original name variants
    variants = sql("""
        SELECT OriginalName, FirstYear, LastYear, UseCount
        FROM FieldNameMappings
        WHERE CanonicalName = ? AND IsNoise = 0
        ORDER BY UseCount DESC
    """, [name])

    # Find latest year with data
    latest_row = sql_one("""
        SELECT MAX(c.Year) AS yr
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE fm.CanonicalName = ? AND fm.IsNoise = 0
    """, [name])
    latest_year = latest_row['yr'] if latest_row and latest_row['yr'] else ANALYSIS_YEAR

    # Sample values
    samples = sql("""
        SELECT mc.CanonicalName AS Country, cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE fm.CanonicalName = ? AND c.Year = ? AND fm.IsNoise = 0
          AND mc.EntityType = 'sovereign'
        ORDER BY mc.CanonicalName LIMIT 10
    """, [name, latest_year])

    return {
        "name": name,
        "coverage": coverage,
        "variants": variants,
        "samples": samples,
        "sample_year": latest_year,
    }


# ══════════════════════════════════════════════════════════════════════
#  FEATURE: QUIZ GAME
# ══════════════════════════════════════════════════════════════════════

QUIZ_CLUE_FIELDS = [
    'Location',
    'Climate',
    'Government type',
    'Ethnic groups',
    'Languages',
    'Religions',
    'Area - comparative',
    'Flag description',
    'Capital',
    'Population',
]

# Ordered from hardest (first revealed) to easiest (last revealed)
CLUE_PRIORITY = {f: i for i, f in enumerate(QUIZ_CLUE_FIELDS)}


@router.get("/analysis/quiz")
async def quiz_page(request: Request):
    return templates.TemplateResponse("analysis/quiz.html", {
        "request": request,
    })


@router.get("/api/analysis/quiz/question")
async def api_quiz_question():
    year = ANALYSIS_YEAR

    # Pick a random sovereign country
    country = sql_one("""
        SELECT mc.MasterCountryID, mc.CanonicalName, mc.ISOAlpha2
        FROM Countries c
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        WHERE c.Year = ? AND mc.EntityType = 'sovereign'
        ORDER BY RANDOM() LIMIT 1
    """, [year])

    if not country:
        return {"error": "No countries found"}

    # Fetch clue fields
    placeholders = ','.join(['?'] * len(QUIZ_CLUE_FIELDS))
    clue_rows = sql(f"""
        SELECT fm.CanonicalName AS field, cf.Content AS value
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE c.Year = ? AND c.MasterCountryID = ? AND fm.IsNoise = 0
          AND fm.CanonicalName IN ({placeholders})
    """, [year, country['MasterCountryID']] + QUIZ_CLUE_FIELDS)

    # Build clues, sorted hardest first
    clues = []
    for r in clue_rows:
        val = r['value'].strip() if r['value'] else ''
        if len(val) > 5:
            # Truncate very long values
            if len(val) > 300:
                val = val[:300] + '...'
            clues.append({'field': r['field'], 'value': val})

    clues.sort(key=lambda c: CLUE_PRIORITY.get(c['field'], 99))
    clues = clues[:5]

    if len(clues) < 3:
        # Not enough clues, try again with another random call
        return await api_quiz_question()

    # Pick 3 wrong answers
    wrong = sql("""
        SELECT DISTINCT mc.CanonicalName
        FROM Countries c
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        WHERE c.Year = ? AND mc.EntityType = 'sovereign'
          AND mc.MasterCountryID != ?
        ORDER BY RANDOM() LIMIT 3
    """, [year, country['MasterCountryID']])

    options = [w['CanonicalName'] for w in wrong] + [country['CanonicalName']]
    random.shuffle(options)

    return {
        "answer": country['CanonicalName'],
        "iso2": country['ISOAlpha2'],
        "clues": clues,
        "options": options,
    }
