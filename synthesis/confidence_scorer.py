from __future__ import annotations
from orchestrator.state import ClaimRecord, EntityRecord


SOURCE_TRUST = {
    "sec_edgar":              0.95,
    "companies_house":        0.95,
    "whois":                  0.85,
    "certificate_transparency": 0.80,
    "github_org":             0.75,
    "github_user":            0.70,
    "gdelt_news":             0.60,
    "newsapi":                0.60,
    "rss":                    0.55,
    "web":                    0.50,
    "reddit":                 0.40,
    "paste_collector":        0.35,
    "github_secret_scan":     0.80,
    "image_intel":            0.65,
}


def score_claim(claim: ClaimRecord, findings_by_url: dict[str, str]) -> float:
    """
    Confidence = base from source count + trust boost from source type diversity.
    """
    urls         = claim.get("source_urls", [])
    source_types = list({findings_by_url.get(u, "web") for u in urls})

    if not urls:
        return 0.10   # ungrounded claim — very low confidence

    base  = min(0.5 + 0.08 * len(urls), 0.75)
    boost = max((SOURCE_TRUST.get(st, 0.45) for st in source_types), default=0.45)
    return round(min(1.0, base * boost + 0.05 * len(source_types)), 3)


def score_overall(
    claims:   list[ClaimRecord],
    entities: list[EntityRecord],
) -> float:
    if not claims:
        return 0.0

    grounded   = [c for c in claims if c.get("source_urls")]
    grounding  = len(grounded) / len(claims)

    avg_entity_conf = (
        sum(e["confidence"] for e in entities) / len(entities) if entities else 0.5
    )
    avg_claim_conf  = (
        sum(c["confidence"] for c in claims) / len(claims)
    )
    cross_ref_ratio = (
        sum(1 for e in entities if e.get("attributes", {}).get("cross_referenced", False))
        / max(len(entities), 1)
    )

    overall = (
        0.35 * grounding
        + 0.30 * avg_claim_conf
        + 0.20 * avg_entity_conf
        + 0.15 * cross_ref_ratio
    )
    return round(min(1.0, overall), 3)
