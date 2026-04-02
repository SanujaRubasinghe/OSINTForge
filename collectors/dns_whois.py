from __future__ import annotations
import asyncio
import uuid
from datetime import datetime, timezone

import whois
import dns.resolver
import httpx


def fetch_whois(domain: str) -> dict:
    """Return parsed WHOIS data for a domain."""
    try:
        w = whois.whois(domain)
        return {
            "registrar":      str(w.registrar or ""),
            "creation_date":  str(w.creation_date or ""),
            "expiration_date": str(w.expiration_date or ""),
            "org":            str(w.org or ""),
            "country":        str(w.country or ""),
            "name_servers":   list(w.name_servers or []),
            "emails":         list(w.emails) if isinstance(w.emails, (list, set))
                              else ([str(w.emails)] if w.emails else []),
            "status":         str(w.status or ""),
        }
    except Exception:
        return {}


def resolve_dns(domain: str) -> dict[str, list[str]]:
    """Resolve common DNS record types for a domain."""
    records: dict[str, list[str]] = {}
    for rtype in ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"]:
        try:
            answers    = dns.resolver.resolve(domain, rtype, lifetime=5)
            records[rtype] = [str(r) for r in answers]
        except Exception:
            records[rtype] = []
    return records


async def enumerate_subdomains(domain: str) -> list[str]:
    """Query crt.sh Certificate Transparency logs for subdomains."""
    subdomains: set[str] = set()
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://crt.sh/",
                params={"q": f"%.{domain}", "output": "json"},
            )
        for cert in resp.json():
            for name in cert.get("name_value", "").split("\n"):
                name = name.strip().lstrip("*.")
                if name.endswith(domain) and name != domain:
                    subdomains.add(name)
    except Exception:
        pass
    return sorted(subdomains)


async def reverse_ip_lookup(ip: str) -> list[str]:
    """Find all domains hosted on the same IP via HackerTarget."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://api.hackertarget.com/reverseiplookup/?q={ip}"
            )
        domains = [d.strip() for d in resp.text.split("\n") if d.strip()]
        return [d for d in domains if "." in d and "error" not in d.lower()]
    except Exception:
        return []


async def collect_all(domain: str) -> dict:
    """Run all DNS/WHOIS collection for a domain concurrently."""
    whois_data, dns_records, subdomains = await asyncio.gather(
        asyncio.to_thread(fetch_whois, domain),
        asyncio.to_thread(resolve_dns, domain),
        enumerate_subdomains(domain),
    )
    a_records = dns_records.get("A", [])
    rev_ips   = {}
    if a_records:
        rev_tasks  = [reverse_ip_lookup(ip) for ip in a_records[:3]]
        rev_results = await asyncio.gather(*rev_tasks, return_exceptions=True)
        for ip, result in zip(a_records[:3], rev_results):
            if isinstance(result, list):
                rev_ips[ip] = result

    return {
        "domain":          domain,
        "whois":           whois_data,
        "dns_records":     dns_records,
        "subdomains":      subdomains,
        "reverse_ip":      rev_ips,
        "timestamp":       datetime.now(timezone.utc).isoformat(),
    }
