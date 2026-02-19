-- ============================================================
-- CIA World Factbook Archive - Test Queries
-- Database: CIA_WorldFactbook | 26 years (2000-2025)
-- ============================================================

-- 1. OVERVIEW: How many countries per year?
SELECT Year, COUNT(*) AS Countries, Source
FROM Countries
GROUP BY Year, Source
ORDER BY Year;

-- 2. TABLE OF CONTENTS: List all countries in 2020
SELECT Code, Name
FROM Countries
WHERE Year = 2020
ORDER BY Name;

-- 3. BROWSE: See all categories for United States in 2020
SELECT cc.CategoryTitle, COUNT(cf.FieldID) AS Fields
FROM Countries c
JOIN CountryCategories cc ON c.CountryID = cc.CountryID
JOIN CountryFields cf ON cc.CategoryID = cf.CategoryID
WHERE c.Code = 'us' AND c.Year = 2020
GROUP BY cc.CategoryTitle
ORDER BY cc.CategoryTitle;

-- 4. VIEW: All fields for a specific country and category
SELECT cf.FieldName, LEFT(cf.Content, 500) AS Content
FROM Countries c
JOIN CountryCategories cc ON c.CountryID = cc.CountryID
JOIN CountryFields cf ON cc.CategoryID = cf.CategoryID
WHERE c.Code = 'us' AND c.Year = 2025
  AND cc.CategoryTitle = 'People and Society'
ORDER BY cf.FieldID;

-- 5. SEARCH: Find all countries mentioning "nuclear" in 2020
SELECT DISTINCT c.Name, cc.CategoryTitle, cf.FieldName
FROM CountryFields cf
JOIN Countries c ON cf.CountryID = c.CountryID
JOIN CountryCategories cc ON cf.CategoryID = cc.CategoryID
WHERE c.Year = 2020
  AND cf.Content LIKE '%nuclear%'
ORDER BY c.Name;

-- 6. COMPARE: Track US population across years
SELECT c.Year, cf.FieldName, LEFT(cf.Content, 200) AS Value
FROM Countries c
JOIN CountryFields cf ON c.CountryID = cf.CountryID
WHERE c.Code = 'us' AND cf.FieldName = 'Population'
ORDER BY c.Year;

-- 7. COMPARE: GDP of China across years
SELECT c.Year, cf.FieldName, LEFT(cf.Content, 300) AS Value
FROM Countries c
JOIN CountryFields cf ON c.CountryID = cf.CountryID
WHERE c.Code = 'ch'
  AND (cf.FieldName LIKE '%GDP%' OR cf.FieldName LIKE '%Gdp%')
  AND cf.FieldName NOT LIKE '%composition%'
  AND cf.FieldName NOT LIKE '%sector%'
ORDER BY c.Year, cf.FieldName;

-- 8. SEARCH across ALL years: Which countries mention "oil reserves"
SELECT c.Year, c.Name, cf.FieldName, LEFT(cf.Content, 200) AS Preview
FROM CountryFields cf
JOIN Countries c ON cf.CountryID = c.CountryID
WHERE cf.Content LIKE '%oil reserves%'
ORDER BY c.Year DESC, c.Name;

-- 9. HOW MANY countries existed each year?
SELECT Year, COUNT(*) AS CountryCount
FROM Countries
GROUP BY Year
ORDER BY Year;

-- 10. FIND a specific country by name
SELECT c.Year, c.Code, c.Name, c.Source
FROM Countries c
WHERE c.Name LIKE '%Korea%'
ORDER BY c.Year, c.Name;

-- 11. DATABASE STATS
SELECT 'Countries' AS TableName, COUNT(*) AS Rows FROM Countries
UNION ALL
SELECT 'Categories', COUNT(*) FROM CountryCategories
UNION ALL
SELECT 'Fields', COUNT(*) FROM CountryFields;

-- 12. WILDCARD SEARCH: Find any field mentioning a keyword
-- Change 'climate change' to whatever you want to search for
SELECT TOP 20
    c.Year, c.Name, cc.CategoryTitle, cf.FieldName,
    LEFT(cf.Content, 300) AS Preview
FROM CountryFields cf
JOIN Countries c ON cf.CountryID = c.CountryID
JOIN CountryCategories cc ON cf.CategoryID = cc.CategoryID
WHERE cf.Content LIKE '%climate change%'
ORDER BY c.Year DESC, c.Name;
