import httpx

from configs.config import api_keys

BASE_URL = "https://serpapi.com/search.json"

class LinkedInSurfaceCollectors:

    async def search_profiles(self, query: str) -> list[dict]:
        search_query = f'site:linkedin.com/in/ "{query}"'

        params = {
            "q": search_query,
            "engine": "google",
            "api_key": api_keys.SERPAPI_API_KEY
        }
        
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(BASE_URL, params=params)

            if resp.status_code != 200:
                raise RuntimeError(f"SerpAPI error: {resp.status_code}: {resp.text}")
            
            data = resp.json()

        organic_results = data.get("organic_results", [])

        profiles = []
        for r in organic_results:
            profiles.append({
                "name": r.get("title"),
                "headline": r.get("snippet"),
                "url": r.get("link"),
                "source": "linkedin_surface"
            })

        return profiles
    
    async def search_company_employees(self, company: str) -> list[dict]:
        search_query = f'site:linkedin.com/in {company}'
        return await self.search_profiles(search_query)
    
    async def search_company_page(self, company: str) -> dict:
        search_query = f'site:linkedin.com/company/ "{company}"'

        params = {
            "q": search_query,
            "engine": "google",
            "api_key": api_keys.SERPAPI_API_KEY
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(BASE_URL, params=params)

            if resp.status_code != 200:
                raise RuntimeError(f"SerpAPI error: {resp.status_code}: {resp.text}")
            
            data = resp.json()

        organic_results = data.get("organic_results", [])

        return organic_results[0] if organic_results else {}

    
