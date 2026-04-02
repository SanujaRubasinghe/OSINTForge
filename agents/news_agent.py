from __future__ import annotations
import uuid
import os
import asyncio
from datetime import datetime, timezone

import httpx
import feedparser

from orchestrator.state import OSINTState, FindingRecord


class NewsAgent:
    GDELT_API   = "https://api.gdeltproject.org/api/v2/doc/doc"
    NEWSAPI_URL = "https://newsapi.org/v2/everything"
    RSS_FEEDS   = [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
    ]

    def __init__(self):
        self.newsapi_key = os.getenv("NEWSAPI_KEY", "")

    def run(self, state: OSINTState) -> dict:
        tasks = [t for t in state["collection_tasks"] if t["type"] == "news" and t["status"] == "pending"]
        if not tasks:
            return {"agent_trace": [{"agent": "news_agent", "action": "no_tasks"}]}

        findings = []
        for task in tasks:
            results = asyncio.run(self._collect_all(task["query"]))
            findings.extend(results)

        return {
            "findings": findings,
            "agent_trace": [{
                "agent":     "news_agent",
                "action":    "collected",
                "count":     len(findings),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

    async def _collect_all(self, query: str) -> list[FindingRecord]:
        results = await asyncio.gather(
            self._gdelt_search(query),
            self._newsapi_search(query),
            asyncio.to_thread(self._rss_search, query),
            return_exceptions=True,
        )
        findings = []
        for r in results:
            if isinstance(r, list):
                findings.extend([x for x in r if x])
        return findings

    async def _gdelt_search(self, query: str) -> list[FindingRecord]:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(self.GDELT_API, params={
                    "query":      query,
                    "mode":       "artlist",
                    "maxrecords": 50,
                    "format":     "json",
                    "timespan":   "90d",
                    "sort":       "toneasc",
                })
            articles = resp.json().get("articles", [])
            return [self._gdelt_to_finding(a) for a in articles if a.get("url")]
        except Exception:
            return []

    def _gdelt_to_finding(self, article: dict) -> FindingRecord:
        return {
            "id":          str(uuid.uuid4()),
            "source_type": "gdelt_news",
            "source_url":  article.get("url", ""),
            "raw_text":    f"{article.get('title', '')} — {article.get('seendates', '')}",
            "title":       article.get("title", ""),
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "tone":    article.get("tone"),
                "domain":  article.get("domain"),
                "language": article.get("language"),
            },
        }

    async def _newsapi_search(self, query: str) -> list[FindingRecord]:
        if not self.newsapi_key:
            return []
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(self.NEWSAPI_URL, params={
                    "q":        query,
                    "sortBy":   "relevancy",
                    "language": "en",
                    "pageSize": 30,
                    "apiKey":   self.newsapi_key,
                })
            articles = resp.json().get("articles", [])
            return [{
                "id":          str(uuid.uuid4()),
                "source_type": "newsapi",
                "source_url":  a.get("url", ""),
                "raw_text":    f"{a.get('title', '')} {a.get('description', '')} {a.get('content', '')}",
                "title":       a.get("title", ""),
                "timestamp":   a.get("publishedAt", datetime.now(timezone.utc).isoformat()),
                "metadata":    {"source": a.get("source", {}).get("name")},
            } for a in articles if a.get("url")]
        except Exception:
            return []

    def _rss_search(self, query: str) -> list[FindingRecord]:
        findings = []
        q_lower = query.lower()
        for feed_url in self.RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    content = (entry.get("summary", "") + " " + entry.get("title", "")).lower()
                    if q_lower in content:
                        findings.append({
                            "id":          str(uuid.uuid4()),
                            "source_type": "rss",
                            "source_url":  entry.get("link", ""),
                            "raw_text":    entry.get("title", "") + " " + entry.get("summary", ""),
                            "title":       entry.get("title", ""),
                            "timestamp":   entry.get("published", datetime.now(timezone.utc).isoformat()),
                            "metadata":    {"feed": feed_url},
                        })
            except Exception:
                pass
        return findings
