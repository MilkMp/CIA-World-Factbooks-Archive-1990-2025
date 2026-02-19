-- ============================================================================
-- CIA World Factbook Archive — Sample Power BI / Analysis Queries
-- ============================================================================
-- Created: 2026-02-15
-- Database: CIA_WorldFactbook
--
-- These queries demonstrate how to use the FieldNameMappings table to pull
-- consistent time-series data across 36 years (1990-2025) despite field name
-- changes. Import these into Power BI via DirectQuery or Import mode.
--
-- Tables used:
--   MasterCountries    — Canonical country list with EntityType
--   Countries          — Year-specific country entries
--   CountryCategories  — Category groupings per country-year
--   CountryFields      — Individual data fields (the raw data)
--   FieldNameMappings  — Maps 1,090 field name variants → canonical names
-- ============================================================================


-- ============================================================================
-- 1. POPULATION TIME SERIES (single country)
-- ============================================================================
-- Pulls population estimates for a country across all available years.
-- Works despite field name changes (Population → Population, same in this case).

SELECT
    c.Year,
    mc.CanonicalName    AS Country,
    cf.FieldName        AS OriginalFieldName,
    cf.Content          AS Population
FROM CountryFields cf
JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
JOIN Countries c          ON cf.CountryID = c.CountryID
JOIN MasterCountries mc   ON c.MasterCountryID = mc.MasterCountryID
WHERE fm.CanonicalName = 'Population'
  AND mc.CanonicalName = 'United States'
  AND fm.IsNoise = 0
ORDER BY c.Year;


-- ============================================================================
-- 2. GDP (PPP) TIME SERIES — Cross-year field name normalization
-- ============================================================================
-- This is the key use case: "GDP (purchasing power parity)" was renamed to
-- "Real GDP (purchasing power parity)" around 2020. The mapping table
-- unifies them automatically.

SELECT
    c.Year,
    mc.CanonicalName    AS Country,
    cf.FieldName        AS OriginalFieldName,
    fm.CanonicalName    AS NormalizedField,
    cf.Content          AS GDP_PPP
FROM CountryFields cf
JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
JOIN Countries c          ON cf.CountryID = c.CountryID
JOIN MasterCountries mc   ON c.MasterCountryID = mc.MasterCountryID
WHERE fm.CanonicalName = 'Real GDP (purchasing power parity)'
  AND mc.CanonicalName = 'China'
  AND fm.IsNoise = 0
ORDER BY c.Year;


-- ============================================================================
-- 3. MULTI-COUNTRY COMPARISON — GDP per capita across G7
-- ============================================================================

SELECT
    c.Year,
    mc.CanonicalName    AS Country,
    cf.Content          AS GDP_PerCapita
FROM CountryFields cf
JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
JOIN Countries c          ON cf.CountryID = c.CountryID
JOIN MasterCountries mc   ON c.MasterCountryID = mc.MasterCountryID
WHERE fm.CanonicalName = 'Real GDP per capita'
  AND mc.CanonicalName IN (
      'United States', 'United Kingdom', 'France',
      'Germany', 'Italy', 'Japan', 'Canada'
  )
  AND fm.IsNoise = 0
ORDER BY c.Year, mc.CanonicalName;


-- ============================================================================
-- 4. SOVEREIGN NATIONS — Full list with entity type breakdown
-- ============================================================================
-- Uses EntityType from MasterCountries (populated by classify_entities.py)

SELECT
    mc.CanonicalCode    AS FIPS,
    mc.CanonicalName    AS Country,
    mc.EntityType,
    mc.ISOAlpha2        AS ISO2,
    MIN(c.Year)         AS FirstYear,
    MAX(c.Year)         AS LastYear,
    COUNT(DISTINCT c.Year) AS YearsPresent
FROM MasterCountries mc
LEFT JOIN Countries c ON c.MasterCountryID = mc.MasterCountryID
GROUP BY mc.CanonicalCode, mc.CanonicalName, mc.EntityType, mc.ISOAlpha2
ORDER BY mc.EntityType, mc.CanonicalName;


-- ============================================================================
-- 5. ENTITY TYPE SUMMARY — Count by classification
-- ============================================================================

SELECT
    mc.EntityType,
    COUNT(*)            AS CountryCount,
    STRING_AGG(mc.CanonicalName, ', ')
        WITHIN GROUP (ORDER BY mc.CanonicalName) AS Countries
FROM MasterCountries mc
GROUP BY mc.EntityType
ORDER BY COUNT(*) DESC;


-- ============================================================================
-- 6. TERRITORY → ADMINISTERING COUNTRY LOOKUP
-- ============================================================================
-- Shows which sovereign nation administers each territory

SELECT
    t.CanonicalName     AS Territory,
    t.EntityType,
    a.CanonicalName     AS AdministeredBy,
    a.EntityType        AS AdminEntityType
FROM MasterCountries t
LEFT JOIN MasterCountries a ON t.AdministeringMasterCountryID = a.MasterCountryID
WHERE t.EntityType IN ('territory', 'crown_dependency', 'special_admin', 'freely_associated')
ORDER BY a.CanonicalName, t.CanonicalName;


-- ============================================================================
-- 7. FIELD NAME TABLE OF CONTENTS — All canonical fields with year ranges
-- ============================================================================
-- This is the "real table of contents" — shows every meaningful field,
-- how many variants it had, and what years it spans.

SELECT
    fm.CanonicalName,
    COUNT(DISTINCT fm.OriginalName)  AS VariantCount,
    fm.MappingType,
    MIN(fm.FirstYear)                AS FirstYear,
    MAX(fm.LastYear)                 AS LastYear,
    SUM(fm.UseCount)                 AS TotalUses,
    fm.ConsolidatedTo
FROM FieldNameMappings fm
WHERE fm.IsNoise = 0
GROUP BY fm.CanonicalName, fm.MappingType, fm.ConsolidatedTo
ORDER BY fm.CanonicalName;


-- ============================================================================
-- 8. YEAR-BY-YEAR DATA COVERAGE — Countries and fields per year
-- ============================================================================
-- Power BI line chart: data volume over time

SELECT
    c.Year,
    COUNT(DISTINCT c.CountryID)          AS CountriesThisYear,
    COUNT(DISTINCT cf.FieldID)           AS TotalFields,
    COUNT(DISTINCT cf.FieldName)         AS DistinctFieldNames,
    COUNT(DISTINCT fm.CanonicalName)     AS DistinctCanonicalFields
FROM Countries c
JOIN CountryFields cf         ON cf.CountryID = c.CountryID
JOIN FieldNameMappings fm     ON cf.FieldName = fm.OriginalName
WHERE fm.IsNoise = 0
GROUP BY c.Year
ORDER BY c.Year;


-- ============================================================================
-- 9. MILITARY EXPENDITURE TRENDS — Top 10 spenders (latest year available)
-- ============================================================================

SELECT
    c.Year,
    mc.CanonicalName    AS Country,
    cf.Content          AS MilitaryExpenditure
FROM CountryFields cf
JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
JOIN Countries c          ON cf.CountryID = c.CountryID
JOIN MasterCountries mc   ON c.MasterCountryID = mc.MasterCountryID
WHERE fm.CanonicalName = 'Military expenditures'
  AND mc.EntityType = 'sovereign'
  AND fm.IsNoise = 0
ORDER BY c.Year DESC, mc.CanonicalName;


-- ============================================================================
-- 10. INTERNET USERS GROWTH — Tracks a field that didn't exist in early years
-- ============================================================================

SELECT
    c.Year,
    mc.CanonicalName    AS Country,
    cf.Content          AS InternetUsers
FROM CountryFields cf
JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
JOIN Countries c          ON cf.CountryID = c.CountryID
JOIN MasterCountries mc   ON c.MasterCountryID = mc.MasterCountryID
WHERE fm.CanonicalName = 'Internet users'
  AND mc.CanonicalName IN ('United States', 'China', 'India', 'Brazil', 'Nigeria')
  AND fm.IsNoise = 0
ORDER BY mc.CanonicalName, c.Year;


-- ============================================================================
-- 11. INFLATION RATE COMPARISON — BRICS nations
-- ============================================================================

SELECT
    c.Year,
    mc.CanonicalName    AS Country,
    cf.Content          AS InflationRate
FROM CountryFields cf
JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
JOIN Countries c          ON cf.CountryID = c.CountryID
JOIN MasterCountries mc   ON c.MasterCountryID = mc.MasterCountryID
WHERE fm.CanonicalName = 'Inflation rate (consumer prices)'
  AND mc.CanonicalName IN ('Brazil', 'Russia', 'India', 'China', 'South Africa')
  AND fm.IsNoise = 0
ORDER BY c.Year, mc.CanonicalName;


-- ============================================================================
-- 12. CONSOLIDATED FIELD VIEW — Petroleum sub-fields over time
-- ============================================================================
-- Shows how multiple Oil/Crude oil fields map to the Petroleum parent

SELECT
    c.Year,
    mc.CanonicalName        AS Country,
    fm.CanonicalName        AS SubField,
    fm.ConsolidatedTo       AS ParentField,
    cf.Content              AS Value
FROM CountryFields cf
JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
JOIN Countries c          ON cf.CountryID = c.CountryID
JOIN MasterCountries mc   ON c.MasterCountryID = mc.MasterCountryID
WHERE fm.ConsolidatedTo = 'Petroleum'
  AND mc.CanonicalName = 'Saudi Arabia'
  AND fm.IsNoise = 0
ORDER BY c.Year, fm.CanonicalName;


-- ============================================================================
-- 13. GEOPOLITICAL EVENTS — Countries that appear/disappear
-- ============================================================================
-- Tracks entities by first/last year — useful for spotting dissolutions,
-- independences, and name changes.

SELECT
    mc.CanonicalName    AS Country,
    mc.EntityType,
    MIN(c.Year)         AS FirstAppearance,
    MAX(c.Year)         AS LastAppearance,
    COUNT(DISTINCT c.Year) AS YearsPresent,
    CASE
        WHEN MAX(c.Year) < 2025 THEN 'No longer tracked'
        WHEN MIN(c.Year) > 1990 THEN 'Added after 1990'
        ELSE 'Present throughout'
    END AS Status
FROM MasterCountries mc
JOIN Countries c ON c.MasterCountryID = mc.MasterCountryID
WHERE mc.EntityType IN ('sovereign', 'disputed', 'dissolved')
GROUP BY mc.CanonicalName, mc.EntityType
HAVING MIN(c.Year) > 1990 OR MAX(c.Year) < 2025
ORDER BY MIN(c.Year), mc.CanonicalName;


-- ============================================================================
-- 14. CATEGORY BREAKDOWN — What sections exist per country-year
-- ============================================================================
-- Useful as a Power BI slicer / filter dimension

SELECT DISTINCT
    c.Year,
    cc.CategoryTitle
FROM CountryCategories cc
JOIN Countries c ON cc.CountryID = c.CountryID
WHERE c.Name = 'United States'
ORDER BY c.Year, cc.CategoryTitle;


-- ============================================================================
-- 15. FIELD COVERAGE MATRIX — Which canonical fields exist for which years
-- ============================================================================
-- Pivot-ready query: one row per canonical field, shows min/max year and
-- total country-year combinations that have data.

SELECT
    fm.CanonicalName,
    MIN(c.Year)                          AS FirstYear,
    MAX(c.Year)                          AS LastYear,
    COUNT(DISTINCT c.Year)               AS YearsCovered,
    COUNT(DISTINCT mc.MasterCountryID)   AS CountriesWithData,
    COUNT(*)                             AS TotalRecords
FROM CountryFields cf
JOIN FieldNameMappings fm ON cf.FieldName = fm.OriginalName
JOIN Countries c          ON cf.CountryID = c.CountryID
JOIN MasterCountries mc   ON c.MasterCountryID = mc.MasterCountryID
WHERE fm.IsNoise = 0
  AND mc.EntityType = 'sovereign'
GROUP BY fm.CanonicalName
HAVING COUNT(DISTINCT c.Year) >= 10   -- fields that span at least 10 years
ORDER BY COUNT(DISTINCT c.Year) DESC, fm.CanonicalName;


-- ============================================================================
-- 16. DATA SOURCE COVERAGE — Records by source type per year
-- ============================================================================

SELECT
    c.Year,
    c.Source,
    COUNT(DISTINCT c.CountryID)  AS Countries,
    COUNT(cf.FieldID)            AS FieldRecords
FROM Countries c
JOIN CountryFields cf ON cf.CountryID = c.CountryID
GROUP BY c.Year, c.Source
ORDER BY c.Year, c.Source;


-- ============================================================================
-- 17. POWER BI FACT TABLE — Flat denormalized view for import
-- ============================================================================
-- Use this as the main Power BI data source. Import into a single table
-- for star-schema modeling with MasterCountries as a dimension.
-- NOTE: This is a large query (~1M rows). Use TOP or WHERE to filter
-- during development, then remove limits for production.

SELECT TOP 10000                       -- Remove TOP for full import
    c.Year,
    mc.MasterCountryID,
    mc.CanonicalCode                    AS FIPS,
    mc.CanonicalName                    AS Country,
    mc.EntityType,
    mc.ISOAlpha2                        AS ISO2,
    cc.CategoryTitle                    AS Category,
    fm.CanonicalName                    AS Field,
    fm.ConsolidatedTo                   AS FieldGroup,
    cf.Content                          AS Value,
    c.Source                            AS DataSource
FROM CountryFields cf
JOIN FieldNameMappings fm   ON cf.FieldName = fm.OriginalName
JOIN Countries c            ON cf.CountryID = c.CountryID
JOIN MasterCountries mc     ON c.MasterCountryID = mc.MasterCountryID
LEFT JOIN CountryCategories cc ON cf.CategoryID = cc.CategoryID
WHERE fm.IsNoise = 0
ORDER BY c.Year, mc.CanonicalName, cc.CategoryTitle, fm.CanonicalName;


-- ============================================================================
-- 18. MAPPING TYPE SUMMARY — How field names were classified
-- ============================================================================

SELECT
    MappingType,
    IsNoise,
    COUNT(*)        AS FieldCount,
    SUM(UseCount)   AS TotalUses,
    MIN(FirstYear)  AS EarliestYear,
    MAX(LastYear)   AS LatestYear
FROM FieldNameMappings
GROUP BY MappingType, IsNoise
ORDER BY COUNT(*) DESC;
