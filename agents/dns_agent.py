from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import dns.resolver
import httpx
import whois

from orchestrator.state import FindingRecord, OSINTState


class DNSAgent:
    def run(self, state: OSINTState) -> dict:
        tasks = [t for t in state["collection_tasks"] if t["type"] == "dns" and t["status"] == "pending"]
        if not tasks:
            return {"agent_trace": [{"agent": "dns_agent", "action": "no_tasks"}]}

        findings = []
        for task in tasks:
            domain = task["query"].strip().lower()
            results = asyncio.run(self._collect_all(domain))
            findings.extend(results)

        return {
            "findings": findings,
            "agent_trace": [{
                "agent":     "dns_agent",
                "action":    "collected",
                "count":     len(findings),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

    async def _collect_all(self, domain: str) -> list[FindingRecord]:
        results = await asyncio.gather(
            asyncio.to_thread(self._whois, domain),
            asyncio.to_thread(self._dns_records, domain),
            self._subdomains_crtsh(domain),
            return_exceptions=True,
        )
        findings = []
        for r in results:
            if isinstance(r, dict):
                findings.append(r)
            elif isinstance(r, list):
                findings.extend([x for x in r if isinstance(x, dict)])
        return findings

    def _whois(self, domain: str) -> FindingRecord:
        try:
            w = whois.whois(domain)
            text = (
                f"Registrar: {w.registrar}\n"
                f"Created: {w.creation_date}\n"
                f"Expires: {w.expiration_date}\n"
                f"Org: {w.org}\n"
                f"Country: {w.country}\n"
                f"Emails: {w.emails}\n"
                f"Name Servers: {w.name_servers}\n"
                f"Status: {w.status}"
            )
            return {
                "id":          str(uuid.uuid4()),
                "source_type": "whois",
                "source_url":  f"whois://{domain}",
                "raw_text":    text,
                "title":       f"WHOIS record for {domain}",
                "timestamp":   datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "registrar":   str(w.registrar),
                    "created":     str(w.creation_date),
                    "org":         str(w.org),
                    "emails":      list(w.emails) if isinstance(w.emails, (list, set)) else [str(w.emails)] if w.emails else [],
                    "name_servers": list(w.name_servers) if w.name_servers else [],
                },
            }
        except Exception as e:
            return None

    def _dns_records(self, domain: str) -> FindingRecord:
        records = {}
        for rtype in ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"]:
            try:
                answers = dns.resolver.resolve(domain, rtype, lifetime=5)
                records[rtype] = [str(r) for r in answers]
            except Exception:
                records[rtype] = []

        text = "\n".join(f"{k}: {', '.join(v)}" for k, v in records.items() if v)
        return {
            "id":          str(uuid.uuid4()),
            "source_type": "dns",
            "source_url":  f"dns://{domain}",
            "raw_text":    text,
            "title":       f"DNS records for {domain}",
            "timestamp":   datetime.now(timezone.utc).isoformat(),
            "metadata":    {"records": records},
        }

    async def _subdomains_crtsh(self, domain: str) -> list[FindingRecord]:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    "https://crt.sh/",
                    params={"q": f"%.{domain}", "output": "json"},
                )
            certs = resp.json()
            subdomains = set()
            internal_signals = []
            internal_keywords = ["vpn", "internal", "corp", "dev", "staging", "test",
                                  "jenkins", "jira", "confluence", "gitlab", "admin", "api"]

            for cert in certs:
                for name in cert.get("name_value", "").split("\n"):
                    name = name.strip().lstrip("*.")
                    if name.endswith(domain):
                        subdomains.add(name)
                        if any(k in name.lower() for k in internal_keywords):
                            internal_signals.append(name)

            text = (
                f"Subdomains discovered via CT logs: {len(subdomains)}\n"
                + "\n".join(sorted(subdomains))
                + (f"\n\nPotential internal hostnames: {', '.join(internal_signals)}" if internal_signals else "")
            )
            return [{
                "id":          str(uuid.uuid4()),
                "source_type": "certificate_transparency",
                "source_url":  f"https://crt.sh/?q=%.{domain}",
                "raw_text":    text,
                "title":       f"Certificate Transparency subdomains for {domain}",
                "timestamp":   datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "subdomain_count":  len(subdomains),
                    "subdomains":       list(sorted(subdomains))[:50],
                    "internal_signals": internal_signals,
                },
            }]
        except Exception:
            return []
