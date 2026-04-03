from __future__ import annotations
import httpx

from configs.config import api_keys

SERP_URL = "https://serpapi.com/search"
MAX_IMAGES = 5


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
