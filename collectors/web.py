import httpx
from ddgs import DDGS

class WebCollector:
    async def search(self, query: str, max_results: int = 20) -> list[dict]:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r["title"],
                    "url": r["href"],
                    "snippet": r["body"],
                    "source": "duckduckgo"
                })
        return results
    
    async def fetch_page(self, url: str) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            return {
                "url": url,
                "status_code": response.status_code,
                "html": response.text,
                "final_url": str(response.url)
            }