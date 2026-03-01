-- ============================================================
-- CIA World Factbook — Extended Sub-Topics (Structured Parsing)
-- Creates a SEPARATE database for decomposed field values.
-- The original CIA_WorldFactbook database is NOT modified.
-- ============================================================

-- Create the extended database
IF DB_ID('CIA_WorldFactbook_Extended_Sub_Topics') IS NULL
    CREATE DATABASE CIA_WorldFactbook_Extended_Sub_Topics;
GO

USE CIA_WorldFactbook_Extended_Sub_Topics;
GO

SET QUOTED_IDENTIFIER ON;
GO

-- Drop existing table if re-running
IF OBJECT_ID('FieldValues', 'U') IS NOT NULL
    DROP TABLE FieldValues;
GO

-- ============================================================
-- FieldValues: decomposed sub-values from CountryFields.Content
--
-- Each row in CIA_WorldFactbook.dbo.CountryFields may produce
-- 1-N rows here. FieldID links back to the source record.
-- No data is invented — every value exists in the text blob.
-- ============================================================
CREATE TABLE FieldValues (
    ValueID     INT IDENTITY(1,1) PRIMARY KEY,
    FieldID     INT NOT NULL,           -- FK to CIA_WorldFactbook.dbo.CountryFields(FieldID)
    SubField    NVARCHAR(100) NOT NULL, -- 'total', 'male', 'female', 'land', 'value', etc.
    NumericVal  FLOAT NULL,             -- parsed numeric value (NULL if non-numeric)
    Units       NVARCHAR(50) NULL,      -- 'sq km', '%', 'years', 'USD', 'bbl/day', etc.
    TextVal     NVARCHAR(MAX) NULL,     -- non-numeric content (country names, descriptions)
    DateEst     NVARCHAR(50) NULL,      -- '2024 est.', 'FY93', '2019 est.'
    Rank        INT NULL,               -- global rank if present in source text
    SourceFragment NVARCHAR(500) NULL  -- exact substring of Content that produced this row
);

-- Indexes for common query patterns
CREATE INDEX IX_FV_FieldID   ON FieldValues(FieldID);
CREATE INDEX IX_FV_SubField  ON FieldValues(SubField);
CREATE INDEX IX_FV_Numeric   ON FieldValues(NumericVal) WHERE NumericVal IS NOT NULL;
GO

PRINT 'CIA_WorldFactbook_Extended_Sub_Topics created with FieldValues table.';
GO
