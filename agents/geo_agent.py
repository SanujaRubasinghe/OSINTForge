from __future__ import annotations
import uuid
import asyncio
import os
from datetime import datetime, timezone

import httpx
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

from orchestrator.state import OSINTState, FindingRecord


class GeoAgent:
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"
    OSM_RADIUS_M = 500

    def __init__(self):
        self.geolocator = Nominatim(user_agent="osintforge_geo")

    def run(self, state: OSINTState) -> dict:
        tasks = [t for t in state["collection_tasks"]
                 if t["type"] == "geo" and t["status"] == "pending"]

        # Also check image intel GPS data
        exif = state.get("exif_data") or {}
        gps  = exif.get("gps_coords")

        findings = []

        for task in tasks:
            results = asyncio.run(self._geocode_and_enrich(task["query"]))
            findings.extend(results)

        if gps:
            results = asyncio.run(self._enrich_coords(gps[0], gps[1], "image_exif_gps"))
            findings.extend(results)

        if not tasks and not gps:
            return {"agent_trace": [{"agent": "geo_agent", "action": "no_tasks"}]}

        return {
            "findings": findings,
            "agent_trace": [{
                "agent":     "geo_agent",
                "action":    "collected",
                "count":     len(findings),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

    async def _geocode_and_enrich(self, address: str) -> list[FindingRecord]:
        try:
            location = await asyncio.to_thread(
                self.geolocator.geocode, address, timeout=10
            )
            if not location:
                return []
            return await self._enrich_coords(location.latitude, location.longitude, address)
        except GeocoderTimedOut:
            return []

    async def _enrich_coords(self, lat: float, lon: float,
                              source_label: str) -> list[FindingRecord]:
        findings = []

        # Reverse geocode for human-readable address
        try:
            loc = await asyncio.to_thread(
                self.geolocator.reverse, f"{lat}, {lon}", timeout=10
            )
            address_str = loc.address if loc else f"{lat},{lon}"
        except Exception:
            address_str = f"{lat},{lon}"

        # OSM Overpass context — nearby POIs
        nearby = await self._overpass_nearby(lat, lon)

        text = (
            f"Location: {address_str}\n"
            f"Coordinates: {lat:.6f}, {lon:.6f}\n"
            + (f"Nearby points of interest:\n{nearby}" if nearby else "")
        )

        findings.append({
            "id":          str(uuid.uuid4()),
            "source_type": "geo_intel",
            "source_url":  f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}",
            "raw_text":    text,
            "title":       f"Geolocation: {address_str[:80]}",
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "lat":         lat,
                "lon":         lon,
                "address":     address_str,
                "source":      source_label,
            },
        })
        return findings

    async def _overpass_nearby(self, lat: float, lon: float) -> str:
        query = f"""
        [out:json];
        (
          node(around:{self.OSM_RADIUS_M},{lat},{lon})["name"]["amenity"];
          node(around:{self.OSM_RADIUS_M},{lat},{lon})["name"]["shop"];
          node(around:{self.OSM_RADIUS_M},{lat},{lon})["name"]["office"];
        );
        out body 20;
        """
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(self.OVERPASS_URL, data={"data": query})
            elements = resp.json().get("elements", [])
            lines = []
            for el in elements[:15]:
                tags = el.get("tags", {})
                name = tags.get("name", "")
                kind = tags.get("amenity") or tags.get("shop") or tags.get("office", "")
                if name:
                    lines.append(f"  - {name} ({kind})")
            return "\n".join(lines)
        except Exception:
            return ""
