from __future__ import annotations

import asyncio
import os
import re
import uuid
from datetime import datetime, timezone

import httpx

from orchestrator.state import FindingRecord, OSINTState

EMAIL_RE = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')


class EmailAgent:
    HUNTER_URL = "https://api.hunter.io/v2"

    def __init__(self):
        self.hunter_key = os.getenv("HUNTER_API_KEY", "")

    def run(self, state: OSINTState) -> dict:
        tasks = [t for t in state["collection_tasks"]
                 if t["type"] == "email" and t["status"] == "pending"]
        if not tasks:
            return {"agent_trace": [{"agent": "email_agent", "action": "no_tasks"}]}

        # Also harvest emails already found in existing findings
        harvested = self._harvest_from_findings(state.get("findings", []))

        findings = list(harvested)
        for task in tasks:
            results = asyncio.run(self._collect_all(task["query"]))
            findings.extend(results)

        return {
            "findings": findings,
            "agent_trace": [{
                "agent":     "email_agent",
                "action":    "collected",
                "count":     len(findings),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

    def _harvest_from_findings(self, findings: list) -> list[FindingRecord]:
        """Extract email addresses already present in collected findings."""
        all_emails: set[str] = set()
        for f in findings:
            # From metadata
            for e in f.get("metadata", {}).get("emails", []):
                all_emails.add(e)
            # From raw text
            for e in EMAIL_RE.findall(f.get("raw_text", "")):
                all_emails.add(e)

        results = []
        for email in all_emails:
            results.append({
                "id":          str(uuid.uuid4()),
                "source_type": "email_harvest",
                "source_url":  "",
                "raw_text":    f"Email address found in collected data: {email}",
                "title":       f"Email: {email}",
                "timestamp":   datetime.now(timezone.utc).isoformat(),
                "metadata":    {"email": email, "via": "harvest"},
            })
        return results

    async def _collect_all(self, domain: str) -> list[FindingRecord]:
        results = await asyncio.gather(
            self._hunter_search(domain),
            return_exceptions=True,
        )
        findings = []
        for r in results:
            if isinstance(r, list):
                findings.extend([x for x in r if x])
        return findings

    async def _hunter_search(self, domain: str) -> list[FindingRecord]:
        if not self.hunter_key:
            return []
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.HUNTER_URL}/domain-search",
                    params={"domain": domain, "api_key": self.hunter_key, "limit": 100},
                )
            data    = resp.json().get("data", {})
            emails  = data.get("emails", [])
            if not emails:
                return []

            text = "\n".join(
                f"{e.get('value', '')} — {e.get('first_name', '')} {e.get('last_name', '')} "
                f"({e.get('position', '')})"
                for e in emails
            )
            return [{
                "id":          str(uuid.uuid4()),
                "source_type": "hunter_io",
                "source_url":  f"https://hunter.io/domain-search/{domain}",
                "raw_text":    text,
                "title":       f"Hunter.io: {len(emails)} email(s) for {domain}",
                "timestamp":   datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "emails":         [e.get("value") for e in emails],
                    "email_count":    len(emails),
                    "pattern":        data.get("pattern", ""),
                    "organization":   data.get("organization", ""),
                },
            }]
        except Exception:
            return []

