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
