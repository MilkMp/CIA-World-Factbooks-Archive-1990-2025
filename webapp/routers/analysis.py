import re
from functools import lru_cache

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from webapp.database import sql, sql_one
from webapp.cocom import COCOM, COCOM_NAMES, get_cocom, iso2_to_iso3
from webapp.config import settings
import pycountry
from webapp.parsers import (
    extract_number, extract_pct_gdp, extract_pct,
    extract_gdp_percap, extract_dollar_billions,
    parse_life_exp, extract_rate, extract_growth_rate,
    extract_per_100,
)

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")

def _latest_year():
    """Return the most recent year available in the database."""
    row = sql_one("SELECT MAX(Year) AS yr FROM Countries")
    return row['yr'] if row and row['yr'] else 2025

ANALYSIS_YEAR = _latest_year()


def _all_years():
    """Return list of all available years, descending."""
    rows = sql("SELECT DISTINCT Year FROM Countries ORDER BY Year DESC")
    return [r['Year'] for r in rows]

# Fields to extract for regional overview
INDICATOR_FIELDS = [
    'Population', 'GDP (purchasing power parity)',
    'GDP - per capita (PPP)', 'Military expenditures',
    'Life expectancy at birth', 'Population growth rate',
]


def _parse_capital_info(content):
    """Extract capital name and lat/lon from CIA Factbook Capital field."""
    if not content:
        return None, None, None
    # Format: "name: Washington, D.C. geographic coordinates: ..."
    # Or just: "Washington, D.C.; ..."
    name_match = re.match(r'(?:name:\s*)?(.+?)(?:\s*geographic\s+coordinates|\s*;\s*note|\s*time\s+difference|\s*etymology|\n|$)', content, re.IGNORECASE)
    name = name_match.group(1).strip().rstrip(';') if name_match else None
    coord_match = re.search(
        r'(\d+)\s+(\d+)\s*([NS])\s*,?\s*(\d+)\s+(\d+)\s*([EW])', content)
    if not coord_match:
        return name, None, None
    lat = int(coord_match.group(1)) + int(coord_match.group(2)) / 60
    if coord_match.group(3) == 'S':
        lat = -lat
    lon = int(coord_match.group(4)) + int(coord_match.group(5)) / 60
    if coord_match.group(6) == 'W':
        lon = -lon
    return name, round(lat, 4), round(lon, 4)


def _get_country_indicators(iso_codes, year=ANALYSIS_YEAR):
    """Pull key indicators for a set of countries."""
    if not iso_codes:
        return []
    placeholders = ','.join(['?'] * len(iso_codes))
    rows = sql(f"""
        SELECT mc.CanonicalName, mc.ISOAlpha2, c.Name AS OriginalName,
               fm.CanonicalName AS Field, cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE mc.ISOAlpha2 IN ({placeholders})
          AND c.Year = ?
          AND (mc.EntityType = 'sovereign'
               OR NOT EXISTS (
                   SELECT 1 FROM MasterCountries mc2
                   WHERE mc2.ISOAlpha2 = mc.ISOAlpha2
                     AND mc2.EntityType = 'sovereign'
                     AND mc2.MasterCountryID != mc.MasterCountryID))
          AND fm.IsNoise = 0
          AND fm.CanonicalName IN ('Population',
              'Real GDP (purchasing power parity)',
              'Real GDP per capita',
              'Military expenditures',
              'Life expectancy at birth','Population growth rate',
              'Government type','Area - comparative','Terrorist group(s)',
              'Capital')
    """, list(iso_codes) + [year])

    # Pivot: group by country
    by_country = {}
    for r in rows:
        key = r['ISOAlpha2']
        if key not in by_country:
            by_country[key] = {
                'name': r['CanonicalName'],
                'original_name': r['OriginalName'],
                'iso2': r['ISOAlpha2'],
                'iso3': iso2_to_iso3(r['ISOAlpha2']),
            }
        by_country[key][r['Field']] = r['Content']

    # Parse numeric values
    result = []
    for iso, d in by_country.items():
        cap_name, cap_lat, cap_lon = _parse_capital_info(d.get('Capital', ''))
        result.append({
            'name': d['name'],
            'original_name': d.get('original_name', d['name']),
            'iso2': d['iso2'],
            'iso3': d['iso3'],
            'population': extract_number(d.get('Population', '')),
            'gdp_billions': extract_dollar_billions(d.get('Real GDP (purchasing power parity)', '')),
            'gdp_percap': extract_gdp_percap(d.get('Real GDP per capita', '')),
            'mil_pct_gdp': extract_pct_gdp(d.get('Military expenditures', '')),
            'life_exp': parse_life_exp(d.get('Life expectancy at birth', '')),
            'pop_growth': extract_growth_rate(d.get('Population growth rate', '')),
            'gov_type': d.get('Government type', ''),
            'area_comp': d.get('Area - comparative', ''),
            'terrorist_groups': d.get('Terrorist group(s)', ''),
            'capital': cap_name,
            'cap_lat': cap_lat,
            'cap_lon': cap_lon,
        })

    result.sort(key=lambda x: x['name'])
    return result


def _all_country_map_data(year=None):
    """Return map data for all countries across all COCOM regions."""
    if year is None:
        year = ANALYSIS_YEAR
    all_data = []
    for region, codes in COCOM.items():
        indicators = _get_country_indicators(codes, year=year)
        for c in indicators:
            c['cocom'] = region
            all_data.append(c)
    return all_data


def _region_summary(year=None):
    """Build summary stats for each COCOM region."""
    if year is None:
        year = ANALYSIS_YEAR
    summaries = []
    for region, codes in COCOM.items():
        indicators = _get_country_indicators(codes, year=year)
        pops = [x['population'] for x in indicators if x['population']]
        gdps = [x['gdp_billions'] for x in indicators if x['gdp_billions']]
        mils = [x['mil_pct_gdp'] for x in indicators if x['mil_pct_gdp']]
        lifes = [x['life_exp'] for x in indicators if x['life_exp']]

        summaries.append({
            'region': region,
            'region_name': COCOM_NAMES.get(region, region),
            'country_count': len(codes),
            'data_count': len(indicators),
            'total_pop': sum(pops) if pops else None,
            'total_gdp': sum(gdps) if gdps else None,
            'avg_mil_pct': round(sum(mils) / len(mils), 2) if mils else None,
            'avg_life_exp': round(sum(lifes) / len(lifes), 1) if lifes else None,
        })
    return summaries


# ── HTML Pages ──────────────────────────────────────────────

@router.get("/analysis")
async def analysis_home(request: Request):
    return templates.TemplateResponse("analysis/index.html", {
        "request": request,
        "year": ANALYSIS_YEAR,
    })


@router.get("/analysis/regional")
async def analysis_dashboard(request: Request, year: int = None):
    yr = year if year and 1990 <= year <= ANALYSIS_YEAR else ANALYSIS_YEAR
    summaries = _region_summary(year=yr)
    map_data = _all_country_map_data(year=yr)

    # Global aggregate KPIs
    total_entities = sum(s['country_count'] for s in summaries)
    total_pop = sum(s['total_pop'] for s in summaries if s['total_pop'])
    total_gdp = sum(s['total_gdp'] for s in summaries if s['total_gdp'])
    all_life = [s['avg_life_exp'] for s in summaries if s['avg_life_exp']]
    avg_life = round(sum(all_life) / len(all_life), 1) if all_life else None
    all_mil = [s['avg_mil_pct'] for s in summaries if s['avg_mil_pct']]
    avg_mil = round(sum(all_mil) / len(all_mil), 2) if all_mil else None

    return templates.TemplateResponse("analysis/dashboard.html", {
        "request": request,
        "summaries": summaries,
        "map_data": map_data,
        "year": yr,
        "years": _all_years(),
        "mapbox_token": settings.MAPBOX_TOKEN,
        "global_kpi": {
            "entities": total_entities,
            "population": total_pop,
            "gdp": total_gdp,
            "life_exp": avg_life,
            "mil_pct": avg_mil,
        },
    })


@router.get("/analysis/region/{cocom}")
async def region_detail(request: Request, cocom: str, year: int = None):
    cocom = cocom.upper()
    yr = year if year and 1990 <= year <= ANALYSIS_YEAR else ANALYSIS_YEAR
    codes = COCOM.get(cocom, [])
    if not codes:
        return templates.TemplateResponse("analysis/region.html", {
            "request": request, "region": cocom,
            "region_name": "Unknown Region", "indicators": [], "year": yr,
            "years": _all_years(),
        })

    indicators = _get_country_indicators(codes, year=yr)

    return templates.TemplateResponse("analysis/region.html", {
        "request": request,
        "region": cocom,
        "region_name": COCOM_NAMES.get(cocom, cocom),
        "indicators": indicators,
        "year": yr,
        "years": _all_years(),
        "mapbox_token": settings.MAPBOX_TOKEN,
    })


@router.get("/analysis/dossier/{code}")
async def country_dossier(request: Request, code: str, year: int = None):
    # Find country
    master = sql_one("""
        SELECT MasterCountryID, CanonicalName, ISOAlpha2, EntityType
        FROM MasterCountries
        WHERE CanonicalCode = ? OR ISOAlpha2 = ?
    """, [code.upper(), code.upper()])

    if not master:
        return templates.TemplateResponse("analysis/dossier.html", {
            "request": request, "master": None, "code": code,
            "sections": {}, "year": ANALYSIS_YEAR, "years": _all_years(),
        })

    # Get available years for this country
    country_years = sql("""
        SELECT DISTINCT c.Year FROM Countries c
        WHERE c.MasterCountryID = ?
        ORDER BY c.Year DESC
    """, [master['MasterCountryID']])
    available_years = [r['Year'] for r in country_years]

    # Use requested year if valid, otherwise latest available
    if year and year in available_years:
        data_year = year
    else:
        data_year = available_years[0] if available_years else ANALYSIS_YEAR

    # Get all fields for that year
    fields = sql("""
        SELECT fm.CanonicalName AS Field, cf.Content AS Val
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE c.MasterCountryID = ? AND c.Year = ? AND fm.IsNoise = 0
    """, [master['MasterCountryID'], data_year])

    field_map = {f['Field']: f['Val'] for f in fields}
    age = ANALYSIS_YEAR - data_year  # 0 = current, positive = older

    # Organize into dossier sections
    dossier_layout = {
        'Government & Political': [
            'Government type', 'Capital', 'Executive branch', 'Legislative branch',
            'Judicial branch', 'Political parties and leaders', 'Constitution',
            'International organization participation',
        ],
        'Military & Security': [
            'Military expenditures', 'Military and security forces',
            'Military service age and obligation', 'Military - note',
            'Military deployments',
        ],
        'Economy': [
            'Real GDP (purchasing power parity)', 'Real GDP per capita',
            'Real GDP growth rate', 'Inflation rate (consumer prices)',
            'Public debt', 'Exports', 'Imports', 'Unemployment rate',
            'Budget', 'Industries', 'Agricultural products',
        ],
        'Demographics': [
            'Population', 'Population growth rate', 'Age structure',
            'Birth rate', 'Death rate', 'Net migration rate',
            'Life expectancy at birth', 'Urbanization',
            'Ethnic groups', 'Languages', 'Religions', 'Literacy',
        ],
        'Energy & Resources': [
            'Natural resources', 'Crude oil - production',
            'Refined petroleum products - production',
            'Natural gas - production', 'Electricity - production',
            'Carbon dioxide emissions from consumption of energy',
        ],
        'Transnational Threats': [
            'Terrorist group(s)', 'Illicit drugs',
            'Trafficking in persons', 'Disputes - international',
            'Refugees and internally displaced persons',
        ],
        'Infrastructure': [
            'Airports', 'Pipelines', 'Railways', 'Roadways',
            'Merchant marine', 'Ports and terminals',
            'Telephones - mobile cellular', 'Internet users',
        ],
    }

    # Confidence based on data age: 0-1 years = HIGH, 2-3 = MODERATE, 4+ = LOW
    if age <= 1:
        conf = 'HIGH'
    elif age <= 3:
        conf = 'MODERATE'
    else:
        conf = 'LOW'

    sections = {}
    for section_name, section_fields in dossier_layout.items():
        section_data = []
        for fname in section_fields:
            val = field_map.get(fname)
            if val:
                section_data.append({
                    'field': fname,
                    'value': val,
                    'confidence': conf,
                })
        if section_data:
            sections[section_name] = section_data

    cocom_region = get_cocom(master.get('ISOAlpha2', ''))

    return templates.TemplateResponse("analysis/dossier.html", {
        "request": request,
        "master": master,
        "code": code,
        "sections": sections,
        "year": data_year,
        "years": available_years,
        "confidence": conf,
        "cocom": cocom_region,
        "cocom_name": COCOM_NAMES.get(cocom_region, ''),
    })


def _parse_compare_value(field, raw):
    """Parse raw CIA Factbook text into a clean display value for comparison."""
    if not raw:
        return None
    if field == 'Population':
        v = extract_number(raw)
        if v:
            if v >= 1e9:
                return f"{v / 1e9:,.2f} billion"
            elif v >= 1e6:
                return f"{v / 1e6:,.1f} million"
            return f"{v:,}"
    elif field == 'Real GDP (purchasing power parity)':
        v = extract_dollar_billions(raw)
        if v:
            if v >= 1000:
                return f"${v / 1000:,.2f} trillion"
            return f"${v:,.1f} billion"
    elif field == 'Real GDP per capita':
        v = extract_gdp_percap(raw)
        if v:
            return f"${v:,}"
    elif field == 'Real GDP growth rate':
        v = extract_growth_rate(raw)
        if v is not None:
            return f"{v}%"
    elif field == 'Military expenditures':
        v = extract_pct_gdp(raw)
        if v is not None:
            return f"{v}% of GDP"
    elif field == 'Life expectancy at birth':
        v = parse_life_exp(raw)
        if v:
            return f"{v} years"
    elif field == 'Population growth rate':
        v = extract_growth_rate(raw)
        if v is not None:
            return f"{v}%"
    elif field in ('Unemployment rate', 'Inflation rate (consumer prices)'):
        v = extract_pct(raw)
        if v is not None:
            return f"{v}%"
    elif field == 'Birth rate':
        v = extract_rate(raw)
        if v:
            return f"{v} births/1,000"
    elif field == 'Death rate':
        v = extract_rate(raw)
        if v:
            return f"{v} deaths/1,000"
    elif field == 'Literacy':
        v = parse_life_exp(raw)  # same "total population: X.X" pattern
        if v:
            return f"{v}%"
    elif field == 'Urbanization':
        v = extract_pct(raw)
        if v is not None:
            return f"{v}% urban"
    elif field == 'Public debt':
        v = extract_pct(raw)
        if v is not None:
            return f"{v}% of GDP"
    # Text fields or parse failure: return truncated raw text
    return raw[:200] if len(raw) > 200 else raw


@router.get("/analysis/compare")
async def compare_page(request: Request, a: str = "", b: str = "", year: int = None):
    yr = year if year and 1990 <= year <= ANALYSIS_YEAR else ANALYSIS_YEAR
    country_a = None
    country_b = None
    data_a = {}
    data_b = {}

    compare_fields = [
        'Population', 'Real GDP (purchasing power parity)', 'Real GDP per capita',
        'Real GDP growth rate', 'Military expenditures', 'Life expectancy at birth',
        'Population growth rate', 'Government type', 'Area - comparative',
        'Unemployment rate', 'Inflation rate (consumer prices)', 'Public debt',
        'Birth rate', 'Death rate', 'Urbanization', 'Literacy',
    ]

    if a:
        country_a = sql_one("""
            SELECT MasterCountryID, CanonicalName, ISOAlpha2
            FROM MasterCountries WHERE CanonicalCode = ? OR ISOAlpha2 = ?
        """, [a.upper(), a.upper()])
        if country_a:
            fields = sql("""
                SELECT fm.CanonicalName AS Field, cf.Content AS Val
                FROM CountryFields cf
                JOIN Countries c ON cf.CountryID = c.CountryID
                JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
                WHERE c.MasterCountryID = ? AND c.Year = ? AND fm.IsNoise = 0
            """, [country_a['MasterCountryID'], yr])
            data_a = {f['Field']: _parse_compare_value(f['Field'], f['Val']) for f in fields}

    if b:
        country_b = sql_one("""
            SELECT MasterCountryID, CanonicalName, ISOAlpha2
            FROM MasterCountries WHERE CanonicalCode = ? OR ISOAlpha2 = ?
        """, [b.upper(), b.upper()])
        if country_b:
            fields = sql("""
                SELECT fm.CanonicalName AS Field, cf.Content AS Val
                FROM CountryFields cf
                JOIN Countries c ON cf.CountryID = c.CountryID
                JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
                WHERE c.MasterCountryID = ? AND c.Year = ? AND fm.IsNoise = 0
            """, [country_b['MasterCountryID'], yr])
            data_b = {f['Field']: _parse_compare_value(f['Field'], f['Val']) for f in fields}

    # Get all countries for the selector dropdowns
    all_countries = sql("""
        SELECT CanonicalName, CanonicalCode, ISOAlpha2
        FROM MasterCountries mc
        WHERE ISOAlpha2 IS NOT NULL
          AND (mc.EntityType = 'sovereign'
               OR NOT EXISTS (
                   SELECT 1 FROM MasterCountries mc2
                   WHERE mc2.ISOAlpha2 = mc.ISOAlpha2
                     AND mc2.EntityType = 'sovereign'
                     AND mc2.MasterCountryID != mc.MasterCountryID))
        ORDER BY CanonicalName
    """)

    return templates.TemplateResponse("analysis/compare.html", {
        "request": request,
        "country_a": country_a,
        "country_b": country_b,
        "data_a": data_a,
        "data_b": data_b,
        "compare_fields": compare_fields,
        "all_countries": all_countries,
        "a": a,
        "b": b,
        "year": yr,
        "years": _all_years(),
    })


@router.get("/analysis/map-compare")
async def map_compare_page(request: Request):
    all_years = sql("SELECT DISTINCT Year FROM Countries ORDER BY Year")
    years = [r['Year'] for r in all_years]
    return templates.TemplateResponse("analysis/map_compare.html", {
        "request": request,
        "years": years,
        "mapbox_token": settings.MAPBOX_TOKEN,
    })


@router.get("/analysis/timeline")
async def timeline_page(request: Request):
    all_years = sql("SELECT DISTINCT Year FROM Countries ORDER BY Year")
    years = [r['Year'] for r in all_years]
    countries = sql("""
        SELECT CanonicalName, ISOAlpha2
        FROM MasterCountries mc
        WHERE ISOAlpha2 IS NOT NULL
          AND (mc.EntityType = 'sovereign'
               OR NOT EXISTS (
                   SELECT 1 FROM MasterCountries mc2
                   WHERE mc2.ISOAlpha2 = mc.ISOAlpha2
                     AND mc2.EntityType = 'sovereign'
                     AND mc2.MasterCountryID != mc.MasterCountryID))
        ORDER BY CanonicalName
    """)
    return templates.TemplateResponse("analysis/timeline.html", {
        "request": request,
        "years": years,
        "countries": countries,
        "mapbox_token": settings.MAPBOX_TOKEN,
    })


@router.get("/analysis/explorer")
async def explorer_page(request: Request):
    return templates.TemplateResponse("analysis/explorer.html", {
        "request": request,
        "year": ANALYSIS_YEAR,
    })


@router.get("/analysis/threats/{cocom}")
async def threats_page(request: Request, cocom: str, year: int = None):
    cocom = cocom.upper()
    yr = year if year and 1990 <= year <= ANALYSIS_YEAR else ANALYSIS_YEAR
    codes = COCOM.get(cocom, [])

    threat_fields = [
        'Terrorist group(s)', 'Illicit drugs', 'Trafficking in persons',
        'Disputes - international', 'Refugees and internally displaced persons',
    ]

    if not codes:
        return templates.TemplateResponse("analysis/threats.html", {
            "request": request, "region": cocom,
            "region_name": "Unknown", "threats": [], "year": yr,
            "years": _all_years(),
        })

    placeholders = ','.join(['?'] * len(codes))
    rows = sql(f"""
        SELECT mc.CanonicalName, mc.ISOAlpha2,
               fm.CanonicalName AS Field, cf.Content AS Val
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE mc.ISOAlpha2 IN ({placeholders})
          AND c.Year = ?
          AND (mc.EntityType = 'sovereign'
               OR NOT EXISTS (
                   SELECT 1 FROM MasterCountries mc2
                   WHERE mc2.ISOAlpha2 = mc.ISOAlpha2
                     AND mc2.EntityType = 'sovereign'
                     AND mc2.MasterCountryID != mc.MasterCountryID))
          AND fm.IsNoise = 0
          AND fm.CanonicalName IN ('Terrorist group(s)','Illicit drugs',
              'Trafficking in persons','Disputes - international',
              'Refugees and internally displaced persons')
    """, list(codes) + [yr])

    by_country = {}
    for r in rows:
        key = r['ISOAlpha2']
        if key not in by_country:
            by_country[key] = {
                'name': r['CanonicalName'],
                'iso2': key,
                'iso3': iso2_to_iso3(key),
            }
        by_country[key][r['Field']] = r['Val']

    threats = sorted(by_country.values(), key=lambda x: x['name'])

    return templates.TemplateResponse("analysis/threats.html", {
        "request": request,
        "region": cocom,
        "region_name": COCOM_NAMES.get(cocom, cocom),
        "threats": threats,
        "threat_fields": threat_fields,
        "year": yr,
        "years": _all_years(),
    })


# ── JSON APIs ───────────────────────────────────────────────

@router.get("/api/analysis/regions")
async def api_regions():
    return _region_summary()


@router.get("/api/analysis/region/{cocom}")
async def api_region(cocom: str):
    cocom = cocom.upper()
    codes = COCOM.get(cocom, [])
    return _get_country_indicators(codes)


@router.get("/api/analysis/map-data")
async def api_map_data():
    return _all_country_map_data()


# Dissolved state -> list of successor ISO2 codes for map expansion
_PREDECESSOR_SUCCESSORS = {
    'RU': ('Soviet Union', ['UA','BY','KZ','UZ','TM','TJ','KG','GE','AM','AZ','MD','EE','LV','LT'], 1991),
    'RS': ('Yugoslavia', ['HR','SI','BA','MK','ME','XK'], 1991),
}


def _iso2_to_name(iso2):
    """Convert ISO2 code to country name via pycountry."""
    _OVERRIDES = {'XK': 'Kosovo'}
    if iso2 in _OVERRIDES:
        return _OVERRIDES[iso2]
    try:
        c = pycountry.countries.get(alpha_2=iso2)
        return getattr(c, 'common_name', c.name)
    except (AttributeError, LookupError):
        return iso2


def _expand_predecessors(all_data):
    """For pre-dissolution years, duplicate a predecessor's map data across
    all successor territories so choropleth maps color the full extent.
    Labels show 'Soviet Union (Kazakhstan)' etc."""
    existing_iso2 = {d['iso2'] for d in all_data}
    additions = []
    for parent_iso2, (parent_label, successors, last_year) in _PREDECESSOR_SUCCESSORS.items():
        parent = next((d for d in all_data if d['iso2'] == parent_iso2), None)
        if not parent:
            continue
        # Rename the parent territory itself (e.g., Russia -> Soviet Union)
        parent['name'] = parent_label
        for succ_iso2 in successors:
            if succ_iso2 not in existing_iso2:
                entry = dict(parent)
                entry['iso2'] = succ_iso2
                entry['iso3'] = iso2_to_iso3(succ_iso2)
                succ_name = _iso2_to_name(succ_iso2)
                entry['name'] = f"{parent_label} ({succ_name})"
                additions.append(entry)
    all_data.extend(additions)


@router.get("/api/analysis/map-data/{year}")
async def api_map_data_year(year: int):
    all_data = []
    for region, codes in COCOM.items():
        indicators = _get_country_indicators(codes, year=year)
        for c in indicators:
            c['cocom'] = region
            all_data.append(c)

    # Expand dissolved states for pre-dissolution years
    if year <= 1991:
        _expand_predecessors(all_data)

    return all_data


INDICATOR_FIELD_MAP = {
    'life_exp': ('Life expectancy at birth', parse_life_exp),
    'gdp_billions': ('Real GDP (purchasing power parity)', extract_dollar_billions),
    'population': ('Population', extract_number),
    'mil_pct_gdp': ('Military expenditures', extract_pct_gdp),
    'gdp_percap': ('Real GDP per capita', extract_gdp_percap),
    'internet_pct': ('Internet users', extract_pct),
    'mobile_per100': ('Telephones - mobile cellular', extract_per_100),
    'fixed_per100': ('Telephones - fixed lines', extract_per_100),
    'broadband_per100': ('Broadband - fixed subscriptions', extract_per_100),
}


@router.get("/api/analysis/timeseries")
async def api_timeseries(indicator: str = "life_exp", countries: str = ""):
    """Return year-by-year values for selected countries and indicator."""
    codes = [c.strip().upper() for c in countries.split(",") if c.strip()]
    if not codes or indicator not in INDICATOR_FIELD_MAP:
        return []

    field_name, parser = INDICATOR_FIELD_MAP[indicator]
    placeholders = ','.join(['?'] * len(codes))

    rows = sql(f"""
        SELECT mc.CanonicalName, mc.ISOAlpha2, c.Year, cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE mc.ISOAlpha2 IN ({placeholders})
          AND fm.CanonicalName = ?
          AND fm.IsNoise = 0
          AND (mc.EntityType = 'sovereign'
               OR NOT EXISTS (
                   SELECT 1 FROM MasterCountries mc2
                   WHERE mc2.ISOAlpha2 = mc.ISOAlpha2
                     AND mc2.EntityType = 'sovereign'
                     AND mc2.MasterCountryID != mc.MasterCountryID))
        ORDER BY mc.CanonicalName, c.Year
    """, codes + [field_name])

    result = []
    for r in rows:
        val = parser(r['Content'])
        if val is not None:
            result.append({
                'name': r['CanonicalName'],
                'iso2': r['ISOAlpha2'],
                'year': r['Year'],
                'value': val,
            })
    return result


@lru_cache(maxsize=16)
def _all_years_indicator(indicator: str):
    """Return all countries' values for every year for one indicator."""
    if indicator not in INDICATOR_FIELD_MAP:
        return []
    field_name, parser = INDICATOR_FIELD_MAP[indicator]
    rows = sql("""
        SELECT mc.CanonicalName, mc.ISOAlpha2, c.Year, cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE fm.CanonicalName = ?
          AND fm.IsNoise = 0
          AND mc.ISOAlpha2 IS NOT NULL
          AND (mc.EntityType = 'sovereign'
               OR NOT EXISTS (
                   SELECT 1 FROM MasterCountries mc2
                   WHERE mc2.ISOAlpha2 = mc.ISOAlpha2
                     AND mc2.EntityType = 'sovereign'
                     AND mc2.MasterCountryID != mc.MasterCountryID))
        ORDER BY mc.CanonicalName, c.Year
    """, [field_name])
    result = []
    for r in rows:
        val = parser(r['Content'])
        if val is not None:
            result.append({
                'name': r['CanonicalName'],
                'iso2': r['ISOAlpha2'],
                'year': r['Year'],
                'value': val,
            })
    return result


@router.get("/api/analysis/all-years-data")
async def api_all_years_data(indicator: str = "life_exp"):
    return _all_years_indicator(indicator)


@router.get("/analysis/query-builder")
async def query_builder_page(request: Request):
    return templates.TemplateResponse("analysis/query_builder.html", {
        "request": request, "year": ANALYSIS_YEAR,
    })


@router.get("/api/analysis/dossier/{code}")
async def api_dossier(code: str):
    master = sql_one("""
        SELECT MasterCountryID, CanonicalName, ISOAlpha2
        FROM MasterCountries WHERE CanonicalCode = ? OR ISOAlpha2 = ?
    """, [code.upper(), code.upper()])
    if not master:
        return {"error": "Not found"}

    fields = sql("""
        SELECT fm.CanonicalName AS Field, cf.Content AS Val
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE c.MasterCountryID = ? AND c.Year = ? AND fm.IsNoise = 0
    """, [master['MasterCountryID'], ANALYSIS_YEAR])

    return {
        "country": master['CanonicalName'],
        "year": ANALYSIS_YEAR,
        "fields": {f['Field']: f['Val'] for f in fields},
    }


# ── Communications Analysis ──────────────────────────────

_COMMS_FIELDS = (
    'Internet users',
    'Telephones - mobile cellular',
    'Telephones - fixed lines',
    'Broadband - fixed subscriptions',
    'Population',
)


def _get_comms_indicators(iso_codes, year=ANALYSIS_YEAR):
    """Pull communications indicators for a set of countries."""
    if not iso_codes:
        return []
    placeholders = ','.join(['?'] * len(iso_codes))
    rows = sql(f"""
        SELECT mc.CanonicalName, mc.ISOAlpha2,
               fm.CanonicalName AS Field, cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE mc.ISOAlpha2 IN ({placeholders})
          AND c.Year = ?
          AND (mc.EntityType = 'sovereign'
               OR NOT EXISTS (
                   SELECT 1 FROM MasterCountries mc2
                   WHERE mc2.ISOAlpha2 = mc.ISOAlpha2
                     AND mc2.EntityType = 'sovereign'
                     AND mc2.MasterCountryID != mc.MasterCountryID))
          AND fm.IsNoise = 0
          AND fm.CanonicalName IN ({','.join(['?'] * len(_COMMS_FIELDS))})
    """, list(iso_codes) + [year] + list(_COMMS_FIELDS))

    by_country = {}
    for r in rows:
        key = r['ISOAlpha2']
        if key not in by_country:
            by_country[key] = {
                'name': r['CanonicalName'],
                'iso2': r['ISOAlpha2'],
                'iso3': iso2_to_iso3(r['ISOAlpha2']),
            }
        by_country[key][r['Field']] = r['Content']

    result = []
    for iso, d in by_country.items():
        inet_pct = extract_pct(d.get('Internet users', ''))
        # Pre-2015: CIA only published raw user counts, no percentage.
        # Estimate percentage from raw count / population.
        if inet_pct is None:
            inet_text = d.get('Internet users', '').lower()
            pop = extract_number(d.get('Population', ''))
            # Parse "245 million", "3.449 million", "1.2 billion", or "115,311,958"
            raw_users = None
            m = re.search(r'([\d.]+)\s*billion', inet_text)
            if m:
                raw_users = float(m.group(1)) * 1e9
            else:
                m = re.search(r'([\d.]+)\s*million', inet_text)
                if m:
                    raw_users = float(m.group(1)) * 1e6
                else:
                    raw_users = extract_number(inet_text)
            if raw_users and pop and pop > 0:
                inet_pct = round(min(raw_users / pop * 100, 100), 1)
        result.append({
            'name': d['name'],
            'iso2': d['iso2'],
            'iso3': d['iso3'],
            'internet_pct': inet_pct,
            'mobile_per100': extract_per_100(d.get('Telephones - mobile cellular', '')),
            'fixed_per100': extract_per_100(d.get('Telephones - fixed lines', '')),
            'broadband_per100': extract_per_100(d.get('Broadband - fixed subscriptions', '')),
        })
    result.sort(key=lambda x: x['name'])
    return result


@router.get("/analysis/communications")
async def communications_page(request: Request, year: int = None):
    """Communications infrastructure analysis dashboard."""
    yr = year if year and 1990 <= year <= ANALYSIS_YEAR else ANALYSIS_YEAR
    all_data = []
    region_summaries = []
    for region, codes in COCOM.items():
        indicators = _get_comms_indicators(codes, year=yr)
        for c in indicators:
            c['cocom'] = region
            all_data.append(c)

        inets = [x['internet_pct'] for x in indicators if x['internet_pct'] is not None]
        mobs = [x['mobile_per100'] for x in indicators if x['mobile_per100'] is not None]
        bbs = [x['broadband_per100'] for x in indicators if x['broadband_per100'] is not None]
        region_summaries.append({
            'region': region,
            'region_name': COCOM_NAMES.get(region, region),
            'country_count': len(codes),
            'data_count': len(indicators),
            'avg_internet': round(sum(inets) / len(inets), 1) if inets else None,
            'avg_mobile': round(sum(mobs) / len(mobs), 1) if mobs else None,
            'avg_broadband': round(sum(bbs) / len(bbs), 1) if bbs else None,
        })

    # Top 10 / Bottom 10 by internet penetration
    with_inet = [c for c in all_data if c['internet_pct'] is not None]
    top10 = sorted(with_inet, key=lambda x: x['internet_pct'], reverse=True)[:10]
    bottom10 = sorted(with_inet, key=lambda x: x['internet_pct'])[:10]

    return templates.TemplateResponse("analysis/communications.html", {
        "request": request,
        "year": yr,
        "years": _all_years(),
        "all_data": all_data,
        "region_summaries": region_summaries,
        "top10": top10,
        "bottom10": bottom10,
        "mapbox_token": settings.MAPBOX_TOKEN,
    })


@router.get("/api/analysis/comms-data/{year}")
async def api_comms_data_year(year: int):
    """Return communications indicators for all countries in a given year."""
    all_data = []
    for region, codes in COCOM.items():
        indicators = _get_comms_indicators(codes, year=year)
        for c in indicators:
            c['cocom'] = region
            all_data.append(c)
    return all_data
