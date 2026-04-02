from __future__ import annotations
import uuid
import asyncio
import os
from datetime import datetime, timezone

import httpx

from orchestrator.state import OSINTState, FindingRecord


class LegalAgent:
    SEC_URL          = "https://efts.sec.gov/LATEST/search-index"
    COMPANIES_HU_URL = "https://api.company-information.service.gov.uk"
    COURT_URL        = "https://www.courtlistener.com/api/rest/v3/search/"
    OFAC_URL         = "https://api.ofac.treas.gov/v1/sdn/search"
    OPENSANCTIONS    = "https://api.opensanctions.org/match/default"

    def __init__(self):
        self.ch_key = os.getenv("COMPANIES_HOUSE_KEY", "")

    def run(self, state: OSINTState) -> dict:
        tasks = [t for t in state["collection_tasks"]
                 if t["type"] == "legal" and t["status"] == "pending"]
        if not tasks:
            return {"agent_trace": [{"agent": "legal_agent", "action": "no_tasks"}]}

        findings = []
        for task in tasks:
            results = asyncio.run(self._collect_all(task["query"]))
            findings.extend(results)

        return {
            "findings": findings,
            "agent_trace": [{
                "agent":     "legal_agent",
                "action":    "collected",
                "count":     len(findings),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

    async def _collect_all(self, query: str) -> list[FindingRecord]:
        results = await asyncio.gather(
            self._sec_edgar(query),
            self._court_listener(query),
            self._ofac_check(query),
            self._opensanctions_check(query),
            return_exceptions=True,
        )
        findings = []
        for r in results:
            if isinstance(r, list):
                findings.extend([x for x in r if x])
        return findings

    async def _sec_edgar(self, query: str) -> list[FindingRecord]:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(self.SEC_URL, params={
                    "q":        f'"{query}"',
                    "forms":    "10-K,8-K,DEF14A,S-1",
                    "dateRange": "custom",
                    "startdt":  "2018-01-01",
                })
            hits = resp.json().get("hits", {}).get("hits", [])
            if not hits:
                return []

            lines = []
            for h in hits[:10]:
                src  = h.get("_source", {})
                lines.append(
                    f"{src.get('form_type', '')} — {src.get('file_date', '')} — "
                    f"{src.get('display_names', '')} — {src.get('period_of_report', '')}"
                )

            return [{
                "id":          str(uuid.uuid4()),
                "source_type": "sec_edgar",
                "source_url":  f"https://efts.sec.gov/LATEST/search-index?q={query}",
                "raw_text":    f"SEC EDGAR filings for '{query}':\n" + "\n".join(lines),
                "title":       f"SEC EDGAR: {len(hits)} filing(s) for {query}",
                "timestamp":   datetime.now(timezone.utc).isoformat(),
                "metadata":    {"filing_count": len(hits), "filings": lines},
            }]
        except Exception:
            return []

    async def _court_listener(self, query: str) -> list[FindingRecord]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(self.COURT_URL, params={
                    "q": query, "type": "o", "order_by": "score desc", "format": "json"
                })
            results = resp.json().get("results", [])[:5]
            if not results:
                return []

            text = "\n".join(
                f"{r.get('caseName', '')} — {r.get('court', '')} — {r.get('dateFiled', '')}"
                for r in results
            )
            return [{
                "id":          str(uuid.uuid4()),
                "source_type": "court_listener",
                "source_url":  f"https://www.courtlistener.com/?q={query}",
                "raw_text":    f"Court records for '{query}':\n{text}",
                "title":       f"CourtListener: {len(results)} case(s) for {query}",
                "timestamp":   datetime.now(timezone.utc).isoformat(),
                "metadata":    {"case_count": len(results)},
            }]
        except Exception:
            return []

    async def _ofac_check(self, query: str) -> list[FindingRecord]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    self.OFAC_URL,
                    params={"name": query, "type": "individual,entity"},
                )
            entries = resp.json().get("sdnList", {}).get("sdnEntry", [])
            if not entries:
                return []

            text = "\n".join(
                f"OFAC SDN HIT: {e.get('lastName', '')} — Program: "
                f"{e.get('programList', '')} — Type: {e.get('sdnType', '')}"
                for e in entries[:5]
            )
            return [{
                "id":          str(uuid.uuid4()),
                "source_type": "ofac_sdn",
                "source_url":  "https://ofac.treasury.gov/specially-designated-nationals-list",
                "raw_text":    text,
                "title":       f"[HIGH RISK] OFAC SDN match for '{query}'",
                "timestamp":   datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "hit_count": len(entries),
                    "risk":      "sanctions_hit",
                },
            }]
        except Exception:
            return []

    async def _opensanctions_check(self, query: str) -> list[FindingRecord]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    self.OPENSANCTIONS,
                    json={"queries": {"e": {"schema": "Thing", "properties": {"name": [query]}}}},
                )
            responses = resp.json().get("responses", {})
            results   = responses.get("e", {}).get("results", [])
            if not results:
                return []

            hits = [r for r in results if r.get("score", 0) > 0.7]
            if not hits:
                return []

            text = "\n".join(
                f"{r.get('caption', '')} — Datasets: "
                f"{', '.join(r.get('datasets', []))} — Score: {r.get('score', 0):.2f}"
                for r in hits[:5]
            )
            return [{
                "id":          str(uuid.uuid4()),
                "source_type": "open_sanctions",
                "source_url":  "https://opensanctions.org",
                "raw_text":    f"OpenSanctions PEP/sanction matches for '{query}':\n{text}",
                "title":       f"[RISK] OpenSanctions: {len(hits)} match(es) for {query}",
                "timestamp":   datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "hit_count": len(hits),
                    "risk":      "pep_or_sanctions",
                },
            }]
        except Exception:
            return []
