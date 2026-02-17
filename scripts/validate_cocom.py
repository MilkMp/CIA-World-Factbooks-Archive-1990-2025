"""
COCOM AOR Validation Script
============================
Cross-references our webapp/cocom.py assignments against authoritative
DoD/OSINT sources for the Unified Command Plan.

Sources:
  - USNORTHCOM: northcom.mil AOR page; CRS IF13044 (Congress.gov)
    AOR: US, Canada, Mexico, Bahamas, plus territories (PR, USVI, BVI, Bermuda, Turks & Caicos)
    Greenland transferred from EUCOM to NORTHCOM effective June 2025

  - USCENTCOM: centcom.mil AOR page; CRS reports; Britannica
    21 nations including Israel (transferred from EUCOM Jan 2021)

  - USEUCOM: eucom.mil/about/the-region; CRS IF11130
    ~50 countries (after Israel -> CENTCOM 2021, Greenland -> NORTHCOM 2025)

  - USINDOPACOM: pacom.mil AOR; CRS IF12604
    36 nations in Asia-Pacific and Indian Ocean

  - USAFRICOM: africom.mil; CRS reports
    53 African nations (all of Africa except Egypt, which is CENTCOM)

  - USSOUTHCOM: southcom.mil; CRS IF13067
    ~31 nations in Central/South America and Caribbean
    (Bahamas is NORTHCOM, not SOUTHCOM)
"""

import pycountry

# ═══════════════════════════════════════════════════════════════
# AUTHORITATIVE COCOM ASSIGNMENTS (DoD Unified Command Plan)
# ═══════════════════════════════════════════════════════════════

OFFICIAL_COCOM = {
    # --NORTHCOM --
    # Source: northcom.mil, CRS IF13044
    # Continental US, Alaska, Canada, Mexico, Bahamas
    # Greenland (GL) transferred from EUCOM June 2025
    'NORTHCOM': ['US', 'CA', 'MX', 'BS'],

    # --CENTCOM --
    # Source: centcom.mil, Britannica, CRS reports
    # 21 nations. Israel added Jan 2021.
    'CENTCOM': [
        'AF',  # Afghanistan
        'BH',  # Bahrain
        'EG',  # Egypt
        'IR',  # Iran
        'IQ',  # Iraq
        'IL',  # Israel (transferred from EUCOM Jan 2021)
        'JO',  # Jordan
        'KW',  # Kuwait
        'KZ',  # Kazakhstan
        'KG',  # Kyrgyzstan
        'LB',  # Lebanon
        'OM',  # Oman
        'PK',  # Pakistan
        'QA',  # Qatar
        'SA',  # Saudi Arabia
        'SY',  # Syria
        'TJ',  # Tajikistan
        'TM',  # Turkmenistan
        'AE',  # UAE
        'UZ',  # Uzbekistan
        'YE',  # Yemen
    ],

    # --EUCOM --
    # Source: eucom.mil, globalsecurity.org, CRS IF11130
    # ~50 countries after Israel->CENTCOM, Greenland->NORTHCOM
    # Includes Russia, Turkey, Iceland, Caucasus states
    'EUCOM': [
        'AL',  # Albania
        'AD',  # Andorra
        'AM',  # Armenia
        'AT',  # Austria
        'AZ',  # Azerbaijan
        'BY',  # Belarus
        'BE',  # Belgium
        'BA',  # Bosnia & Herzegovina
        'BG',  # Bulgaria
        'HR',  # Croatia
        'CY',  # Cyprus
        'CZ',  # Czech Republic
        'DK',  # Denmark
        'EE',  # Estonia
        'FI',  # Finland
        'FR',  # France
        'GE',  # Georgia
        'DE',  # Germany
        'GR',  # Greece
        'HU',  # Hungary
        'IS',  # Iceland
        'IE',  # Ireland
        'IT',  # Italy
        'XK',  # Kosovo
        'LV',  # Latvia
        'LI',  # Liechtenstein
        'LT',  # Lithuania
        'LU',  # Luxembourg
        'MT',  # Malta
        'MD',  # Moldova
        'MC',  # Monaco
        'ME',  # Montenegro
        'NL',  # Netherlands
        'MK',  # North Macedonia
        'NO',  # Norway
        'PL',  # Poland
        'PT',  # Portugal
        'RO',  # Romania
        'RU',  # Russia
        'SM',  # San Marino
        'RS',  # Serbia
        'SK',  # Slovakia
        'SI',  # Slovenia
        'ES',  # Spain
        'SE',  # Sweden
        'CH',  # Switzerland
        'TR',  # Turkey
        'UA',  # Ukraine
        'GB',  # United Kingdom
        'VA',  # Vatican City / Holy See
    ],

    # --INDOPACOM --
    # Source: pacom.mil, CRS IF12604
    # 36 nations in Asia-Pacific and Indian Ocean
    'INDOPACOM': [
        'AU',  # Australia
        'BD',  # Bangladesh
        'BN',  # Brunei
        'MM',  # Burma / Myanmar
        'KH',  # Cambodia
        'CN',  # China
        'FJ',  # Fiji
        'IN',  # India
        'ID',  # Indonesia
        'JP',  # Japan
        'KI',  # Kiribati
        'KP',  # North Korea
        'KR',  # South Korea
        'LA',  # Laos
        'MY',  # Malaysia
        'MV',  # Maldives
        'MH',  # Marshall Islands
        'FM',  # Micronesia
        'MN',  # Mongolia
        'NR',  # Nauru
        'NP',  # Nepal
        'NZ',  # New Zealand
        'PW',  # Palau
        'PG',  # Papua New Guinea
        'PH',  # Philippines
        'WS',  # Samoa
        'SG',  # Singapore
        'SB',  # Solomon Islands
        'LK',  # Sri Lanka
        'TW',  # Taiwan
        'TH',  # Thailand
        'TL',  # Timor-Leste
        'TO',  # Tonga
        'TV',  # Tuvalu
        'VU',  # Vanuatu
        'VN',  # Vietnam
    ],

    # --AFRICOM --
    # Source: africom.mil, CRS reports
    # 53 African nations — all of Africa EXCEPT Egypt (which is CENTCOM)
    'AFRICOM': [
        'DZ',  # Algeria
        'AO',  # Angola
        'BJ',  # Benin
        'BW',  # Botswana
        'BF',  # Burkina Faso
        'BI',  # Burundi
        'CV',  # Cape Verde
        'CM',  # Cameroon
        'CF',  # Central African Republic
        'TD',  # Chad
        'KM',  # Comoros
        'CG',  # Congo (Republic)
        'CD',  # Congo (DR)
        'CI',  # Cote d'Ivoire
        'DJ',  # Djibouti
        'GQ',  # Equatorial Guinea
        'ER',  # Eritrea
        'SZ',  # Eswatini
        'ET',  # Ethiopia
        'GA',  # Gabon
        'GM',  # Gambia
        'GH',  # Ghana
        'GN',  # Guinea
        'GW',  # Guinea-Bissau
        'KE',  # Kenya
        'LS',  # Lesotho
        'LR',  # Liberia
        'LY',  # Libya
        'MG',  # Madagascar
        'MW',  # Malawi
        'ML',  # Mali
        'MR',  # Mauritania
        'MU',  # Mauritius
        'MA',  # Morocco
        'MZ',  # Mozambique
        'NA',  # Namibia
        'NE',  # Niger
        'NG',  # Nigeria
        'RW',  # Rwanda
        'ST',  # Sao Tome & Principe
        'SN',  # Senegal
        'SC',  # Seychelles
        'SL',  # Sierra Leone
        'SO',  # Somalia
        'ZA',  # South Africa
        'SS',  # South Sudan
        'SD',  # Sudan
        'TZ',  # Tanzania
        'TG',  # Togo
        'TN',  # Tunisia
        'UG',  # Uganda
        'ZM',  # Zambia
        'ZW',  # Zimbabwe
    ],

    # --SOUTHCOM --
    # Source: southcom.mil, CRS IF13067
    # ~31 nations in Central/South America and Caribbean
    # Bahamas is NORTHCOM, not SOUTHCOM
    'SOUTHCOM': [
        'AG',  # Antigua & Barbuda
        'AR',  # Argentina
        'BB',  # Barbados
        'BZ',  # Belize
        'BO',  # Bolivia
        'BR',  # Brazil
        'CL',  # Chile
        'CO',  # Colombia
        'CR',  # Costa Rica
        'CU',  # Cuba
        'DM',  # Dominica
        'DO',  # Dominican Republic
        'EC',  # Ecuador
        'SV',  # El Salvador
        'GD',  # Grenada
        'GT',  # Guatemala
        'GY',  # Guyana
        'HT',  # Haiti
        'HN',  # Honduras
        'JM',  # Jamaica
        'NI',  # Nicaragua
        'PA',  # Panama
        'PY',  # Paraguay
        'PE',  # Peru
        'KN',  # Saint Kitts & Nevis
        'LC',  # Saint Lucia
        'VC',  # Saint Vincent & the Grenadines
        'SR',  # Suriname
        'TT',  # Trinidad & Tobago
        'UY',  # Uruguay
        'VE',  # Venezuela
    ],
}


def iso2_name(code):
    """Get country name from ISO-2 code."""
    try:
        return pycountry.countries.get(alpha_2=code).name
    except (AttributeError, LookupError):
        special = {'XK': 'Kosovo', 'TW': 'Taiwan'}
        return special.get(code, code)


def validate():
    """Compare our cocom.py against official DoD assignments."""
    # Import our current mapping
    import sys
    sys.path.insert(0, 'c:/Users/milan/CIA_Factbook_Archive')
    from webapp.cocom import COCOM as OUR_COCOM

    print("=" * 72)
    print("  COCOM AOR VALIDATION REPORT")
    print("  Source: DoD Unified Command Plan / OSINT Military References")
    print("=" * 72)

    # Build reverse lookups
    our_map = {}
    for region, codes in OUR_COCOM.items():
        for code in codes:
            our_map[code] = region

    official_map = {}
    for region, codes in OFFICIAL_COCOM.items():
        for code in codes:
            official_map[code] = region

    errors = []
    warnings = []

    # --Check 1: Countries in our mapping but wrong COCOM --
    print("\n-- CHECK 1: Misassigned Countries --")
    for code, our_region in sorted(our_map.items()):
        if code in official_map and official_map[code] != our_region:
            name = iso2_name(code)
            errors.append({
                'code': code,
                'name': name,
                'ours': our_region,
                'official': official_map[code],
            })

    if errors:
        print(f"\n  ERRORS FOUND: {len(errors)} misassigned countries\n")
        print(f"  {'Code':<6} {'Country':<30} {'Our COCOM':<12} {'Official':<12}")
        print(f"  {'-'*6} {'-'*30} {'-'*12} {'-'*12}")
        for e in errors:
            print(f"  {e['code']:<6} {e['name']:<30} {e['ours']:<12} {e['official']:<12}")
    else:
        print("\n  PASS — No misassigned countries found")

    # --Check 2: Countries in official but missing from ours --
    print("\n-- CHECK 2: Missing Countries (in official, not in ours) --")
    missing = []
    for code, region in sorted(official_map.items()):
        if code not in our_map:
            missing.append({
                'code': code,
                'name': iso2_name(code),
                'official': region,
            })

    if missing:
        print(f"\n  WARNINGS: {len(missing)} countries not in our mapping\n")
        print(f"  {'Code':<6} {'Country':<30} {'Should Be':<12}")
        print(f"  {'-'*6} {'-'*30} {'-'*12}")
        for m in missing:
            print(f"  {m['code']:<6} {m['name']:<30} {m['official']:<12}")
    else:
        print("\n  PASS — All official countries present in our mapping")

    # --Check 3: Countries in ours but not in official --
    print("\n-- CHECK 3: Extra Countries (in ours, not in official) --")
    extra = []
    for code, region in sorted(our_map.items()):
        if code not in official_map:
            extra.append({
                'code': code,
                'name': iso2_name(code),
                'ours': region,
            })

    if extra:
        print(f"\n  INFO: {len(extra)} countries in our mapping but not in official reference\n")
        print(f"  {'Code':<6} {'Country':<30} {'Our COCOM':<12}")
        print(f"  {'-'*6} {'-'*30} {'-'*12}")
        for e in extra:
            print(f"  {e['code']:<6} {e['name']:<30} {e['ours']:<12}")
        print("\n  Note: These may be valid (territories, disputed areas, etc.)")
    else:
        print("\n  PASS — No extra countries beyond official reference")

    # --Check 4: Count comparison --
    print("\n-- CHECK 4: Region Counts --\n")
    print(f"  {'Region':<12} {'Ours':<8} {'Official':<10} {'Status'}")
    print(f"  {'-'*12} {'-'*8} {'-'*10} {'-'*20}")
    for region in ['NORTHCOM', 'CENTCOM', 'EUCOM', 'INDOPACOM', 'AFRICOM', 'SOUTHCOM']:
        ours = len(OUR_COCOM.get(region, []))
        official = len(OFFICIAL_COCOM.get(region, []))
        status = "MATCH" if ours == official else f"DIFF ({'+' if ours > official else ''}{ours - official})"
        marker = "  " if ours == official else ">>"
        print(f"  {region:<12} {ours:<8} {official:<10} {marker} {status}")

    our_total = sum(len(v) for v in OUR_COCOM.values())
    off_total = sum(len(v) for v in OFFICIAL_COCOM.values())
    print(f"\n  {'TOTAL':<12} {our_total:<8} {off_total:<10}")

    # --Check 5: Duplicate check --
    print("\n-- CHECK 5: Duplicate Assignments --")
    seen = {}
    dupes = []
    for region, codes in OUR_COCOM.items():
        for code in codes:
            if code in seen:
                dupes.append((code, iso2_name(code), seen[code], region))
            seen[code] = region

    if dupes:
        print(f"\n  ERRORS: {len(dupes)} countries assigned to multiple COCOMs\n")
        for code, name, r1, r2 in dupes:
            print(f"  {code} ({name}): {r1} AND {r2}")
    else:
        print("\n  PASS — No duplicate assignments")

    # --Summary --
    total_issues = len(errors) + len(missing)
    print("\n" + "=" * 72)
    if total_issues == 0:
        print("  VALIDATION PASSED — All assignments match official DoD sources")
    else:
        print(f"  VALIDATION FAILED — {len(errors)} errors, {len(missing)} missing")
        print("\n  Recommended fixes:")
        for e in errors:
            print(f"    Move {e['code']} ({e['name']}) from {e['ours']} -> {e['official']}")
        for m in missing:
            print(f"    Add {m['code']} ({m['name']}) to {m['official']}")
    print("=" * 72)

    return errors, missing, extra


if __name__ == '__main__':
    validate()
