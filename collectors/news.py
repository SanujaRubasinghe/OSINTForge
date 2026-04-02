from __future__ import annotations
import os
import asyncio
from datetime import datetime, timezone

import httpx
import feedparser

GDELT_API   = "https://api.gdeltproject.org/api/v2/doc/doc"
NEWSAPI_URL = "https://newsapi.org/v2/everything"

RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
]


async def gdelt_search(query: str, days_back: int = 90,
                        max_records: int = 50) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(GDELT_API, params={
                "query":      query,
                "mode":       "artlist",
                "maxrecords": max_records,
                "format":     "json",
                "timespan":   f"{days_back}d",
                "sort":       "toneasc",
            })
        return resp.json().get("articles", [])
    except Exception:
        return []


async def gdelt_timeline(query: str, days_back: int = 90) -> dict:
    """Coverage volume over time — useful for timeline analysis."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(GDELT_API, params={
                "query":    query,
                "mode":     "timelinevol",
                "format":   "json",
                "timespan": f"{days_back}d",
            })
        return resp.json()
    except Exception:
        return {}


async def newsapi_search(query: str, page_size: int = 30) -> list[dict]:
    key = os.getenv("NEWSAPI_KEY", "")
    if not key:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(NEWSAPI_URL, params={
                "q":        query,
                "sortBy":   "relevancy",
                "language": "en",
                "pageSize": page_size,
                "apiKey":   key,
            })
        return resp.json().get("articles", [])
    except Exception:
        return []


def rss_search(query: str, feeds: list[str] | None = None) -> list[dict]:
    if feeds is None:
        feeds = RSS_FEEDS
    q_lower  = query.lower()
    articles = []
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                content = (entry.get("summary", "") + entry.get("title", "")).lower()
                if q_lower in content:
                    articles.append({
                        "title":     entry.get("title", ""),
                        "url":       entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "summary":   entry.get("summary", ""),
                        "feed":      feed_url,
                    })
        except Exception:
            pass
    return articles


async def collect_all(query: str) -> dict:
    gdelt_results, news_results = await asyncio.gather(
        gdelt_search(query),
        newsapi_search(query),
    )
    rss_results = rss_search(query)
    return {
        "query":   query,
        "gdelt":   gdelt_results,
        "newsapi": news_results,
        "rss":     rss_results,
        "total":   len(gdelt_results) + len(news_results) + len(rss_results),
    }
