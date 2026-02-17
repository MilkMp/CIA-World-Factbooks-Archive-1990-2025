"""Additional analysis routes: rankings, change detection, dissolved states."""
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from webapp.database import sql, sql_one
from webapp.cocom import COCOM, COCOM_NAMES, get_cocom, iso2_to_iso3
from webapp.parsers import (
    extract_number, extract_pct_gdp, extract_pct,
    extract_gdp_percap, extract_dollar_billions,
    parse_life_exp, extract_rate, extract_growth_rate,
    extract_per_100,
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


def _latest_year():
    row = sql_one("SELECT MAX(Year) AS yr FROM Countries")
    return row['yr'] if row and row['yr'] else 2025

ANALYSIS_YEAR = _latest_year()

# ── Indicator definitions ──────────────────────────────────────────
# (field_name, parser, format_string, sort_descending)
RANKINGS_INDICATORS = {
    'population':     ('Population', extract_number, '{:,.0f}', True),
    'gdp_billions':   ('Real GDP (purchasing power parity)', extract_dollar_billions, '${:,.1f}B', True),
    'gdp_percap':     ('Real GDP per capita', extract_gdp_percap, '${:,}', True),
    'life_exp':       ('Life expectancy at birth', parse_life_exp, '{:.1f} yrs', True),
    'mil_pct_gdp':    ('Military expenditures', extract_pct_gdp, '{:.1f}% GDP', True),
    'pop_growth':     ('Population growth rate', extract_growth_rate, '{:.2f}%', True),
    'birth_rate':     ('Birth rate', extract_rate, '{:.1f}/1k', True),
    'death_rate':     ('Death rate', extract_rate, '{:.1f}/1k', False),
    'internet_pct':   ('Internet users', extract_pct, '{:.1f}%', True),
    'mobile_per100':  ('Telephones - mobile cellular', extract_per_100, '{:.1f}/100', True),
    'unemployment':   ('Unemployment rate', extract_pct, '{:.1f}%', False),
    'inflation':      ('Inflation rate (consumer prices)', extract_pct, '{:.1f}%', False),
}

RANKINGS_LABELS = {
    'population': 'Population',
    'gdp_billions': 'GDP (PPP, $B)',
    'gdp_percap': 'GDP per Capita',
    'life_exp': 'Life Expectancy',
    'mil_pct_gdp': 'Military % GDP',
    'pop_growth': 'Pop. Growth Rate',
    'birth_rate': 'Birth Rate',
    'death_rate': 'Death Rate',
    'internet_pct': 'Internet Users %',
    'mobile_per100': 'Mobile /100',
    'unemployment': 'Unemployment',
    'inflation': 'Inflation',
}

CHANGE_INDICATORS = {
    'population':   ('Population', extract_number),
    'gdp_billions': ('Real GDP (purchasing power parity)', extract_dollar_billions),
    'gdp_percap':   ('Real GDP per capita', extract_gdp_percap),
    'life_exp':     ('Life expectancy at birth', parse_life_exp),
    'mil_pct_gdp':  ('Military expenditures', extract_pct_gdp),
    'pop_growth':   ('Population growth rate', extract_growth_rate),
}

CHANGE_LABELS = {
    'population': 'Population',
    'gdp_billions': 'GDP ($B)',
    'gdp_percap': 'GDP per Capita',
    'life_exp': 'Life Expectancy',
    'mil_pct_gdp': 'Military % GDP',
    'pop_growth': 'Pop. Growth',
}

DISSOLVED_STATES = {
    'soviet_union': {
        'label': 'Soviet Union',
        'parent_iso2': 'RU',
        'dissolution_year': 1991,
        'successors': ['RU', 'UA', 'BY', 'KZ', 'UZ', 'TM', 'TJ', 'KG', 'GE', 'AM', 'AZ', 'MD', 'EE', 'LV', 'LT'],
    },
    'yugoslavia': {
        'label': 'Yugoslavia',
        'parent_iso2': 'CS',
        'dissolution_year': 1991,
        'successors': ['RS', 'HR', 'SI', 'BA', 'MK', 'ME'],
    },
    'czechoslovakia': {
        'label': 'Czechoslovakia',
        'parent_iso2': 'SK',
        'dissolution_year': 1992,
        'successors': ['CZ', 'SK'],
    },
}

# Dissolved state indicator options (subset that has good historical coverage)
DISSOLVED_INDICATORS = {
    'population': 'Population',
    'gdp_billions': 'GDP (PPP, $B)',
    'life_exp': 'Life Expectancy',
    'gdp_percap': 'GDP per Capita',
    'mil_pct_gdp': 'Military % GDP',
    'internet_pct': 'Internet Users %',
}


# ══════════════════════════════════════════════════════════════════════
#  FEATURE: GLOBAL RANKINGS
# ══════════════════════════════════════════════════════════════════════

def _build_rankings(indicator, year):
    """Query all sovereign countries for an indicator, parse, rank."""
    field_name, parser, fmt, desc = RANKINGS_INDICATORS[indicator]
    rows = sql("""
        SELECT mc.CanonicalName, mc.ISOAlpha2, cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE c.Year = ? AND fm.CanonicalName = ? AND fm.IsNoise = 0
          AND mc.EntityType = 'sovereign'
    """, [year, field_name])

    results = []
    for r in rows:
        val = parser(r['Content'])
        if val is not None:
            results.append({
                'name': r['CanonicalName'],
                'iso2': r['ISOAlpha2'],
                'iso3': iso2_to_iso3(r['ISOAlpha2']),
                'value': val,
                'display': fmt.format(val),
                'cocom': get_cocom(r['ISOAlpha2']) or '',
            })

    results.sort(key=lambda x: x['value'], reverse=desc)
    for i, r in enumerate(results):
        r['rank'] = i + 1
    return results


def _build_sparklines(indicator, iso_codes, end_year):
    """Fetch last 10 years of data for sparkline rendering."""
    field_name, parser, _, _ = RANKINGS_INDICATORS[indicator]
    start_year = end_year - 9
    ph = ','.join(['?'] * len(iso_codes))
    rows = sql(f"""
        SELECT mc.ISOAlpha2, c.Year, cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE mc.ISOAlpha2 IN ({ph})
          AND c.Year BETWEEN ? AND ?
          AND fm.CanonicalName = ? AND fm.IsNoise = 0
        ORDER BY mc.ISOAlpha2, c.Year
    """, iso_codes + [start_year, end_year, field_name])

    by_country = {}
    for r in rows:
        val = parser(r['Content'])
        if val is not None:
            by_country.setdefault(r['ISOAlpha2'], []).append(val)
    return by_country


@router.get("/analysis/rankings")
async def rankings_page(request: Request, indicator: str = "gdp_percap",
                        year: int = 0):
    if year <= 0:
        year = ANALYSIS_YEAR
    if indicator not in RANKINGS_INDICATORS:
        indicator = 'gdp_percap'

    rankings = _build_rankings(indicator, year)
    top10 = rankings[:10]
    bottom10 = rankings[-10:][::-1] if len(rankings) > 10 else []

    # Sparklines for top 50
    spark_codes = [r['iso2'] for r in rankings[:50]]
    sparklines = _build_sparklines(indicator, spark_codes, year) if spark_codes else {}

    years = [r['Year'] for r in sql("SELECT DISTINCT Year FROM Countries ORDER BY Year DESC")]

    return templates.TemplateResponse("analysis/rankings.html", {
        "request": request,
        "year": year,
        "indicator": indicator,
        "indicators": RANKINGS_LABELS,
        "rankings": rankings,
        "top10": top10,
        "bottom10": bottom10,
        "sparklines": sparklines,
        "years": years,
    })


@router.get("/api/analysis/rankings")
async def api_rankings(indicator: str = "gdp_percap", year: int = 0):
    if year <= 0:
        year = ANALYSIS_YEAR
    if indicator not in RANKINGS_INDICATORS:
        return []
    return _build_rankings(indicator, year)


# ══════════════════════════════════════════════════════════════════════
#  FEATURE: CHANGE DETECTION
# ══════════════════════════════════════════════════════════════════════

def _compute_changes(year):
    """Compute year-over-year changes for all sovereign countries."""
    prev_year = year - 1
    all_changes = []

    for ind_key, (field_name, parser) in CHANGE_INDICATORS.items():
        rows = sql("""
            SELECT mc.CanonicalName, mc.ISOAlpha2, c.Year, cf.Content
            FROM CountryFields cf
            JOIN Countries c ON cf.CountryID = c.CountryID
            JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
            JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
            WHERE c.Year IN (?, ?)
              AND fm.CanonicalName = ? AND fm.IsNoise = 0
              AND mc.EntityType = 'sovereign'
            ORDER BY mc.ISOAlpha2, c.Year
        """, [prev_year, year, field_name])

        by_country = {}
        for r in rows:
            iso2 = r['ISOAlpha2']
            val = parser(r['Content'])
            if val is not None:
                by_country.setdefault(iso2, {'name': r['CanonicalName'], 'iso2': iso2})
                by_country[iso2][r['Year']] = val

        for iso2, data in by_country.items():
            if prev_year in data and year in data:
                prev_val = data[prev_year]
                curr_val = data[year]
                abs_change = curr_val - prev_val
                pct_change = (abs_change / abs(prev_val) * 100) if prev_val != 0 else 0

                if abs(pct_change) > 20:
                    severity = 'critical'
                elif abs(pct_change) > 10:
                    severity = 'high'
                elif abs(pct_change) > 5:
                    severity = 'moderate'
                else:
                    severity = 'low'

                all_changes.append({
                    'name': data['name'],
                    'iso2': iso2,
                    'indicator': ind_key,
                    'indicator_label': CHANGE_LABELS.get(ind_key, field_name),
                    'prev_value': prev_val,
                    'curr_value': curr_val,
                    'abs_change': abs_change,
                    'pct_change': round(pct_change, 2),
                    'severity': severity,
                    'cocom': get_cocom(iso2) or '',
                })

    all_changes.sort(key=lambda x: abs(x['pct_change']), reverse=True)
    return all_changes


@router.get("/analysis/changes")
async def changes_page(request: Request, year: int = 0):
    if year <= 0:
        year = ANALYSIS_YEAR

    changes = _compute_changes(year)
    years = [r['Year'] for r in sql("SELECT DISTINCT Year FROM Countries WHERE Year > 1990 ORDER BY Year DESC")]

    # Summary stats
    critical = [c for c in changes if c['severity'] == 'critical']
    high = [c for c in changes if c['severity'] == 'high']

    # Most changed country (by count of high+ changes)
    country_counts = {}
    for c in changes:
        if c['severity'] in ('critical', 'high'):
            country_counts[c['name']] = country_counts.get(c['name'], 0) + 1
    most_changed = max(country_counts, key=country_counts.get) if country_counts else '—'

    # Top 20 movers for bar chart
    top_movers = changes[:20]

    return templates.TemplateResponse("analysis/changes.html", {
        "request": request,
        "year": year,
        "prev_year": year - 1,
        "changes": changes,
        "years": years,
        "total_changes": len(changes),
        "critical_count": len(critical),
        "high_count": len(high),
        "most_changed": most_changed,
        "top_movers": top_movers,
        "indicators": CHANGE_LABELS,
        "cocom_names": COCOM_NAMES,
    })


@router.get("/api/analysis/changes")
async def api_changes(year: int = 0, indicator: str = "", region: str = ""):
    if year <= 0:
        year = ANALYSIS_YEAR
    changes = _compute_changes(year)
    if indicator:
        changes = [c for c in changes if c['indicator'] == indicator]
    if region:
        changes = [c for c in changes if c['cocom'] == region]
    return changes


# ══════════════════════════════════════════════════════════════════════
#  FEATURE: DISSOLVED STATES TRACKER
# ══════════════════════════════════════════════════════════════════════

def _get_dissolved_timeseries(group_key, indicator):
    """Fetch timeseries for all successors in a dissolved state group."""
    group = DISSOLVED_STATES[group_key]
    field_name, parser, _, _ = RANKINGS_INDICATORS[indicator]
    successors = group['successors']
    ph = ','.join(['?'] * len(successors))

    rows = sql(f"""
        SELECT mc.CanonicalName, mc.ISOAlpha2, c.Year, c.Name AS OriginalName, cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE mc.ISOAlpha2 IN ({ph})
          AND fm.CanonicalName = ? AND fm.IsNoise = 0
        ORDER BY mc.ISOAlpha2, c.Year
    """, successors + [field_name])

    # Group by country
    series = {}
    for r in rows:
        iso2 = r['ISOAlpha2']
        val = parser(r['Content'])
        if val is not None:
            if iso2 not in series:
                series[iso2] = {'name': r['CanonicalName'], 'iso2': iso2, 'data': []}
            series[iso2]['data'].append({'year': r['Year'], 'value': val})

    return list(series.values())


@router.get("/analysis/dissolved")
async def dissolved_page(request: Request, indicator: str = "population"):
    if indicator not in RANKINGS_INDICATORS:
        indicator = 'population'

    groups = {}
    for key, group in DISSOLVED_STATES.items():
        series = _get_dissolved_timeseries(key, indicator)
        groups[key] = {
            'label': group['label'],
            'dissolution_year': group['dissolution_year'],
            'successor_count': len(group['successors']),
            'series': series,
        }

    return templates.TemplateResponse("analysis/dissolved.html", {
        "request": request,
        "indicator": indicator,
        "indicators": DISSOLVED_INDICATORS,
        "groups": groups,
        "year": ANALYSIS_YEAR,
    })


@router.get("/api/analysis/dissolved/{group}")
async def api_dissolved(group: str, indicator: str = "population"):
    if group not in DISSOLVED_STATES:
        return {"error": "Unknown group"}
    if indicator not in RANKINGS_INDICATORS:
        return {"error": "Unknown indicator"}
    return _get_dissolved_timeseries(group, indicator)
