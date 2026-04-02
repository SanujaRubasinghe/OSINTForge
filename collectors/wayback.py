from __future__ import annotations
import uuid
import asyncio
from datetime import datetime, timezone

import httpx

from orchestrator.state import OSINTState, FindingRecord

CDX_API = "http://web.archive.org/cdx/search/cdx"


class WaybackCollector:
    def run(self, state: OSINTState) -> dict:
        # Triggered by web tasks that include a known domain
        tasks = [t for t in state["collection_tasks"]
                 if t["type"] == "web" and "." in t["query"] and t["status"] == "pending"]
        if not tasks:
            return {"agent_trace": [{"agent": "wayback", "action": "no_tasks"}]}

        findings = []
        for task in tasks:
            domain = self._extract_domain(task["query"])
            if not domain:
                continue
            results = asyncio.run(self._collect(domain))
            findings.extend(results)

        return {
            "findings": findings,
            "agent_trace": [{
                "agent":     "wayback",
                "action":    "collected",
                "count":     len(findings),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

    def _extract_domain(self, query: str) -> str | None:
        import re
        m = re.search(r'([a-zA-Z0-9-]+\.[a-zA-Z]{2,})', query)
        return m.group(1) if m else None

    async def _collect(self, domain: str) -> list[FindingRecord]:
        results = await asyncio.gather(
            self._snapshot_history(domain),
            self._deleted_pages(domain),
            return_exceptions=True,
        )
        findings = []
        for r in results:
            if isinstance(r, list):
                findings.extend([x for x in r if x])
        return findings

    async def _snapshot_history(self, domain: str) -> list[FindingRecord]:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(CDX_API, params={
                    "url":      f"{domain}/*",
                    "output":   "json",
                    "fl":       "timestamp,original,statuscode",
                    "collapse": "timestamp:6",
                    "limit":    36,
                    "from":     "20150101",
                })
            rows = resp.json()[1:]   # skip header
            if not rows:
                return []

            text = (
                f"Wayback Machine snapshots for {domain} ({len(rows)} found):\n"
                + "\n".join(
                    f"  {r[0][:6]}-{r[0][6:8]}: {r[1]} [{r[2]}]"
                    for r in rows[:20]
                )
            )
            return [{
                "id":          str(uuid.uuid4()),
                "source_type": "wayback_history",
                "source_url":  f"https://web.archive.org/web/*/{domain}",
                "raw_text":    text,
                "title":       f"Wayback: {len(rows)} archive snapshots for {domain}",
                "timestamp":   datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "snapshot_count": len(rows),
                    "domain":         domain,
                    "oldest":         rows[-1][0] if rows else None,
                    "newest":         rows[0][0]  if rows else None,
                },
            }]
        except Exception:
            return []

    async def _deleted_pages(self, domain: str) -> list[FindingRecord]:
        """Surface URLs that appear in the archive but are no longer live."""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                archived_resp = await client.get(CDX_API, params={
                    "url":      f"{domain}/*",
                    "output":   "json",
                    "fl":       "original",
                    "collapse": "urlkey",
                    "limit":    200,
                })
                archived_urls = {r[0] for r in archived_resp.json()[1:]}

                # Fetch current sitemap
                try:
                    sitemap_resp = await client.get(
                        f"https://{domain}/sitemap.xml", timeout=8
                    )
                    current_text = sitemap_resp.text
                    import re
                    current_urls = set(re.findall(r'<loc>(https?://[^<]+)</loc>', current_text))
                except Exception:
                    current_urls = set()

            deleted = archived_urls - current_urls
            if not deleted:
                return []

            sample = list(deleted)[:20]
            text = (
                f"Potentially deleted/removed URLs for {domain} "
                f"(found in archive, not in current sitemap):\n"
                + "\n".join(f"  - {u}" for u in sample)
            )
            return [{
                "id":          str(uuid.uuid4()),
                "source_type": "wayback_deleted",
                "source_url":  f"https://web.archive.org/web/*/{domain}",
                "raw_text":    text,
                "title":       f"Wayback: {len(deleted)} potentially deleted pages on {domain}",
                "timestamp":   datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "deleted_count": len(deleted),
                    "sample_urls":   sample,
                },
            }]
        except Exception:
            return []
