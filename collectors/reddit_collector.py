from __future__ import annotations
import asyncio
import os
from datetime import datetime, timezone, timedelta

import asyncpraw
from ddgs import DDGS


async def search_reddit(query: str, max_posts: int = 50,
                         time_filter: str = "year") -> list[dict]:
    """
    Search Reddit using the public API.
    Falls back to DDG site:reddit.com if no API credentials are set.
    """
    client_id     = os.getenv("REDDIT_CLIENT_ID", "")
    client_secret = os.getenv("REDDIT_SECRET", "")

    if client_id and client_secret:
        return await _asyncpraw_search(query, client_id, client_secret,
                                        max_posts, time_filter)
    return _ddg_reddit_search(query, max_posts)


async def _asyncpraw_search(query: str, client_id: str, secret: str,
                              max_posts: int, time_filter: str) -> list[dict]:
    posts = []
    try:
        reddit = asyncpraw.Reddit(
            client_id     = client_id,
            client_secret = secret,
            user_agent    = "OSINTForge/1.0 (read-only)",
        )
        async for post in reddit.subreddit("all").search(
            query, sort="relevance", time_filter=time_filter, limit=max_posts
        ):
            posts.append({
                "title":        post.title,
                "url":          f"https://reddit.com{post.permalink}",
                "text":         (post.selftext or "")[:1500],
                "subreddit":    post.subreddit.display_name,
                "score":        post.score,
                "num_comments": post.num_comments,
                "author":       str(post.author) if post.author else None,
                "created":      datetime.fromtimestamp(
                    post.created_utc, tz=timezone.utc
                ).isoformat(),
            })
        await reddit.close()
    except Exception:
        pass
    return posts


def _ddg_reddit_search(query: str, max_results: int = 20) -> list[dict]:
    posts = []
    try:
        with DDGS() as ddg:
            for r in ddg.text(f'site:reddit.com "{query}"', max_results=max_results):
                posts.append({
                    "title":        r["title"],
                    "url":          r["href"],
                    "text":         r["body"],
                    "subreddit":    _extract_subreddit(r["href"]),
                    "score":        None,
                    "num_comments": None,
                    "author":       None,
                    "created":      datetime.now(timezone.utc).isoformat(),
                })
    except Exception:
        pass
    return posts


def _extract_subreddit(url: str) -> str:
    import re
    m = re.search(r'reddit\.com/r/([^/]+)', url)
    return m.group(1) if m else "unknown"
