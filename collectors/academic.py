from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import arxiv
import httpx

from orchestrator.state import FindingRecord, OSINTState

SEMANTIC_SCHOLAR = "https://api.semanticscholar.org/graph/v1/paper/search"


class AcademicCollector:
    def run(self, state: OSINTState) -> dict:
        tasks = [t for t in state["collection_tasks"]
                 if t["type"] in ("web", "news") and t["status"] == "pending"]
        if not tasks:
            return {"agent_trace": [{"agent": "academic_collector", "action": "no_tasks"}]}

        findings = []
        for task in tasks:
            results = asyncio.run(self._collect_all(task["query"]))
            findings.extend(results)

        return {
            "findings": findings,
            "agent_trace": [{
                "agent":     "academic_collector",
                "action":    "collected",
                "count":     len(findings),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

    async def _collect_all(self, query: str) -> list[FindingRecord]:
        results = await asyncio.gather(
            self._semantic_scholar(query),
            asyncio.to_thread(self._arxiv_search, query),
            return_exceptions=True,
        )
        findings = []
        for r in results:
            if isinstance(r, list):
                findings.extend([x for x in r if x])
        return findings

    async def _semantic_scholar(self, query: str) -> list[FindingRecord]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(SEMANTIC_SCHOLAR, params={
                    "query":  query,
                    "limit":  10,
                    "fields": "title,authors,year,abstract,citationCount,url",
                })
            papers = resp.json().get("data", [])
            if not papers:
                return []

            text = "\n\n".join(
                f"Title: {p.get('title', '')}\n"
                f"Authors: {', '.join(a['name'] for a in p.get('authors', [])[:5])}\n"
                f"Year: {p.get('year', '')}\n"
                f"Citations: {p.get('citationCount', 0)}\n"
                f"Abstract: {(p.get('abstract') or '')[:300]}"
                for p in papers[:5]
            )
            return [{
                "id":          str(uuid.uuid4()),
                "source_type": "semantic_scholar",
                "source_url":  f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}",
                "raw_text":    text,
                "title":       f"Semantic Scholar: {len(papers)} paper(s) for '{query}'",
                "timestamp":   datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "paper_count": len(papers),
                    "authors": list({
                        a["name"]
                        for p in papers
                        for a in p.get("authors", [])
                    }),
                },
            }]
        except Exception:
            return []

    def _arxiv_search(self, query: str) -> list[FindingRecord]:
        try:
            search  = arxiv.Search(query=query, max_results=8,
                                   sort_by=arxiv.SortCriterion.Relevance)
            results = list(search.results())
            if not results:
                return []

            text = "\n\n".join(
                f"Title: {r.title}\n"
                f"Authors: {', '.join(str(a) for a in r.authors[:5])}\n"
                f"Published: {r.published.strftime('%Y-%m-%d')}\n"
                f"Abstract: {r.summary[:300]}"
                for r in results[:5]
            )
            return [{
                "id":          str(uuid.uuid4()),
                "source_type": "arxiv",
                "source_url":  results[0].entry_id if results else "https://arxiv.org",
                "raw_text":    text,
                "title":       f"arXiv: {len(results)} paper(s) for '{query}'",
                "timestamp":   datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "paper_count": len(results),
                    "authors": list({str(a) for r in results for a in r.authors}),
                },
            }]
        except Exception:
            return []
