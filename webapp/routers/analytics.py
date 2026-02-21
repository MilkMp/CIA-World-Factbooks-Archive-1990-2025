import hashlib
import os
import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel
from webapp.database import get_analytics_connection

logger = logging.getLogger(__name__)

router = APIRouter()

# IP2Location reader (loaded once at module level)
_ip2loc = None


def _get_ip2loc():
    global _ip2loc
    if _ip2loc is None:
        try:
            import IP2Location
            bin_path = os.environ.get(
                "IP2LOC_PATH",
                os.path.join(os.path.dirname(os.environ.get("DB_PATH", "data/factbook.db")), "IP2LOCATION-LITE-DB11.BIN"),
            )
            if os.path.exists(bin_path):
                _ip2loc = IP2Location.IP2Location(bin_path)
                logger.info("IP2Location loaded from %s", bin_path)
            else:
                logger.info("IP2Location .BIN not found at %s — geolocation disabled", bin_path)
        except ImportError:
            logger.info("ip2location package not installed — geolocation disabled")
    return _ip2loc


def _hash_ip(ip: str) -> str:
    """SHA-256 hash of IP, truncated to 16 hex chars for privacy."""
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def _geolocate(ip: str) -> dict:
    """Resolve IP to country/city/lat/lon. Returns nulls if unavailable."""
    reader = _get_ip2loc()
    if not reader or ip in ("127.0.0.1", "::1", "testclient"):
        return {"country": None, "city": None, "lat": None, "lon": None}
    try:
        rec = reader.get_all(ip)
        return {
            "country": rec.country_long if rec.country_long != "-" else None,
            "city": rec.city if rec.city != "-" else None,
            "lat": rec.latitude if rec.latitude != 0 else None,
            "lon": rec.longitude if rec.longitude != 0 else None,
        }
    except Exception:
        return {"country": None, "city": None, "lat": None, "lon": None}


def record_page_view(ip, path, method, status_code, referrer, user_agent, session_id, response_ms):
    """Write a page view record to analytics.db. Called from middleware."""
    ip_hash = _hash_ip(ip)
    geo = _geolocate(ip)
    conn = get_analytics_connection()
    try:
        conn.execute(
            """INSERT INTO page_views
               (ip_hash, country, city, latitude, longitude, path, method,
                status_code, referrer, user_agent, session_id, response_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ip_hash, geo["country"], geo["city"], geo["lat"], geo["lon"],
             path, method, status_code, referrer, user_agent, session_id, response_ms),
        )
        conn.commit()
    finally:
        conn.close()


class ClickEvent(BaseModel):
    path: str
    element_id: str = ""
    element_text: str = ""
    x: float = 0
    y: float = 0


@router.post("/api/analytics/click")
async def track_click(event: ClickEvent, request: Request):
    session_id = request.cookies.get("session_id", "")
    conn = get_analytics_connection()
    try:
        conn.execute(
            "INSERT INTO click_events (session_id, path, element_id, element_text, x, y) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, event.path, event.element_id, event.element_text, event.x, event.y),
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}
