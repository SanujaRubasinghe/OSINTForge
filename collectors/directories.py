import httpx

class CrunchBaseCollector:
    BASE_URL = "https://api.crunchbase.com/api/v4"
    API_KEY = "crunch-base-api-key"

    async def fetch_organization(self, org_name: str) -> dict:
        async with httpx.AsyncClient() as client:
            search_resp = await client.post(
                f"{self.BASE_URL}/searches/organizations",
                json={
                    "field_ids": ["short_description", "website_url", "founded_on",
                                  "num_employees_enum", "location_identifiers"],
                    "query": [{
                        "type": "predicate",
                        "field_id": "facet_ids",
                        "operator_id": "includes",
                        "values": ["company"]
                    }],
                    "limit": 5
                },
                params={"user_key": self.API_KEY}
            )
            return search_resp.json()
        

class SECEdgarCollector:
    async def fetch_filings(self, company_name: str) -> list[dict]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://efts.sec.gov/LATEST/search-index",
                headers={"User-Agent": "Mozilla/5.0"},
                params={
                    "q": f'"{company_name}"',
                    "dateRange": "custom",
                    "startdt": "2020-01-01",
                    "forms": "10-K,8-K,DEF14A"
                }
            )

            if resp.status_code != 200:
                raise Exception(f"Request failed: {resp.status_code} - {resp.text}")

            if not resp.content:
                raise Exception("Empty response received")
            return resp.json()["hits"]["hits"]