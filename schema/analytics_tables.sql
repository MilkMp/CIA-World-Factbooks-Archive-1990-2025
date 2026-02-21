-- Analytics tables for CIA Factbook Archive
-- Stored in data/analytics.db (separate from factbook.db)
-- Tables are created automatically on first connection by webapp/database.py
-- This file is a reference for the schema.

CREATE TABLE IF NOT EXISTS page_views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now')),
    ip_hash TEXT,
    country TEXT,
    city TEXT,
    latitude REAL,
    longitude REAL,
    path TEXT,
    method TEXT,
    status_code INTEGER,
    referrer TEXT,
    user_agent TEXT,
    session_id TEXT,
    response_ms REAL
);

CREATE TABLE IF NOT EXISTS click_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now')),
    session_id TEXT,
    path TEXT,
    element_id TEXT,
    element_text TEXT,
    x REAL,
    y REAL
);

CREATE INDEX IF NOT EXISTS idx_pv_timestamp ON page_views(timestamp);
CREATE INDEX IF NOT EXISTS idx_pv_session ON page_views(session_id);
CREATE INDEX IF NOT EXISTS idx_pv_path ON page_views(path);
CREATE INDEX IF NOT EXISTS idx_ce_session ON click_events(session_id);
CREATE INDEX IF NOT EXISTS idx_ce_timestamp ON click_events(timestamp);
