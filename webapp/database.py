import sqlite3
from webapp.config import settings


def get_connection():
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
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
