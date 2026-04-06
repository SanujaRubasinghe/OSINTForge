from __future__ import annotations
from pathlib import Path
import httpx

from configs.config import api_keys

SERP_URL = "https://serpapi.com/search"
MAX_IMAGES = 5
MAX_REVERSE_RESULTS = 5


async def fetch_images(query: str) -> list[dict]:
    """
    Search Google Images via SerpAPI and return up to MAX_IMAGES results.
    Each result: {title, thumbnail, original, source_url}
    """
    params = {
        "engine":  "google_images",
        "q":       query,
        "num":     MAX_IMAGES,
        "api_key": api_keys.SERPAPI_API_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(SERP_URL, params=params)
        if resp.status_code != 200:
            return []
        data = resp.json()
        results = []
        for item in data.get("images_results", [])[:MAX_IMAGES]:
            results.append({
                "title":      item.get("title", ""),
                "thumbnail":  item.get("thumbnail", ""),
                "original":   item.get("original", ""),
                "source_url": item.get("link", ""),
            })
        return results
    except Exception:
        return []


async def fetch_reverse_image_search(image_path: str) -> list[dict]:
    """
    Reverse image search via SerpAPI Google Reverse Image engine.
    POSTs the local image file and returns up to MAX_REVERSE_RESULTS results.
    Each result: {title, link, source, thumbnail, snippet}
    """
    params = {
        "engine":  "google_reverse_image",
        "api_key": api_keys.SERPAPI_API_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            with open(image_path, "rb") as f:
                resp = await client.post(
                    SERP_URL,
                    params=params,
                    files={"file": (Path(image_path).name, f, "image/jpeg")},
                )
        if resp.status_code != 200:
            return []
        data = resp.json()
        results = []
        for item in data.get("image_results", [])[:MAX_REVERSE_RESULTS]:
            results.append({
                "title":     item.get("title", ""),
                "link":      item.get("link", ""),
                "source":    item.get("source", ""),
                "thumbnail": item.get("thumbnail", ""),
                "snippet":   item.get("snippet", ""),
            })
        return results
    except Exception:
        return []
