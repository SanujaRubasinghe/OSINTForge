from __future__ import annotations
import asyncio
import os
import httpx

SEC_URL  = "https://efts.sec.gov/LATEST/search-index"
CH_URL   = "https://api.company-information.service.gov.uk"
OC_URL   = "https://api.opencorporates.com/v0.4/companies/search"


async def sec_edgar_search(query: str, forms: str = "10-K,8-K,DEF14A,S-1",
                             from_date: str = "2018-01-01") -> list[dict]:
    """Full-text search of SEC EDGAR filings."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(SEC_URL, params={
                "q":        f'"{query}"',
                "forms":    forms,
                "dateRange": "custom",
                "startdt":  from_date,
            })
        hits = resp.json().get("hits", {}).get("hits", [])
        return [
            {
                "form_type":      h["_source"].get("form_type"),
                "file_date":      h["_source"].get("file_date"),
                "company":        h["_source"].get("display_names"),
                "period":         h["_source"].get("period_of_report"),
                "filing_url":     h["_source"].get("file_date"),
            }
            for h in hits[:20]
        ]
    except Exception:
        return []


async def companies_house_search(company_name: str) -> dict:
    """Search UK Companies House for a company and fetch officers."""
    key = os.getenv("COMPANIES_HOUSE_KEY", "")
    if not key:
        return {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            search = await client.get(
                f"{CH_URL}/search/companies",
                params={"q": company_name},
                auth=(key, ""),
            )
            items = search.json().get("items", [])
            if not items:
                return {}

            number = items[0]["company_number"]
            officers_resp = await client.get(
                f"{CH_URL}/company/{number}/officers",
                auth=(key, ""),
            )
            filing_resp = await client.get(
                f"{CH_URL}/company/{number}/filing-history",
                auth=(key, ""),
            )

        return {
            "company_number": number,
            "company_name":   items[0].get("title"),
            "status":         items[0].get("company_status"),
            "type":           items[0].get("company_type"),
            "officers":       officers_resp.json().get("items", [])[:20],
            "filings":        filing_resp.json().get("items", [])[:20],
        }
    except Exception:
        return {}


async def opencorporates_search(company_name: str,
                                 jurisdiction: str | None = None) -> list[dict]:
    """Search the OpenCorporates global company database."""
    params: dict = {"q": company_name, "format": "json"}
    if jurisdiction:
        params["jurisdiction_code"] = jurisdiction
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(OC_URL, params=params)
        companies = resp.json().get("results", {}).get("companies", [])
        return [c.get("company", {}) for c in companies[:10]]
    except Exception:
        return []
