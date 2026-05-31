"""Geolocation proxy endpoint.

Endpoint:
    POST /api/geo/batch — resolve a list of IPs to country/city via ip-api.com
"""

import sys
from pathlib import Path

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

router_geo = APIRouter(prefix="/api/geo")

_FIELDS = "query,status,country,countryCode,city"
_GEO_URL = f"http://ip-api.com/batch?fields={_FIELDS}"


class GeoRequest(BaseModel):
    """List of IP addresses to geolocate."""
    ips: list[str]


@router_geo.post("/batch")
async def geo_batch(body: GeoRequest) -> dict:
    """Resolve up to 100 IPs to country/city using ip-api.com.

    Private, loopback, and unknown IPs are skipped and returned as None.

    Args:
        body: GeoRequest containing a list of IP strings.

    Returns:
        Dict mapping each IP to {country, countryCode, city} or None.
    """
    result: dict[str, dict | None] = {}

    queryable = [
        ip for ip in dict.fromkeys(body.ips)  # deduplicate, preserve order
        if ip and ip not in ("unknown", "0.0.0.0") and not _is_private(ip)
    ]

    for ip in body.ips:
        result[ip] = None

    if not queryable:
        return result

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                _GEO_URL,
                json=[{"query": ip} for ip in queryable[:100]],
            )
        if resp.status_code == 200:
            for row in resp.json():
                ip = row.get("query", "")
                if row.get("status") == "success":
                    result[ip] = {
                        "country": row.get("country", ""),
                        "countryCode": row.get("countryCode", ""),
                        "city": row.get("city", ""),
                    }
    except Exception:
        pass  # network error — return nulls, frontend shows fallback

    return result


def _is_private(ip: str) -> bool:
    """Return True if the IP is a private/loopback/link-local address."""
    try:
        import ipaddress
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False
