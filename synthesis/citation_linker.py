from __future__ import annotations
import re
from orchestrator.state import ClaimRecord


SOURCE_TAG_RE = re.compile(r'\[SOURCE:\s*(https?://[^\]]+)\]')


def extract_cited_urls(text: str) -> list[str]:
    """Pull all [SOURCE: url] citations out of a text string."""
    return SOURCE_TAG_RE.findall(text)


def link_claim(claim: ClaimRecord) -> ClaimRecord:
    """
    If a claim has inline [SOURCE: url] tags, extract them and populate source_urls.
    If source_urls is already populated, keep it.
    """
    cited = extract_cited_urls(claim["text"])
    if cited:
        existing = set(claim.get("source_urls", []))
        claim["source_urls"] = list(existing | set(cited))
    return claim


def link_all_claims(claims: list[ClaimRecord]) -> list[ClaimRecord]:
    return [link_claim(c) for c in claims]


def grounding_rate(claims: list[ClaimRecord]) -> float:
    """Fraction of claims that have at least one source URL."""
    if not claims:
        return 0.0
    grounded = sum(1 for c in claims if c.get("source_urls"))
    return round(grounded / len(claims), 3)


def flag_ungrounded(claims: list[ClaimRecord]) -> list[ClaimRecord]:
    """Mark claims with no source citation as flagged for critic review."""
    for claim in claims:
        if not claim.get("source_urls"):
            claim["flagged"] = True
    return claims
