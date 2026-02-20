"""Analysis routes: global trends, field explorer, quiz game."""
import re
import random
from collections import defaultdict
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from webapp.database import sql, sql_one
from webapp.parsers import (
    extract_number, extract_pct_gdp, extract_pct,
    extract_gdp_percap, parse_life_exp, extract_growth_rate,
    extract_capital_name, extract_area,
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
    """Aggregate indicator values across all countries per year."""
    results = {}

    for key, (field_name, parser, agg, label, fmt) in TRENDS_INDICATORS.items():
        rows = sql("""
            SELECT c.Year, cf.Content
            FROM CountryFields cf
            JOIN Countries c ON cf.CountryID = c.CountryID
            JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
            JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
            WHERE fm.CanonicalName = ? AND fm.IsNoise = 0
              AND (mc.EntityType = 'sovereign'
                   OR NOT EXISTS (
                       SELECT 1 FROM MasterCountries mc2
                       WHERE mc2.ISOAlpha2 = mc.ISOAlpha2
                         AND mc2.EntityType = 'sovereign'
                         AND mc2.MasterCountryID != mc.MasterCountryID))
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
          AND (mc.EntityType = 'sovereign'
               OR NOT EXISTS (
                   SELECT 1 FROM MasterCountries mc2
                   WHERE mc2.ISOAlpha2 = mc.ISOAlpha2
                     AND mc2.EntityType = 'sovereign'
                     AND mc2.MasterCountryID != mc.MasterCountryID))
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
    'Flag',
    'Capital',
    'Population',
]

CLUE_PRIORITY = {f: i for i, f in enumerate(QUIZ_CLUE_FIELDS)}

HIGHER_LOWER_STATS = [
    {'field': 'Population',              'label': 'Population',
     'parser': extract_number,           'format': '{:,}'},
    {'field': 'Area',                    'label': 'Total Area (sq km)',
     'parser': extract_area,             'format': '{:,}'},
    {'field': 'Real GDP per capita',     'label': 'GDP per Capita',
     'parser': extract_gdp_percap,       'format': '${:,}'},
    {'field': 'Life expectancy at birth', 'label': 'Life Expectancy',
     'parser': parse_life_exp,           'format': '{:.1f} yrs'},
]


def _strip_flag_text(text):
    """Remove 'description:' prefix and 'meaning:'/'history:' subsections."""
    text = re.sub(r'^description\s*:\s*', '', text.strip(), flags=re.IGNORECASE)
    m = re.search(r'\b(meaning|history)\s*:', text, re.IGNORECASE)
    if m:
        text = text[:m.start()].strip().rstrip(',;')
    return text


def _build_exclude_ids(exclude):
    if not exclude:
        return []
    names = [n.strip() for n in exclude.split(",") if n.strip()]
    if not names:
        return []
    ph = ','.join(['?'] * len(names))
    rows = sql(f"SELECT MasterCountryID FROM MasterCountries WHERE CanonicalName IN ({ph})", names)
    return [r['MasterCountryID'] for r in rows]


def _pick_random_country(year, exclude_ids):
    if exclude_ids:
        ex_ph = ','.join(['?'] * len(exclude_ids))
        return sql_one(f"""
            SELECT mc.MasterCountryID, mc.CanonicalName, mc.ISOAlpha2
            FROM Countries c
            JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
            WHERE c.Year = ?
              AND (mc.EntityType = 'sovereign'
                   OR NOT EXISTS (
                       SELECT 1 FROM MasterCountries mc2
                       WHERE mc2.ISOAlpha2 = mc.ISOAlpha2
                         AND mc2.EntityType = 'sovereign'
                         AND mc2.MasterCountryID != mc.MasterCountryID))
              AND mc.MasterCountryID NOT IN ({ex_ph})
            ORDER BY RANDOM() LIMIT 1
        """, [year] + exclude_ids)
    return sql_one("""
        SELECT mc.MasterCountryID, mc.CanonicalName, mc.ISOAlpha2
        FROM Countries c
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        WHERE c.Year = ?
          AND (mc.EntityType = 'sovereign'
               OR NOT EXISTS (
                   SELECT 1 FROM MasterCountries mc2
                   WHERE mc2.ISOAlpha2 = mc.ISOAlpha2
                     AND mc2.EntityType = 'sovereign'
                     AND mc2.MasterCountryID != mc.MasterCountryID))
        ORDER BY RANDOM() LIMIT 1
    """, [year])


def _pick_wrong_countries(year, exclude_id, n=3):
    rows = sql("""
        SELECT DISTINCT mc.CanonicalName
        FROM Countries c
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        WHERE c.Year = ?
          AND (mc.EntityType = 'sovereign'
               OR NOT EXISTS (
                   SELECT 1 FROM MasterCountries mc2
                   WHERE mc2.ISOAlpha2 = mc.ISOAlpha2
                     AND mc2.EntityType = 'sovereign'
                     AND mc2.MasterCountryID != mc.MasterCountryID))
          AND mc.MasterCountryID != ?
        ORDER BY RANDOM() LIMIT ?
    """, [year, exclude_id, n])
    return [r['CanonicalName'] for r in rows]


@router.get("/analysis/quiz")
async def quiz_page(request: Request):
    return templates.TemplateResponse("analysis/quiz.html", {"request": request})


@router.get("/api/analysis/quiz/question")
async def api_quiz_question(mode: str = "country", exclude: str = ""):
    year = ANALYSIS_YEAR
    exclude_ids = _build_exclude_ids(exclude)

    if mode == "capital":
        return _quiz_capital(year, exclude_ids)
    elif mode == "higher-lower":
        return _quiz_higher_lower(year, exclude_ids)
    elif mode == "flag":
        return _quiz_flag(year, exclude_ids, exclude)
    else:
        return _quiz_country(year, exclude_ids, exclude)


def _quiz_country(year, exclude_ids, exclude_str):
    country = _pick_random_country(year, exclude_ids)
    if not country:
        return {"error": "No countries found"}

    placeholders = ','.join(['?'] * len(QUIZ_CLUE_FIELDS))
    clue_rows = sql(f"""
        SELECT fm.CanonicalName AS field, cf.Content AS value
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE c.Year = ? AND c.MasterCountryID = ? AND fm.IsNoise = 0
          AND fm.CanonicalName IN ({placeholders})
        GROUP BY fm.CanonicalName
    """, [year, country['MasterCountryID']] + QUIZ_CLUE_FIELDS)

    clues = []
    for r in clue_rows:
        val = r['value'].strip() if r['value'] else ''
        if r['field'] == 'Flag':
            val = _strip_flag_text(val)
        if len(val) > 5:
            if len(val) > 300:
                val = val[:300] + '...'
            clues.append({'field': r['field'], 'value': val})

    clues.sort(key=lambda c: CLUE_PRIORITY.get(c['field'], 99))
    clues = clues[:5]

    if len(clues) < 3:
        return _quiz_country(year, exclude_ids + [country['MasterCountryID']], exclude_str)

    wrong = _pick_wrong_countries(year, country['MasterCountryID'])
    options = wrong + [country['CanonicalName']]
    random.shuffle(options)

    return {
        "mode": "country",
        "answer": country['CanonicalName'],
        "iso2": country['ISOAlpha2'],
        "clues": clues,
        "options": options,
    }


def _quiz_capital(year, exclude_ids):
    country = _pick_random_country(year, exclude_ids)
    if not country:
        return {"error": "No countries found"}

    cap_row = sql_one("""
        SELECT cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE c.Year = ? AND c.MasterCountryID = ?
          AND fm.CanonicalName = 'Capital' AND fm.IsNoise = 0
        LIMIT 1
    """, [year, country['MasterCountryID']])

    correct_cap = extract_capital_name(cap_row['Content']) if cap_row else None
    if not correct_cap:
        return _quiz_capital(year, exclude_ids + [country['MasterCountryID']])

    # Fetch 15 random capitals for wrong answers
    wrong_rows = sql("""
        SELECT cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE c.Year = ?
          AND (mc.EntityType = 'sovereign'
               OR NOT EXISTS (
                   SELECT 1 FROM MasterCountries mc2
                   WHERE mc2.ISOAlpha2 = mc.ISOAlpha2
                     AND mc2.EntityType = 'sovereign'
                     AND mc2.MasterCountryID != mc.MasterCountryID))
          AND mc.MasterCountryID != ?
          AND fm.CanonicalName = 'Capital' AND fm.IsNoise = 0
        ORDER BY RANDOM() LIMIT 15
    """, [year, country['MasterCountryID']])

    wrong_caps = []
    for r in wrong_rows:
        cap = extract_capital_name(r['Content'])
        if cap and cap != correct_cap and cap not in wrong_caps:
            wrong_caps.append(cap)
        if len(wrong_caps) == 3:
            break

    if len(wrong_caps) < 3:
        return {"error": "Not enough capital data"}

    options = wrong_caps + [correct_cap]
    random.shuffle(options)

    return {
        "mode": "capital",
        "country": country['CanonicalName'],
        "iso2": country['ISOAlpha2'],
        "answer": correct_cap,
        "options": options,
    }


def _quiz_higher_lower(year, exclude_ids):
    stat = random.choice(HIGHER_LOWER_STATS)

    rows = sql("""
        SELECT mc.MasterCountryID, mc.CanonicalName, mc.ISOAlpha2, cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE c.Year = ?
          AND (mc.EntityType = 'sovereign'
               OR NOT EXISTS (
                   SELECT 1 FROM MasterCountries mc2
                   WHERE mc2.ISOAlpha2 = mc.ISOAlpha2
                     AND mc2.EntityType = 'sovereign'
                     AND mc2.MasterCountryID != mc.MasterCountryID))
          AND fm.CanonicalName = ? AND fm.IsNoise = 0
    """, [year, stat['field']])

    candidates = []
    for r in rows:
        val = stat['parser'](r['Content'])
        if val is not None and r['MasterCountryID'] not in exclude_ids:
            candidates.append({
                'id': r['MasterCountryID'],
                'name': r['CanonicalName'],
                'iso2': r['ISOAlpha2'],
                'value': val,
            })

    if len(candidates) < 2:
        return {"error": "Not enough data"}

    a, b = random.sample(candidates, 2)

    # Avoid ties -- pick a new b if values match
    if a['value'] == b['value']:
        others = [c for c in candidates if c['id'] != a['id'] and c['value'] != a['value']]
        if others:
            b = random.choice(others)
        else:
            return {"error": "Not enough distinct values"}

    answer = "higher" if b['value'] > a['value'] else "lower"

    return {
        "mode": "higher-lower",
        "stat_label": stat['label'],
        "country_a": a['name'],
        "iso2_a": a['iso2'],
        "value_a": stat['format'].format(a['value']),
        "country_b": b['name'],
        "iso2_b": b['iso2'],
        "answer": answer,
        "reveal_value": stat['format'].format(b['value']),
        "used_names": [a['name'], b['name']],
    }


def _quiz_flag(year, exclude_ids, exclude_str):
    country = _pick_random_country(year, exclude_ids)
    if not country:
        return {"error": "No countries found"}

    flag_row = sql_one("""
        SELECT cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE c.Year = ? AND c.MasterCountryID = ?
          AND fm.CanonicalName = 'Flag' AND fm.IsNoise = 0
        LIMIT 1
    """, [year, country['MasterCountryID']])

    if not flag_row:
        return _quiz_flag(year, exclude_ids + [country['MasterCountryID']], exclude_str)

    raw = _strip_flag_text(flag_row['Content'])
    if len(raw) < 20:
        return _quiz_flag(year, exclude_ids + [country['MasterCountryID']], exclude_str)

    # Split into sentences for progressive reveal
    sentences = re.split(r'(?<=[.;])\s+', raw)
    clues = [s.strip() for s in sentences if len(s.strip()) > 5][:4]

    if not clues:
        return _quiz_flag(year, exclude_ids + [country['MasterCountryID']], exclude_str)

    wrong = _pick_wrong_countries(year, country['MasterCountryID'])
    options = wrong + [country['CanonicalName']]
    random.shuffle(options)

    return {
        "mode": "flag",
        "answer": country['CanonicalName'],
        "iso2": country['ISOAlpha2'],
        "clues": clues,
        "options": options,
    }
