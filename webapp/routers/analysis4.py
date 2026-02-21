"""Trade & Organization Network visualization routes."""
import re
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from webapp.database import sql
from webapp.cocom import COCOM, COCOM_NAMES, get_cocom, iso2_to_iso3
from webapp.parsers import parse_trade_partners, parse_org_memberships

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


def _latest_year():
    row = sql("SELECT MAX(Year) AS yr FROM Countries")
    return row[0]['yr'] if row else 2025


ANALYSIS_YEAR = _latest_year()


def _all_years():
    rows = sql("SELECT DISTINCT Year FROM Countries ORDER BY Year DESC")
    return [r['Year'] for r in rows]


# ── Country name resolution ─────────────────────────────────────

_NAME_ALIASES = {
    'us': 'US', 'usa': 'US', 'united states': 'US',
    'uk': 'GB', 'united kingdom': 'GB',
    'uae': 'AE', 'united arab emirates': 'AE',
    'south korea': 'KR', 'korea south': 'KR', "korea, south": 'KR',
    'north korea': 'KP', 'korea north': 'KP', "korea, north": 'KP',
    'china': 'CN', "china, people's republic of": 'CN',
    'russia': 'RU', 'russian federation': 'RU',
    'taiwan': 'TW',
    'hong kong': 'HK',
    'macau': 'MO', 'macao': 'MO',
    'czech republic': 'CZ', 'czechia': 'CZ',
    'cote d\'ivoire': 'CI', "cote d'ivoire": 'CI', 'ivory coast': 'CI',
    'burma': 'MM', 'myanmar': 'MM',
    'congo, democratic republic of the': 'CD', 'dr congo': 'CD', 'drc': 'CD',
    'congo, republic of the': 'CG',
    'vatican city': 'VA', 'holy see': 'VA',
    'brunei': 'BN',
    'vietnam': 'VN', 'viet nam': 'VN',
    'laos': 'LA',
    'syria': 'SY',
    'iran': 'IR',
    'turkey': 'TR', 'turkiye': 'TR',
    'bolivia': 'BO',
    'venezuela': 'VE',
    'tanzania': 'TZ',
    'the gambia': 'GM', 'gambia': 'GM',
    'eswatini': 'SZ', 'swaziland': 'SZ',
    'timor-leste': 'TL', 'east timor': 'TL',
    'cabo verde': 'CV', 'cape verde': 'CV',
    'micronesia': 'FM',
    'saint kitts and nevis': 'KN', 'st. kitts and nevis': 'KN',
    'saint lucia': 'LC', 'st. lucia': 'LC',
    'saint vincent and the grenadines': 'VC', 'st. vincent and the grenadines': 'VC',
    'trinidad and tobago': 'TT',
}


# ── Organization category classification ────────────────────────
# Categories: mil (military/security), eco (economic/trade),
#             pol (political/regional), dev (development/financial)

_ORG_CATEGORIES = {
    # Military & Security — alliances, peacekeeping, nonproliferation
    'NATO': 'mil', 'CSTO': 'mil', 'ANZUS': 'mil', 'AUKUS': 'mil',
    'EAPC': 'mil', 'PFP': 'mil', 'Quad': 'mil', 'GUAM': 'mil',
    'NSG': 'mil', 'Wassenaar Arrangement': 'mil', 'Australia Group': 'mil',
    'ZC': 'mil', 'OPANAL': 'mil', 'FATF': 'mil', 'MNJTF': 'mil',
    'OPCW': 'mil', 'CD': 'mil', 'IAEA': 'mil',
    # UN peacekeeping missions
    'UNIFIL': 'mil', 'MONUSCO': 'mil', 'UNMISS': 'mil', 'UNISFA': 'mil',
    'UNAMID': 'mil', 'UNOCI': 'mil', 'UNMIL': 'mil', 'MINURSO': 'mil',
    'MINUSCA': 'mil', 'MINUSTAH': 'mil', 'UNDOF': 'mil', 'UNTSO': 'mil',
    'UNMOGIP': 'mil', 'UNSOM': 'mil', 'ATMIS': 'mil', 'UNFICYP': 'mil',
    'UNRWA': 'mil', 'MINUSMA': 'mil', 'UN Security Council': 'mil',

    # Economic & Trade — trade blocs, economic unions, energy
    'WTO': 'eco', 'EU': 'eco', 'ASEAN': 'eco', 'OPEC': 'eco',
    'OAPEC': 'eco', 'APEC': 'eco', 'Mercosur': 'eco', 'NAFTA': 'eco',
    'USMCA': 'eco', 'EFTA': 'eco', 'CACM': 'eco', 'LAIA': 'eco',
    'ECOWAS': 'eco', 'CEMAC': 'eco', 'COMESA': 'eco', 'SADC': 'eco',
    'EAC': 'eco', 'WAEMU': 'eco', 'SACU': 'eco', 'D-8': 'eco',
    'ECO': 'eco', 'BIMSTEC': 'eco', 'GCC': 'eco', 'AMU': 'eco',
    'BRICS': 'eco', 'OECS': 'eco', 'Pacific Alliance': 'eco',
    'Caricom': 'eco', 'SICA': 'eco', 'ACS': 'eco', 'EMU': 'eco',
    'Schengen Convention': 'eco', 'Petrocaribe': 'eco', 'CAEU': 'eco',
    'CAN': 'eco', 'PROSUR': 'eco', 'UNASUR': 'eco', 'Sparteca': 'eco',
    'EAEU': 'eco', 'EAEC': 'eco', 'OECD': 'eco', 'G-7': 'eco',
    'G-8': 'eco', 'G-20': 'eco', 'G-10': 'eco', 'G-5': 'eco',
    'LAES': 'eco', 'CELAC': 'eco', 'Benelux': 'eco', 'ALBA': 'eco',
    'WCO': 'eco', 'ICC': 'eco',

    # Political & Regional — political bodies, regional councils
    'UN': 'pol', 'AU': 'pol', 'OAS': 'pol', 'OIF': 'pol', 'OIC': 'pol',
    'OSCE': 'pol', 'NAM': 'pol', 'G-77': 'pol', 'IOC': 'pol',
    'LAS': 'pol', 'BSEC': 'pol', 'SCO': 'pol', 'CIS': 'pol',
    'CE': 'pol', 'Arctic Council': 'pol', 'CBSS': 'pol', 'SELEC': 'pol',
    'SAARC': 'pol', 'PIF': 'pol', 'SPC': 'pol', 'C': 'pol',
    'CICA': 'pol', 'ARF': 'pol', 'CP': 'pol', 'EAS': 'pol',
    'CEI': 'pol', 'IGAD': 'pol', 'NC': 'pol', 'LCBC': 'pol',
    'AOSIS': 'pol', 'CPLP': 'pol', 'FZ': 'pol', 'Union Latina': 'pol',
    'Entente': 'pol', 'InOC': 'pol', 'SACEP': 'pol', 'ACP': 'pol',
    'G-15': 'pol', 'G-24': 'pol', 'G-9': 'pol', 'G-11': 'pol',
    'Interpol': 'pol', 'ICCt': 'pol', 'PCA': 'pol', 'UNHRC': 'pol',
    'IPU': 'pol', 'Commonwealth of Nations': 'pol',

    # Development & Financial — development banks, finance, UN agencies
    'IMF': 'dev', 'IBRD': 'dev', 'IDA': 'dev', 'IFC': 'dev',
    'MIGA': 'dev', 'AfDB': 'dev', 'ADB': 'dev', 'EBRD': 'dev',
    'BIS': 'dev', 'IADB': 'dev', 'IDB': 'dev', 'AIIB': 'dev',
    'NIB': 'dev', 'CABEI': 'dev', 'BCIE': 'dev', 'CDB': 'dev',
    'WADB': 'dev', 'BDEAC': 'dev', 'EADB': 'dev', 'EIB': 'dev',
    'ECB': 'dev', 'AMF': 'dev', 'AFESD': 'dev', 'ABEDA': 'dev',
    'Paris Club': 'dev', 'IEA': 'dev', 'NEA': 'dev', 'ESA': 'dev',
    'EITI': 'dev',
    # UN specialized agencies
    'FAO': 'dev', 'UNESCO': 'dev', 'WHO': 'dev', 'ILO': 'dev',
    'ICAO': 'dev', 'ITU': 'dev', 'IMO': 'dev', 'WIPO': 'dev',
    'UNIDO': 'dev', 'IFAD': 'dev', 'UPU': 'dev', 'WMO': 'dev',
    'UNWTO': 'dev', 'IOM': 'dev', 'ITUC': 'dev', 'ISO': 'dev',
    'IFRCS': 'dev', 'ICRM': 'dev', 'IMSO': 'dev', 'ITSO': 'dev',
    'UNHCR': 'dev', 'UNOOSA': 'dev', 'IHO': 'dev', 'WFTU': 'dev',
    'UNITAR': 'dev', 'UNCTAD': 'dev', 'CERN': 'dev',
}


def _org_category(name):
    """Return the category for an org, defaulting to 'pol'."""
    return _ORG_CATEGORIES.get(name, 'pol')


def _build_name_lookup():
    """Build lowercase-name -> ISO2 lookup from DB + aliases."""
    rows = sql("""
        SELECT CanonicalName, ISOAlpha2 FROM MasterCountries
        WHERE ISOAlpha2 IS NOT NULL
    """)
    lookup = {}
    for r in rows:
        lookup[r['CanonicalName'].lower()] = r['ISOAlpha2']
    for alias, iso2 in _NAME_ALIASES.items():
        lookup[alias.lower()] = iso2
    return lookup


_NAME_LOOKUP = None


def _resolve_name(name):
    """Resolve an informal trade partner name to an ISO2 code."""
    global _NAME_LOOKUP
    if _NAME_LOOKUP is None:
        _NAME_LOOKUP = _build_name_lookup()
    key = name.strip().lower()
    if key in _NAME_LOOKUP:
        return _NAME_LOOKUP[key]
    # Try partial match: "Korea, South" -> south korea
    for alias, iso2 in _NAME_LOOKUP.items():
        if key in alias or alias in key:
            return iso2
    return None


# ── Page route ───────────────────────────────────────────────────

@router.get("/analysis/networks")
async def networks_page(request: Request):
    return templates.TemplateResponse("analysis/networks.html", {
        "request": request,
        "year": ANALYSIS_YEAR,
        "years": _all_years(),
    })


# ── Trade Network API ────────────────────────────────────────────

@router.get("/api/analysis/trade-network")
async def api_trade_network(year: int = None, direction: str = "exports",
                            region: str = ""):
    yr = year if year and 1990 <= year <= ANALYSIS_YEAR else ANALYSIS_YEAR

    field_name = 'Exports' if direction == 'exports' else 'Imports'
    partner_field = f'{field_name} - partners'

    # Query trade partner text for all countries
    rows = sql("""
        SELECT mc.CanonicalName, mc.ISOAlpha2,
               fm.CanonicalName AS Field, cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE c.Year = ?
          AND fm.CanonicalName IN (?, ?)
          AND fm.IsNoise = 0
          AND mc.ISOAlpha2 IS NOT NULL
          AND (mc.EntityType = 'sovereign'
               OR NOT EXISTS (
                   SELECT 1 FROM MasterCountries mc2
                   WHERE mc2.ISOAlpha2 = mc.ISOAlpha2
                     AND mc2.EntityType = 'sovereign'
                     AND mc2.MasterCountryID != mc.MasterCountryID))
    """, [yr, partner_field, field_name])

    # Group by country
    by_country = {}
    for r in rows:
        key = r['ISOAlpha2']
        if key not in by_country:
            by_country[key] = {
                'name': r['CanonicalName'],
                'iso2': key,
            }
        by_country[key][r['Field']] = r['Content']

    # Filter by region if specified
    region_codes = set()
    if region and region.upper() in COCOM:
        region_codes = set(COCOM[region.upper()])

    # Build nodes and edges
    nodes = {}
    edges = []

    for iso2, data in by_country.items():
        if region_codes and iso2 not in region_codes:
            continue

        cocom = get_cocom(iso2)
        partner_text = data.get(partner_field, '')
        partners = parse_trade_partners(partner_text)

        if not partners:
            continue

        # Add source node
        if iso2 not in nodes:
            nodes[iso2] = {
                'id': iso2,
                'name': data['name'],
                'cocom': cocom,
                'total_pct': 0,
            }

        total = sum(p['pct'] for p in partners)
        nodes[iso2]['total_pct'] = total

        # Add edges and target nodes
        for p in partners[:8]:  # Top 8 partners max per country
            target_iso2 = _resolve_name(p['name'])
            if not target_iso2 or target_iso2 == iso2:
                continue

            if target_iso2 not in nodes:
                target_cocom = get_cocom(target_iso2)
                # Look up canonical name
                target_data = by_country.get(target_iso2)
                target_name = target_data['name'] if target_data else p['name']
                nodes[target_iso2] = {
                    'id': target_iso2,
                    'name': target_name,
                    'cocom': target_cocom,
                    'total_pct': 0,
                }

            edges.append({
                'source': iso2,
                'target': target_iso2,
                'weight': p['pct'],
            })

    return {
        'nodes': list(nodes.values()),
        'edges': edges,
        'year': yr,
        'direction': direction,
    }


# ── Organization Network API ─────────────────────────────────────

@router.get("/api/analysis/org-network")
async def api_org_network(year: int = None, min_members: int = 10):
    yr = year if year and 1990 <= year <= ANALYSIS_YEAR else ANALYSIS_YEAR

    rows = sql("""
        SELECT mc.CanonicalName, mc.ISOAlpha2, cf.Content
        FROM CountryFields cf
        JOIN Countries c ON cf.CountryID = c.CountryID
        JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
        JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
        WHERE c.Year = ?
          AND fm.CanonicalName = 'International organization participation'
          AND fm.IsNoise = 0
          AND mc.ISOAlpha2 IS NOT NULL
          AND (mc.EntityType = 'sovereign'
               OR NOT EXISTS (
                   SELECT 1 FROM MasterCountries mc2
                   WHERE mc2.ISOAlpha2 = mc.ISOAlpha2
                     AND mc2.EntityType = 'sovereign'
                     AND mc2.MasterCountryID != mc.MasterCountryID))
    """, [yr])

    # Count members per org, build country->org edges
    org_members = {}
    country_orgs = {}

    for r in rows:
        iso2 = r['ISOAlpha2']
        orgs = parse_org_memberships(r['Content'])
        country_orgs[iso2] = {
            'name': r['CanonicalName'],
            'orgs': orgs,
        }
        for org in orgs:
            if org not in org_members:
                org_members[org] = set()
            org_members[org].add(iso2)

    # Filter orgs by min_members
    filtered_orgs = {k: v for k, v in org_members.items() if len(v) >= min_members}

    # Build nodes
    nodes = []
    org_ids = {}

    # Country nodes
    seen_countries = set()
    for org_name, members in filtered_orgs.items():
        for iso2 in members:
            if iso2 not in seen_countries:
                seen_countries.add(iso2)
                cocom = get_cocom(iso2)
                cdata = country_orgs.get(iso2, {})
                nodes.append({
                    'id': iso2,
                    'name': cdata.get('name', iso2),
                    'type': 'country',
                    'cocom': cocom,
                })

    # Org nodes
    for org_name, members in filtered_orgs.items():
        org_id = f'org_{org_name}'
        org_ids[org_name] = org_id
        nodes.append({
            'id': org_id,
            'name': org_name,
            'type': 'org',
            'members': len(members),
            'category': _org_category(org_name),
        })

    # Edges
    edges = []
    for org_name, members in filtered_orgs.items():
        org_id = org_ids[org_name]
        for iso2 in members:
            if iso2 in seen_countries:
                edges.append({
                    'source': iso2,
                    'target': org_id,
                })

    return {
        'nodes': nodes,
        'edges': edges,
        'year': yr,
        'org_count': len(filtered_orgs),
        'country_count': len(seen_countries),
    }
