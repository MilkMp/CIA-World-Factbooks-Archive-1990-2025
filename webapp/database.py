import os
import sqlite3
from webapp.config import settings


def get_connection():
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_feedback_connection():
    """Connection to the feedback database (separate from the archive)."""
    db_dir = os.path.dirname(settings.DB_PATH)
    path = os.path.join(db_dir, "feedback.db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS bug_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT DEFAULT (datetime('now')),
        page_url TEXT,
        category TEXT,
        description TEXT,
        user_agent TEXT
    )""")
    conn.commit()
    return conn


def get_analytics_connection():
    """Connection to the analytics database (separate from the archive)."""
    db_dir = os.path.dirname(settings.DB_PATH)
    path = os.path.join(db_dir, "analytics.db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS page_views (
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
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS click_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT (datetime('now')),
        session_id TEXT,
        path TEXT,
        element_id TEXT,
        element_text TEXT,
        x REAL,
        y REAL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pv_timestamp ON page_views(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pv_session ON page_views(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pv_path ON page_views(path)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ce_session ON click_events(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ce_timestamp ON click_events(timestamp)")
    conn.commit()
    return conn


def sql(query, params=None):
    """Execute a query and return list of dicts."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        if cursor.description is None:
            return []
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def sql_one(query, params=None):
    """Execute a query and return a single dict or None."""
    rows = sql(query, params)
    return rows[0] if rows else None
