from __future__ import annotations
import uuid
from datetime import datetime, timezone

from orchestrator.state import OSINTState, OSINTReport, ClaimRecord
from synthesis.citation_linker import link_all_claims, flag_ungrounded, grounding_rate
from synthesis.confidence_scorer import score_claim, score_overall


def build_report(state: OSINTState, raw_claims: list[dict]) -> OSINTReport:
    """
    Assembles the final OSINTReport from state + raw LLM claim output.
    Called by SynthesisAgent after LLM generation.
    """
    entities      = state.get("entities", [])
    relationships = state.get("relationships", [])
    findings      = state.get("findings", [])

    # Build URL → source_type lookup for confidence scoring
    url_to_type = {f["source_url"]: f["source_type"] for f in findings}
    source_urls = list({f["source_url"] for f in findings if f["source_url"]})[:50]

    # Normalise raw claims into ClaimRecord
    claims: list[ClaimRecord] = [
        {
            "id":          str(uuid.uuid4()),
            "text":        c.get("text", ""),
            "source_urls": c.get("source_urls", []),
            "confidence":  float(c.get("confidence", 0.5)),
            "flagged":     False,
        }
        for c in raw_claims
        if c.get("text")
    ]

    # Link inline citations and flag ungrounded claims
    claims = link_all_claims(claims)
    claims = flag_ungrounded(claims)

    # Re-score confidence using source trust model
    for claim in claims:
        claim["confidence"] = score_claim(claim, url_to_type)

    overall_conf = score_overall(claims, entities)

    rate = grounding_rate(claims)

    report: OSINTReport = {
        "target":             state["query"],
        "summary":            "",        # filled in by SynthesisAgent
        "entities":           entities,
        "relationships":      relationships,
        "claims":             claims,
        "source_urls":        source_urls,
        "gaps":               [],        # filled in by SynthesisAgent
        "confidence_overall": overall_conf,
        "generated_at":       datetime.now(timezone.utc).isoformat(),
    }

    return report
