from __future__ import annotations
import asyncio
import httpx


async def search_yandex(image_path: str) -> list[str]:
    """
    Upload image to Yandex CBir and return matching page URLs.
    Yandex gives the best results for photos of people and scenes.
    """
    urls = []
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            with open(image_path, "rb") as f:
                resp = await client.post(
                    "https://yandex.com/images/search",
                    params={"rpt": "imageview", "format": "json"},
                    files={"upfile": ("image.jpg", f, "image/jpeg")},
                    headers={"User-Agent": "Mozilla/5.0"},
                )
            if resp.status_code in (200, 302):
                # Parse redirect URL which contains the search query
                final = str(resp.url)
                if "cbir_id" in final or "imgurl" in final:
                    urls.append(final)
    except Exception:
        pass
    return urls


async def search_tineye(image_path: str, api_key: str = "") -> list[str]:
    """
    TinEye reverse image search.
    Free API tier: 100 searches/month.
    Returns URLs of pages containing matching images.
    """
    urls = []
    if not api_key:
        return urls
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            with open(image_path, "rb") as f:
                resp = await client.post(
                    "https://api.tineye.com/rest/search/",
                    params={"api_key": api_key},
                    files={"image": ("image.jpg", f, "image/jpeg")},
                )
            if resp.status_code == 200:
                matches = resp.json().get("results", {}).get("matches", [])
                for m in matches[:20]:
                    for img in m.get("image_url", []):
                        urls.append(img)
    except Exception:
        pass
    return urls


async def search_all(image_path: str, tineye_key: str = "") -> list[str]:
    """Run all reverse search engines in parallel, return deduplicated URLs."""
    results = await asyncio.gather(
        search_yandex(image_path),
        search_tineye(image_path, tineye_key),
        return_exceptions=True,
    )
    seen: set[str] = set()
    urls: list[str] = []
    for r in results:
        if isinstance(r, list):
            for url in r:
                if url not in seen:
                    seen.add(url)
                    urls.append(url)
    return urls
