from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from webapp.database import sql, sql_one
from webapp.cocom import iso2_to_iso3

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("/countries")
async def countries_page(request: Request, q: str = ""):
    query = """
        SELECT mc.MasterCountryID, mc.CanonicalName, mc.CanonicalCode,
               mc.ISOAlpha2, mc.EntityType,
               MIN(c.Year) AS FirstYear, MAX(c.Year) AS LastYear,
               COUNT(c.CountryID) AS YearCount
        FROM MasterCountries mc
        LEFT JOIN Countries c ON mc.MasterCountryID = c.MasterCountryID
        GROUP BY mc.MasterCountryID, mc.CanonicalName, mc.CanonicalCode,
                 mc.ISOAlpha2, mc.EntityType
        ORDER BY mc.CanonicalName
    """
    rows = sql(query)

    # Add ISO-3 and group by entity type
    groups = {}
    for r in rows:
        if q and q.lower() not in r['CanonicalName'].lower():
            continue
        r['ISOAlpha3'] = iso2_to_iso3(r.get('ISOAlpha2', ''))
        et = r['EntityType'] or 'Other'
        groups.setdefault(et, []).append(r)

    # Sort groups: sovereign first, then alphabetical
    order = ['sovereign', 'territory', 'dependency', 'disputed', 'dissolved', 'other']
    sorted_groups = {}
    for key in order:
        for et in list(groups.keys()):
            if et.lower().startswith(key):
                sorted_groups[et] = groups.pop(et)
    for et in sorted(groups.keys()):
        sorted_groups[et] = groups[et]

    return templates.TemplateResponse("countries.html", {
        "request": request,
        "groups": sorted_groups,
        "total": sum(len(v) for v in sorted_groups.values()),
        "q": q,
    })


@router.get("/api/countries")
async def api_countries():
    rows = sql("""
        SELECT mc.MasterCountryID, mc.CanonicalName, mc.CanonicalCode,
               mc.ISOAlpha2, mc.EntityType,
               MIN(c.Year) AS FirstYear, MAX(c.Year) AS LastYear,
               COUNT(c.CountryID) AS YearCount
        FROM MasterCountries mc
        LEFT JOIN Countries c ON mc.MasterCountryID = c.MasterCountryID
        GROUP BY mc.MasterCountryID, mc.CanonicalName, mc.CanonicalCode,
                 mc.ISOAlpha2, mc.EntityType
        ORDER BY mc.CanonicalName
    """)
    for r in rows:
        r['ISOAlpha3'] = iso2_to_iso3(r.get('ISOAlpha2', ''))
    return rows


@router.get("/api/countries/{code}")
async def api_country_detail(code: str):
    master = sql_one("""
        SELECT * FROM MasterCountries
        WHERE CanonicalCode = ? OR ISOAlpha2 = ?
    """, [code.upper(), code.upper()])
    if not master:
        return {"error": "Country not found"}

    years = sql("""
        SELECT c.Year, c.Code, c.Name, c.Source,
               COUNT(cf.FieldID) AS FieldCount
        FROM Countries c
        LEFT JOIN CountryFields cf ON c.CountryID = cf.CountryID
        WHERE c.MasterCountryID = ?
        GROUP BY c.Year, c.Code, c.Name, c.Source
        ORDER BY c.Year
    """, [master['MasterCountryID']])

    return {"master": master, "years": years}
