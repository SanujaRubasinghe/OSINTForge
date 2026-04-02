from __future__ import annotations
import uuid
import asyncio
from datetime import datetime, timezone

import asyncpraw
import os

from orchestrator.state import OSINTState, FindingRecord


class RedditAgent:
    MAX_POSTS    = 100
    COMMENT_DEPTH = 2

    def __init__(self):
        self.client_id     = os.getenv("REDDIT_CLIENT_ID", "")
        self.client_secret = os.getenv("REDDIT_SECRET", "")

    def run(self, state: OSINTState) -> dict:
        tasks = [t for t in state["collection_tasks"]
                 if t["type"] == "reddit" and t["status"] == "pending"]
        if not tasks:
            return {"agent_trace": [{"agent": "reddit_agent", "action": "no_tasks"}]}

        findings = []
        for task in tasks:
            results = asyncio.run(self._search(task["query"]))
            findings.extend(results)

        return {
            "findings": findings,
            "agent_trace": [{
                "agent":     "reddit_agent",
                "action":    "collected",
                "count":     len(findings),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

    async def _search(self, query: str) -> list[FindingRecord]:
        if not self.client_id:
            # Fallback: search via Pushshift-style DDG search
            return await self._ddg_reddit_fallback(query)

        findings = []
        try:
            reddit = asyncpraw.Reddit(
                client_id     = self.client_id,
                client_secret = self.client_secret,
                user_agent    = "OSINTForge/1.0 (read-only research)",
            )
            async for post in reddit.subreddit("all").search(
                query, sort="relevance", time_filter="year", limit=self.MAX_POSTS
            ):
                body = (post.selftext or "")[:2000]
                findings.append({
                    "id":          str(uuid.uuid4()),
                    "source_type": "reddit",
                    "source_url":  f"https://reddit.com{post.permalink}",
                    "raw_text":    f"{post.title}\n{body}",
                    "title":       post.title,
                    "timestamp":   datetime.fromtimestamp(
                        post.created_utc, tz=timezone.utc
                    ).isoformat(),
                    "metadata": {
                        "subreddit":    post.subreddit.display_name,
                        "score":        post.score,
                        "num_comments": post.num_comments,
                        "author":       str(post.author) if post.author else None,
                    },
                })
            await reddit.close()
        except Exception:
            pass
        return findings

    async def _ddg_reddit_fallback(self, query: str) -> list[FindingRecord]:
        """Use DuckDuckGo site:reddit.com search when no API key is available."""
        from duckduckgo_search import DDGS
        findings = []
        try:
            with DDGS() as ddg:
                for r in ddg.text(f'site:reddit.com "{query}"', max_results=20):
                    findings.append({
                        "id":          str(uuid.uuid4()),
                        "source_type": "reddit",
                        "source_url":  r["href"],
                        "raw_text":    r["title"] + " " + r["body"],
                        "title":       r["title"],
                        "timestamp":   datetime.now(timezone.utc).isoformat(),
                        "metadata":    {"via": "ddg_fallback"},
                    })
        except Exception:
            pass
        return findings
