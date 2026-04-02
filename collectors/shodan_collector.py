from __future__ import annotations
import os


def search_org(org_name: str) -> list[dict]:
    """
    Search Shodan for all hosts associated with an organisation.
    Returns list of host records with open ports, services, and CVEs.
    Requires SHODAN_API_KEY env var.
    """
    api_key = os.getenv("SHODAN_API_KEY", "")
    if not api_key:
        return []
    try:
        import shodan
        api     = shodan.Shodan(api_key)
        results = api.search(f'org:"{org_name}"')
        findings = []
        for match in results.get("matches", [])[:50]:
            findings.append({
                "ip":        match["ip_str"],
                "port":      match["port"],
                "transport": match.get("transport"),
                "product":   match.get("product"),
                "version":   match.get("version"),
                "cpe":       match.get("cpe", []),
                "vulns":     list(match.get("vulns", {}).keys()),
                "banner":    match.get("data", "")[:300],
                "hostnames": match.get("hostnames", []),
                "location": {
                    "country": match.get("location", {}).get("country_name"),
                    "city":    match.get("location", {}).get("city"),
                },
            })
        return findings
    except Exception:
        return []


def get_host(ip: str) -> dict:
    """Detailed host info including historical scan data."""
    api_key = os.getenv("SHODAN_API_KEY", "")
    if not api_key:
        return {}
    try:
        import shodan
        api  = shodan.Shodan(api_key)
        host = api.host(ip)
        return {
            "ip":        host.get("ip_str"),
            "org":       host.get("org"),
            "os":        host.get("os"),
            "ports":     host.get("ports", []),
            "hostnames": host.get("hostnames", []),
            "vulns":     list(host.get("vulns", {}).keys()),
        }
    except Exception:
        return {}
