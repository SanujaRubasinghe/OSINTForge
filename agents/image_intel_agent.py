from __future__ import annotations
import uuid
import base64
import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path

import piexif
from PIL import Image
from geopy.geocoders import Nominatim
import httpx
from anthropic import Anthropic

from orchestrator.state import OSINTState, FindingRecord
from collectors.image_search import fetch_reverse_image_search


VISION_PROMPT = """You are an OSINT visual intelligence analyst. 
Analyze this image for intelligence value. Focus on:

1. LOCATION CLUES: Signage, landmarks, architecture, vegetation, license plates, flags
2. ORGANIZATIONAL CLUES: Logos, uniforms, badges, lanyards, branded items  
3. TEMPORAL CLUES: Visible dates, seasonal indicators, technology vintage
4. TEXT IN FRAME: Any readable text — signs, documents, screens, clothing
5. BACKGROUND CONTEXT: Setting type (office, outdoor, event venue, vehicle)

IMPORTANT: Do NOT attempt to identify or name any individuals in the image.

Respond with a JSON object:
{
  "location_clues": ["..."],
  "organization_clues": ["..."],
  "temporal_clues": ["..."],
  "visible_text": ["..."],
  "background_context": "...",
  "confidence": "low|medium|high",
  "analyst_notes": "..."
}"""


class ImageIntelAgent:
    def __init__(self):
        self.anthropic  = Anthropic()
        self.geolocator = Nominatim(user_agent="osintforge")

    def run(self, state: OSINTState) -> dict:
        image_path = state.get("input_image_path")
        if not image_path or not Path(image_path).exists():
            return {"agent_trace": [{"agent": "image_intel", "action": "no_image"}]}

        exif_data       = self._extract_exif(image_path)
        visual_analysis = self._visual_analysis(image_path)
        ocr_text        = self._ocr_extract(image_path)
        reverse_urls    = asyncio.run(self._reverse_search(image_path))
        serp_results    = asyncio.run(fetch_reverse_image_search(image_path))

        # Build a finding record for the image intel
        summary_parts = []
        if exif_data:
            if exif_data.get("gps_coords"):
                summary_parts.append(f"GPS: {exif_data['gps_coords']} ({exif_data.get('location_name', 'unknown')})")
            if exif_data.get("device_make"):
                summary_parts.append(f"Device: {exif_data['device_make']} {exif_data.get('device_model', '')}")
            if exif_data.get("datetime"):
                summary_parts.append(f"Captured: {exif_data['datetime']}")

        if visual_analysis:
            for k in ["location_clues", "organization_clues", "visible_text"]:
                if visual_analysis.get(k):
                    summary_parts.append(f"{k}: {', '.join(visual_analysis[k][:3])}")

        if ocr_text:
            summary_parts.append(f"OCR text: {ocr_text[:200]}")

        finding: FindingRecord = {
            "id":          str(uuid.uuid4()),
            "source_type": "image_intel",
            "source_url":  f"file://{image_path}",
            "raw_text":    "\n".join(summary_parts),
            "title":       "Image intelligence analysis",
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "exif":            exif_data,
                "visual_analysis": visual_analysis,
                "ocr_text":        ocr_text,
                "reverse_urls":    reverse_urls,
                "serp_reverse":    serp_results,
            },
        }

        return {
            "exif_data":            exif_data,
            "visual_analysis":      visual_analysis,
            "ocr_text":             ocr_text,
            "reverse_search_urls":  reverse_urls,
            "serp_reverse_results": serp_results,
            "findings":             [finding],
            "agent_trace": [{
                "agent":        "image_intel",
                "action":       "analysed",
                "has_gps":      bool(exif_data and exif_data.get("gps_coords")),
                "org_clues":    len(visual_analysis.get("organization_clues", [])) if visual_analysis else 0,
                "reverse_urls": len(reverse_urls),
                "serp_reverse": len(serp_results),
                "ocr_chars":    len(ocr_text or ""),
                "timestamp":    datetime.now(timezone.utc).isoformat(),
            }],
        }

    def _extract_exif(self, image_path: str) -> dict:
        try:
            img = Image.open(image_path)
            raw = piexif.load(img.info.get("exif", b""))

            def get(ifd, tag):
                try:
                    val = raw.get(ifd, {}).get(tag)
                    return val.decode() if isinstance(val, bytes) else val
                except Exception:
                    return None

            gps = raw.get("GPS", {})
            coords = self._dms_to_decimal(gps) if gps else None
            location_name = None
            if coords:
                try:
                    loc = self.geolocator.reverse(f"{coords[0]}, {coords[1]}", timeout=10)
                    location_name = loc.address if loc else None
                except Exception:
                    pass

            return {
                "device_make":    get("0th", piexif.ImageIFD.Make),
                "device_model":   get("0th", piexif.ImageIFD.Model),
                "software":       get("0th", piexif.ImageIFD.Software),
                "datetime":       get("0th", piexif.ImageIFD.DateTime),
                "gps_coords":     coords,
                "location_name":  location_name,
            }
        except Exception:
            return {}

    def _dms_to_decimal(self, gps: dict) -> tuple[float, float] | None:
        try:
            def to_dec(dms, ref):
                d, m, s = [(n / d) for n, d in dms]
                dec = d + m / 60 + s / 3600
                if ref in [b'S', b'W']:
                    dec = -dec
                return dec
            lat = to_dec(gps[2], gps[1])
            lon = to_dec(gps[4], gps[3])
            return (lat, lon)
        except Exception:
            return None

    def _visual_analysis(self, image_path: str) -> dict:
        try:
            with open(image_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode()

            img = Image.open(image_path)
            fmt = img.format or "JPEG"
            mt  = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(fmt, "image/jpeg")

            response = self.anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": mt, "data": image_data}},
                        {"type": "text",  "text": VISION_PROMPT},
                    ],
                }],
            )
            raw = response.content[0].text
            if raw.strip().startswith("```"):
                raw = raw.strip().split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(raw)
        except Exception:
            return {}

    def _ocr_extract(self, image_path: str) -> str:
        try:
            import pytesseract
            import cv2
            import numpy as np
            img  = cv2.imread(image_path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            denoised = cv2.fastNlMeansDenoising(gray, h=10)
            _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return pytesseract.image_to_string(thresh).strip()
        except Exception:
            return ""

    async def _reverse_search(self, image_path: str) -> list[str]:
        urls = []
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                with open(image_path, "rb") as f:
                    resp = await client.post(
                        "https://yandex.com/images/search",
                        params={"rpt": "imageview", "format": "json"},
                        files={"upfile": ("image.jpg", f, "image/jpeg")},
                    )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("blocks", [])[:10]:
                        url = item.get("url") or item.get("link")
                        if url:
                            urls.append(url)
        except Exception:
            pass
        return urls
