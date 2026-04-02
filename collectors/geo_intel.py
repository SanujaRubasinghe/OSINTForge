from __future__ import annotations
import asyncio
import os
import httpx
from geopy.geocoders import Nominatim

_geolocator = Nominatim(user_agent="osintforge_geo_standalone")
OVERPASS    = "https://overpass-api.de/api/interpreter"


async def geocode(address: str) -> dict:
    try:
        loc = await asyncio.to_thread(_geolocator.geocode, address, timeout=10)
        if not loc:
            return {}
        return {
            "address":   loc.address,
            "latitude":  loc.latitude,
            "longitude": loc.longitude,
            "raw":       loc.raw,
        }
    except Exception:
        return {}


async def reverse_geocode(lat: float, lon: float) -> str:
    try:
        loc = await asyncio.to_thread(
            _geolocator.reverse, f"{lat}, {lon}", timeout=10
        )
        return loc.address if loc else f"{lat},{lon}"
    except Exception:
        return f"{lat},{lon}"


async def overpass_nearby(lat: float, lon: float, radius_m: int = 500) -> list[dict]:
    """Return named POIs within radius_m metres of coordinates."""
    query = f"""
    [out:json];
    (
      node(around:{radius_m},{lat},{lon})["name"]["amenity"];
      node(around:{radius_m},{lat},{lon})["name"]["shop"];
      node(around:{radius_m},{lat},{lon})["name"]["office"];
    );
    out body 20;
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(OVERPASS, data={"data": query})
        elements = resp.json().get("elements", [])
        return [
            {"name": el["tags"].get("name", ""),
             "type": (el["tags"].get("amenity")
                      or el["tags"].get("shop")
                      or el["tags"].get("office", "")),
             "lat":  el.get("lat"), "lon": el.get("lon")}
            for el in elements[:20] if el.get("tags", {}).get("name")
        ]
    except Exception:
        return []


async def streetview_metadata(lat: float, lon: float) -> dict:
    """
    Fetches Street View METADATA only (no image — avoids copyright issues).
    Returns capture date, pano_id, and whether imagery exists at this point.
    """
    key = os.getenv("GOOGLE_MAPS_KEY", "")
    if not key:
        return {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://maps.googleapis.com/maps/api/streetview/metadata",
                params={"location": f"{lat},{lon}", "key": key},
            )
        return resp.json()
    except Exception:
        return {}
