from __future__ import annotations
import asyncio
import httpx

INTERNAL_KEYWORDS = [
    "vpn", "internal", "corp", "dev", "staging", "test",
    "jenkins", "jira", "confluence", "gitlab", "admin",
    "api-dev", "api-staging", "intranet", "ldap",
]


async def query_crtsh(domain: str) -> list[dict]:
    """Query Certificate Transparency logs via crt.sh."""
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.get(
                "https://crt.sh/",
                params={"q": f"%.{domain}", "output": "json"},
            )
        return resp.json()
    except Exception:
        return []


def extract_subdomains(certs: list[dict], domain: str) -> dict:
    """
    From a list of cert records, extract:
    - all subdomains
    - subdomains that suggest internal/staging infrastructure
    """
    all_subs: set[str] = set()
    internal: set[str] = set()

    for cert in certs:
        for name in cert.get("name_value", "").split("\n"):
            name = name.strip().lstrip("*.")
            if not name.endswith(domain) or name == domain:
                continue
            all_subs.add(name)
            if any(k in name.lower() for k in INTERNAL_KEYWORDS):
                internal.add(name)

    return {
        "all_subdomains":      sorted(all_subs),
        "internal_signals":    sorted(internal),
        "total_certs":         len(certs),
        "subdomain_count":     len(all_subs),
        "internal_count":      len(internal),
    }


async def collect(domain: str) -> dict:
    """Full certificate intelligence collection for a domain."""
    certs  = await query_crtsh(domain)
    result = extract_subdomains(certs, domain)
    result["domain"] = domain
    return result
