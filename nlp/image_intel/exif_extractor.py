from __future__ import annotations
import piexif
from PIL import Image
from geopy.geocoders import Nominatim
import asyncio


_geolocator = Nominatim(user_agent="osintforge_exif")


def extract_exif(image_path: str) -> dict:
    try:
        img = Image.open(image_path)
        raw = piexif.load(img.info.get("exif", b""))

        def get(ifd, tag):
            try:
                val = raw.get(ifd, {}).get(tag)
                return val.decode() if isinstance(val, bytes) else val
            except Exception:
                return None

        gps           = raw.get("GPS", {})
        coords        = _dms_to_decimal(gps) if gps else None
        location_name = None

        if coords:
            try:
                loc = _geolocator.reverse(f"{coords[0]}, {coords[1]}", timeout=10)
                location_name = loc.address if loc else None
            except Exception:
                pass

        return {
            "device_make":   get("0th", piexif.ImageIFD.Make),
            "device_model":  get("0th", piexif.ImageIFD.Model),
            "software":      get("0th", piexif.ImageIFD.Software),
            "datetime":      get("0th", piexif.ImageIFD.DateTime),
            "gps_coords":    coords,
            "location_name": location_name,
        }
    except Exception:
        return {}


def _dms_to_decimal(gps: dict):
    try:
        def to_dec(dms, ref):
            d, m, s = [(n / d) for n, d in dms]
            dec = d + m / 60 + s / 3600
            if ref in [b'S', b'W']:
                dec = -dec
            return dec
        return (to_dec(gps[2], gps[1]), to_dec(gps[4], gps[3]))
    except Exception:
        return None
