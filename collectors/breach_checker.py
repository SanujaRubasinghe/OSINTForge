from __future__ import annotations
import asyncio
import os
import httpx

HIBP_URL = "https://haveibeenpwned.com/api/v3"


async def check_email(email: str) -> list[dict]:
    key = os.getenv("HIBP_API_KEY", "")
    if not key:
        return []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{HIBP_URL}/breachedaccount/{email}",
                headers={"hibp-api-key": key, "User-Agent": "OSINTForge"},
            )
        if resp.status_code == 404:
            return []
        return resp.json()
    except Exception:
        return []


async def check_domain(domain: str) -> list[dict]:
    key = os.getenv("HIBP_API_KEY", "")
    if not key:
        return []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{HIBP_URL}/breaches",
                params={"domain": domain},
                headers={"hibp-api-key": key, "User-Agent": "OSINTForge"},
            )
        if resp.status_code == 404:
            return []
        return resp.json()
    except Exception:
        return []


def summarise_breaches(breaches: list[dict]) -> str:
    if not breaches:
        return "No breaches found."
    lines = []
    for b in breaches:
        classes = ", ".join(b.get("DataClasses", [])[:4])
        lines.append(f"{b['Name']} ({b['BreachDate']}) — {classes}")
    return "\n".join(lines)
