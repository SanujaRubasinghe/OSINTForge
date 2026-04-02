from __future__ import annotations
import uuid
import asyncio
from datetime import datetime, timezone

from ddgs import DDGS
from orchestrator.state import OSINTState, FindingRecord

PASTE_SITES = [
    "site:pastebin.com",
    "site:paste.ee",
    "site:ghostbin.co",
    "site:hastebin.com",
    "site:dpaste.org",
]


class PasteCollector:
    def run(self, state: OSINTState) -> dict:
        # Runs opportunistically on any web task query
        tasks = [t for t in state["collection_tasks"]
                 if t["type"] == "web" and t["status"] == "pending"]
        if not tasks:
            return {"agent_trace": [{"agent": "paste_collector", "action": "no_tasks"}]}

        findings = []
        for task in tasks:
            results = self._search_pastes(task["query"])
            findings.extend(results)

        return {
            "findings": findings,
            "agent_trace": [{
                "agent":     "paste_collector",
                "action":    "collected",
                "count":     len(findings),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

    def _search_pastes(self, query: str) -> list[FindingRecord]:
        findings = []
        try:
            with DDGS() as ddg:
                for site in PASTE_SITES:
                    for r in ddg.text(f'{site} "{query}"', max_results=5):
                        findings.append({
                            "id":          str(uuid.uuid4()),
                            "source_type": "paste_collector",
                            "source_url":  r["href"],
                            "raw_text":    r["title"] + " " + r["body"],
                            "title":       f"[LEAK?] {r['title']}",
                            "timestamp":   datetime.now(timezone.utc).isoformat(),
                            "metadata": {
                                "paste_site": site,
                                "risk":       "potential_leak",
                            },
                        })
        except Exception:
            pass
        return findings
