import hashlib
import json
import logging
import urllib.request

from fastapi import APIRouter, Request
from pydantic import BaseModel
from webapp.database import get_analytics_connection

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory geo cache: ip -> {country, city, lat, lon}
_geo_cache: dict = {}
_NULL_GEO = {"country": None, "city": None, "lat": None, "lon": None}


def _hash_ip(ip: str) -> str:
    """SHA-256 hash of IP, truncated to 16 hex chars for privacy."""
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def _geolocate(ip: str) -> dict:
    """Resolve IP to country/city/lat/lon via ip-api.com (free, cached)."""
    if ip in ("127.0.0.1", "::1", "testclient"):
        return _NULL_GEO
    if ip in _geo_cache:
        return _geo_cache[ip]
    try:
        resp = urllib.request.urlopen(
            f"http://ip-api.com/json/{ip}?fields=country,city,lat,lon",
            timeout=2,
        )
        data = json.loads(resp.read())
        result = {
            "country": data.get("country"),
            "city": data.get("city"),
            "lat": data.get("lat"),
            "lon": data.get("lon"),
        }
    except Exception:
        result = _NULL_GEO
    _geo_cache[ip] = result
    return result


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
