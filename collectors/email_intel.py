from __future__ import annotations
import asyncio
import os
import re

import httpx

HUNTER_URL = "https://api.hunter.io/v2"
HIBP_URL   = "https://haveibeenpwned.com/api/v3"
EMAIL_RE   = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')


async def hunter_domain_search(domain: str) -> dict:
    key = os.getenv("HUNTER_API_KEY", "")
    if not key:
        return {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{HUNTER_URL}/domain-search",
                params={"domain": domain, "api_key": key, "limit": 100},
            )
        return resp.json().get("data", {})
    except Exception:
        return {}


async def hunter_verify(email: str) -> dict:
    """SMTP probe — verifies deliverability without sending mail."""
    key = os.getenv("HUNTER_API_KEY", "")
    if not key:
        return {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{HUNTER_URL}/email-verifier",
                params={"email": email, "api_key": key},
            )
        return resp.json().get("data", {})
    except Exception:
        return {}


async def hibp_check_email(email: str) -> list[dict]:
    """Check a single email against Have I Been Pwned."""
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


async def hibp_check_domain(domain: str) -> list[dict]:
    """Check all breaches affecting a domain."""
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


def extract_emails_from_text(text: str) -> list[str]:
    return list(set(EMAIL_RE.findall(text)))


def infer_email_patterns(known_emails: list[str]) -> str | None:
    """
    Given a list of confirmed emails from the same domain,
    infer the naming convention (e.g., {first}.{last}@domain.com).
    """
    import re as _re
    if not known_emails:
        return None

    domain = known_emails[0].split("@")[1] if "@" in known_emails[0] else ""
    local_parts = [e.split("@")[0] for e in known_emails if "@" in e]

    # Simple heuristic: check for dot-separated first.last
    dot_count = sum(1 for lp in local_parts if "." in lp)
    if dot_count > len(local_parts) / 2:
        return f"{{first}}.{{last}}@{domain}"

    return None
