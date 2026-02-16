/*
 * CIA World Factbook Archive — Database Schema
 * ==============================================
 * SQL Server DDL for the complete 1990-2025 archive.
 *
 * Tables (creation order respects foreign keys):
 *   1. MasterCountries      — 281 canonical entities
 *   2. Countries             — Per-year country records (~9,500 rows)
 *   3. CountryCategories     — Category headings per country-year (~83,600 rows)
 *   4. CountryFields         — Individual data fields (~1,071,200 rows)
 *   5. FieldNameMappings     — Field-name standardization (~1,090 rows)
 *
 * Restore order:
 *   1. Run this script to create tables + indexes
 *   2. Import data/master_countries.sql
 *   3. Import data/countries.sql
 *   4. Import data/categories.sql
 *   5. Import data/fields/country_fields_*.sql.gz  (gunzip first)
 *   6. Import data/field_name_mappings.sql
 */

USE CIA_WorldFactbook;
GO

-- ============================================================
-- 1. MasterCountries — One row per canonical entity
-- ============================================================
CREATE TABLE MasterCountries (
    MasterCountryID             INT             IDENTITY(1,1)   NOT NULL,
    CanonicalCode               NVARCHAR(10)                    NOT NULL,
    CanonicalName               NVARCHAR(200)                   NOT NULL,
    CreatedDate                 DATETIME                        NULL    DEFAULT GETDATE(),
    ISOAlpha2                   NVARCHAR(2)                     NULL,
    EntityType                  NVARCHAR(20)                    NULL,
    AdministeringMasterCountryID INT                            NULL,

    CONSTRAINT PK_MasterCountries
        PRIMARY KEY CLUSTERED (MasterCountryID),
    CONSTRAINT UQ_MasterCountries_CanonicalCode
        UNIQUE (CanonicalCode),
    CONSTRAINT FK_MasterCountries_Administering
        FOREIGN KEY (AdministeringMasterCountryID)
        REFERENCES MasterCountries (MasterCountryID)
);
GO

-- ============================================================
-- 2. Countries — One row per entity per year
-- ============================================================
CREATE TABLE Countries (
    CountryID       INT             IDENTITY(1,1)   NOT NULL,
    Year            INT                             NOT NULL,
    Code            NVARCHAR(10)                    NOT NULL,
    Name            NVARCHAR(200)                   NOT NULL,
    Source          NVARCHAR(50)                    NULL    DEFAULT 'html',
    MasterCountryID INT                             NULL,

    CONSTRAINT PK_Countries
        PRIMARY KEY CLUSTERED (CountryID),
    CONSTRAINT FK_Countries_MasterCountries
        FOREIGN KEY (MasterCountryID)
        REFERENCES MasterCountries (MasterCountryID)
);
GO

CREATE INDEX IX_Countries_Year ON Countries (Year);
CREATE INDEX IX_Countries_Code ON Countries (Code);
GO

-- ============================================================
-- 3. CountryCategories — Section headings (e.g. "Geography")
-- ============================================================
CREATE TABLE CountryCategories (
    CategoryID      INT             IDENTITY(1,1)   NOT NULL,
    CountryID       INT                             NOT NULL,
    CategoryTitle   NVARCHAR(200)                   NULL,

    CONSTRAINT PK_CountryCategories
        PRIMARY KEY CLUSTERED (CategoryID),
    CONSTRAINT FK_CountryCategories_Countries
        FOREIGN KEY (CountryID)
        REFERENCES Countries (CountryID)
);
GO

CREATE INDEX IX_Categories_Country ON CountryCategories (CountryID);
GO

-- ============================================================
-- 4. CountryFields — Individual data fields
-- ============================================================
CREATE TABLE CountryFields (
    FieldID         INT             IDENTITY(1,1)   NOT NULL,
    CategoryID      INT                             NOT NULL,
    CountryID       INT                             NOT NULL,
    FieldName       NVARCHAR(200)                   NULL,
    Content         NVARCHAR(MAX)                   NULL,

    CONSTRAINT PK_CountryFields
        PRIMARY KEY CLUSTERED (FieldID),
    CONSTRAINT FK_CountryFields_Categories
        FOREIGN KEY (CategoryID)
        REFERENCES CountryCategories (CategoryID),
    CONSTRAINT FK_CountryFields_Countries
        FOREIGN KEY (CountryID)
        REFERENCES Countries (CountryID)
);
GO

CREATE INDEX IX_Fields_Category ON CountryFields (CategoryID);
CREATE INDEX IX_Fields_Country  ON CountryFields (CountryID);
GO

-- ============================================================
-- 5. FieldNameMappings — Maps raw field names to canonical names
-- ============================================================
CREATE TABLE FieldNameMappings (
    MappingID       INT             IDENTITY(1,1)   NOT NULL,
    OriginalName    NVARCHAR(200)                   NOT NULL,
    CanonicalName   NVARCHAR(200)                   NOT NULL,
    MappingType     NVARCHAR(30)                    NOT NULL,
    ConsolidatedTo  NVARCHAR(200)                   NULL,
    IsNoise         BIT                             NOT NULL    DEFAULT 0,
    FirstYear       INT                             NULL,
    LastYear        INT                             NULL,
    UseCount        INT                             NULL,
    Notes           NVARCHAR(500)                   NULL,

    CONSTRAINT PK_FieldNameMappings
        PRIMARY KEY CLUSTERED (MappingID),
    CONSTRAINT UQ_FieldNameMappings_OriginalName
        UNIQUE (OriginalName)
);
GO

CREATE INDEX IX_FieldNameMappings_CanonicalName ON FieldNameMappings (CanonicalName);
GO
