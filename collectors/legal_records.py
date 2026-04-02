from __future__ import annotations
import asyncio
import httpx

COURT_URL     = "https://www.courtlistener.com/api/rest/v3/search/"
OFAC_URL      = "https://api.ofac.treas.gov/v1/sdn/search"
OPENSANCTIONS = "https://api.opensanctions.org/match/default"


async def court_listener_search(query: str, count: int = 10) -> list[dict]:
    """Search CourtListener for US federal and state court opinions."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(COURT_URL, params={
                "q":        query,
                "type":     "o",
                "order_by": "score desc",
                "format":   "json",
            })
        results = resp.json().get("results", [])[:count]
        return [
            {
                "case_name":  r.get("caseName"),
                "court":      r.get("court"),
                "date_filed": r.get("dateFiled"),
                "url":        r.get("absolute_url"),
                "snippet":    r.get("snippet", "")[:200],
            }
            for r in results
        ]
    except Exception:
        return []


async def ofac_sdn_search(name: str) -> list[dict]:
    """Check OFAC Specially Designated Nationals list."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                OFAC_URL,
                params={"name": name, "type": "individual,entity"},
            )
        entries = resp.json().get("sdnList", {}).get("sdnEntry", [])
        return [
            {
                "name":    entry.get("lastName"),
                "type":    entry.get("sdnType"),
                "program": entry.get("programList"),
                "risk":    "ofac_sdn_hit",
            }
            for entry in entries[:5]
        ]
    except Exception:
        return []


async def opensanctions_match(name: str, schema: str = "Thing") -> list[dict]:
    """Match a name against OpenSanctions PEP and sanctions database."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                OPENSANCTIONS,
                json={"queries": {"e": {"schema": schema,
                                         "properties": {"name": [name]}}}},
            )
        results = resp.json().get("responses", {}).get("e", {}).get("results", [])
        return [
            {
                "caption":   r.get("caption"),
                "score":     r.get("score"),
                "datasets":  r.get("datasets", []),
                "url":       r.get("id"),
                "risk":      "pep_or_sanctions",
            }
            for r in results
            if r.get("score", 0) > 0.65
        ]
    except Exception:
        return []


async def check_all(name: str) -> dict:
    court, ofac, sanctions = await asyncio.gather(
        court_listener_search(name),
        ofac_sdn_search(name),
        opensanctions_match(name),
    )
    return {
        "court_cases": court,
        "ofac_hits":   ofac,
        "sanctions":   sanctions,
        "risk_score":  ("HIGH" if ofac or sanctions else
                        "MEDIUM" if court else "LOW"),
    }
