from __future__ import annotations
import uuid
import asyncio
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from datasketch import MinHash, MinHashLSH

from orchestrator.state import OSINTState, FindingRecord


class WebCollectorAgent:
    MAX_RESULTS   = 20
    MAX_PAGES     = 8
    TIMEOUT       = 15
    LSH_THRESHOLD = 0.7          # cosine sim threshold for dedup
    NUM_PERM      = 128

    def __init__(self):
        self._lsh   = MinHashLSH(threshold=self.LSH_THRESHOLD, num_perm=self.NUM_PERM)
        self._seen  : set[str] = set()

    def run(self, state: OSINTState) -> dict:
        tasks = [t for t in state["collection_tasks"] if t["type"] == "web" and t["status"] == "pending"]
        if not tasks:
            return {"agent_trace": [{"agent": "web_collector", "action": "no_tasks"}]}

        findings: list[FindingRecord] = []
        for task in tasks:
            results = asyncio.run(self._collect(task["query"]))
            findings.extend(results)

        deduped = self._deduplicate(findings)

        return {
            "findings": deduped,
            "agent_trace": [{
                "agent":         "web_collector",
                "action":        "collected",
                "raw_count":     len(findings),
                "deduped_count": len(deduped),
                "timestamp":     datetime.now(timezone.utc).isoformat(),
            }],
        }

    async def _collect(self, query: str) -> list[FindingRecord]:
        urls = self._ddg_search(query)
        pages = await self._fetch_pages(urls)
        return pages

    def _ddg_search(self, query: str) -> list[str]:
        urls = []
        try:
            with DDGS() as ddg:
                for r in ddg.text(query, max_results=self.MAX_RESULTS):
                    urls.append(r["href"])
        except Exception:
            pass
        return urls[:self.MAX_PAGES]

    async def _fetch_pages(self, urls: list[str]) -> list[FindingRecord]:
        results = []
        async with httpx.AsyncClient(timeout=self.TIMEOUT, follow_redirects=True,
                                      headers={"User-Agent": "Mozilla/5.0"}) as client:
            tasks = [self._fetch_one(client, url) for url in urls]
            pages = await asyncio.gather(*tasks, return_exceptions=True)
        for p in pages:
            if isinstance(p, FindingRecord):
                results.append(p)
        return results

    async def _fetch_one(self, client: httpx.AsyncClient, url: str) -> FindingRecord | None:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            title = soup.title.string.strip() if soup.title else ""
            body  = " ".join(soup.get_text(" ", strip=True).split())[:4000]
            emails = self._extract_emails(body)
            return {
                "id":          str(uuid.uuid4()),
                "source_type": "web",
                "source_url":  str(resp.url),
                "raw_text":    body,
                "title":       title,
                "timestamp":   datetime.now(timezone.utc).isoformat(),
                "metadata":    {"emails": emails, "status_code": resp.status_code},
            }
        except Exception:
            return None

    def _extract_emails(self, text: str) -> list[str]:
        import re
        return list(set(re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', text)))

    def _deduplicate(self, findings: list[FindingRecord]) -> list[FindingRecord]:
        unique = []
        for f in findings:
            if f["source_url"] in self._seen:
                continue
            m = MinHash(num_perm=self.NUM_PERM)
            for word in f["raw_text"].split():
                m.update(word.encode("utf-8"))
            try:
                if not self._lsh.query(m):
                    self._lsh.insert(f["id"], m)
                    self._seen.add(f["source_url"])
                    unique.append(f)
            except Exception:
                unique.append(f)
        return unique
