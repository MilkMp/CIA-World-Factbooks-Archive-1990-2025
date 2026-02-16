# Field Name Evolution

How CIA World Factbook field names changed over 36 years (1990-2025).

## The Problem

The CIA renamed, split, merged, and reformatted field names many times across 36 years. A simple query for "GDP" would miss years where it was called "National product", "GNP", "GDP (purchasing power parity)", or "Real GDP (purchasing power parity)".

The `FieldNameMappings` table solves this by mapping all 1,090 raw field name variants to 414 canonical names.

## Mapping Statistics

| Mapping Type | Count | Description |
|-------------|-------|-------------|
| identity | 184 | Modern field names that haven't changed |
| rename | 159 | CIA explicitly renamed the field |
| dash_format | 64 | Formatting differences (dashes, spacing) |
| consolidation | 48 | Sub-fields merged into a parent aggregate |
| country_specific | 354 | Regional entries, government body names |
| noise | 281 | Parser artifacts (flagged IsNoise=1) |
| **Total** | **1,090** | |

## Notable Renames

### Economic Fields

| Old Name(s) | Years | Canonical Name |
|------------|-------|---------------|
| National product | 1990-1995 | Real GDP (purchasing power parity) |
| GNP | 1990-1992 | GNP |
| GDP | 1993-2000 | Real GDP (purchasing power parity) |
| GDP (purchasing power parity) | 2001-2019 | Real GDP (purchasing power parity) |
| GDP - real growth rate | 2001-2019 | Real GDP growth rate |
| GDP - per capita (PPP) | 2001-2019 | Real GDP per capita |
| National product per capita | 1990-1995 | Real GDP per capita |
| Economy - overview | 2001-2019 | Economic overview |
| External debt | 1990-1999 | Debt - external |

### Military Fields

| Old Name(s) | Years | Canonical Name |
|------------|-------|---------------|
| Defense expenditures | 1990-1999 | Military expenditures |
| Military branches | 2001-2019 | Military and security forces |
| Branches | 1990-1995 | Military and security forces |
| Military manpower - availability | 1993-2008 | Military and security service personnel strengths |
| Manpower available for military service | 2009-2017 | Military and security service personnel strengths |

### Communications Fields

| Old Name(s) | Years | Canonical Name |
|------------|-------|---------------|
| Telecommunications | 1990-1995 | Telecommunication systems |
| Telephone system | 1996-2019 | Telecommunication systems |
| Telephones - main lines in use | 2001-2017 | Telephones - fixed lines |
| Radio broadcast stations | 2001-2017 | Broadcast media |
| Television broadcast stations | 2001-2017 | Broadcast media |

### Geography/People Fields

| Old Name(s) | Years | Canonical Name |
|------------|-------|---------------|
| Comparative area | 1990-1995 | Area - comparative |
| Ethnic divisions | 1990-1999 | Ethnic groups |
| Elevation extremes | 2001-2014 | Elevation |
| Maternal mortality rate | 2009-2019 | Maternal mortality ratio |
| Physicians density | 2009-2019 | Physician density |

## Consolidation Groups

Some sub-fields are consolidated into parent aggregates for analysis:

### Petroleum (12 sub-fields)
- Oil - production, consumption, exports, imports, proved reserves
- Crude oil - production, exports, imports, proved reserves
- Refined petroleum products - production, consumption, exports, imports

### Natural Gas (5 sub-fields)
- Natural gas - production, consumption, exports, imports, proved reserves

### Electricity (5 sub-fields)
- Electricity - production, consumption, exports, imports, installed generating capacity

### Electricity Generation Sources (5 sub-fields)
- Electricity - from fossil fuels, hydroelectric plants, nuclear fuels, other renewable sources, production by source

### Military Personnel (7 sub-fields)
- Military manpower - availability, fit for military service, reaching military age annually
- Manpower available/fit for military service, reaching military service age annually

### Maritime Claims (6 sub-fields)
- Contiguous zone, Continental shelf, Exclusive economic zone, Exclusive fishing zone, Territorial sea

## Dash Formatting

The 1998-1999 editions used inconsistent dash formatting:

- `Economy-overview` instead of `Economy - overview`
- `GDP--real growth rate` instead of `GDP - real growth rate`

The `dash_format` mapping type normalizes these to the standard `Field - qualifier` pattern.

## Noise Fields

281 entries are flagged as `IsNoise=1`. These include:

- **Parser artifacts**: Single/two-letter fragments, lowercase entries
- **Sub-field labels from 1994**: "adjective", "cabinet", "chancery", etc. (parsed as standalone fields due to HTML structure)
- **Abbreviation entries**: Short entries ending in periods
- **Long descriptive fragments**: 80+ character text that isn't a real field name
- **Political party names**: Country-specific party names that appeared as field names in 1990s data

Always filter with `WHERE fm.IsNoise = 0` in analytical queries.

## How to Use

```sql
-- Query with canonical field names (works across all 36 years)
SELECT c.Year, mc.CanonicalName, cf.Content
FROM CountryFields cf
JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
JOIN Countries c ON cf.CountryID = c.CountryID
JOIN MasterCountries mc ON c.MasterCountryID = mc.MasterCountryID
WHERE fm.CanonicalName = 'Population'
  AND fm.IsNoise = 0
ORDER BY mc.CanonicalName, c.Year;
```
