"""COCOM region mapping — DoD Unified Command Plan."""
import pycountry

COCOM = {
    'EUCOM': [
        'AL','AD','AM','AT','AZ','BY','BE','BA','BG','HR','CY','CZ','DK',
        'EE','FI','FR','GE','DE','GR','HU','IS','IE','IT','XK','LV','LI',
        'LT','LU','MC','MT','MD','ME','NL','MK','NO','PL','PT','RO','RU',
        'SM','RS','SK','SI','ES','SE','CH','TR','UA','GB','VA',
        # Territories
        'GI','FO','SJ',
    ],
    'CENTCOM': [
        'AF','BH','EG','IL','IR','IQ','JO','KW','KZ','KG','LB','OM','PK',
        'QA','SA','SY','TJ','TM','AE','UZ','YE',
    ],
    'INDOPACOM': [
        'AU','BD','BT','BN','KH','CN','FJ','IN','ID','JP','KI','KP','KR',
        'LA','MY','MV','MH','FM','MN','MM','NR','NP','NZ','PW','PG',
        'PH','WS','SG','SB','LK','TW','TH','TL','TO','TV','VU','VN',
        # Territories
        'GU','AS','MP','NC','PF','WF','CK','NU','CX','CC','NF','HK','MO',
    ],
    'AFRICOM': [
        'DZ','AO','BJ','BW','BF','BI','CV','CM','CF','TD','KM','CG',
        'CD','CI','DJ','GQ','ER','SZ','ET','GA','GM','GH','GN','GW',
        'KE','LS','LR','LY','MG','MW','ML','MR','MU','MA','MZ','NA',
        'NE','NG','RW','ST','SN','SC','SL','SO','ZA','SS','SD','TZ',
        'TG','TN','UG','ZM','ZW',
        # Territories
        'YT','TF','SH','RE',
    ],
    'SOUTHCOM': [
        'AG','AR','BB','BZ','BO','BR','CL','CO','CR','CU','DM',
        'DO','EC','SV','GD','GT','GY','HT','HN','JM','NI','PA',
        'PY','PE','KN','LC','VC','SR','TT','UY','VE',
        # Territories
        'AW','CW','SX','KY','TC','VG','AI','MS','GF','GP','MQ','FK','GS',
        'PR','VI',
    ],
    'NORTHCOM': ['US','CA','MX','BS','GL',
        # Territories
        'BM',
    ],
}

COCOM_NAMES = {
    'EUCOM': 'Europe & Eurasia',
    'CENTCOM': 'Middle East & Central Asia',
    'INDOPACOM': 'Indo-Pacific',
    'AFRICOM': 'Africa',
    'SOUTHCOM': 'Central & South America',
    'NORTHCOM': 'North America',
}

# Reverse lookup
_iso2_to_cocom = {}
for region, codes in COCOM.items():
    for code in codes:
        _iso2_to_cocom[code] = region


def get_cocom(iso2):
    return _iso2_to_cocom.get(str(iso2).strip().upper(), 'OTHER')


def iso2_to_iso3(code):
    """Convert ISO Alpha-2 to Alpha-3 code."""
    if not code:
        return ''
    try:
        return pycountry.countries.get(alpha_2=code.upper()).alpha_3
    except (AttributeError, LookupError):
        return ''
