from __future__ import annotations
import pytest
from synthesis.citation_linker import (
    extract_cited_urls,
    link_claim,
    grounding_rate,
    flag_ungrounded,
)
from synthesis.confidence_scorer import score_claim, score_overall


def _make_claim(text: str, source_urls=None, confidence=0.5, flagged=False):
    import uuid
    return {
        "id":          str(uuid.uuid4()),
        "text":        text,
        "source_urls": source_urls or [],
        "confidence":  confidence,
        "flagged":     flagged,
    }


def _make_entity(confidence=0.8, cross_ref=False, sources=None):
    import uuid
    return {
        "id":         str(uuid.uuid4()),
        "type":       "ORG",
        "name":       "Acme Corp",
        "aliases":    [],
        "sources":    sources or ["https://a.com"],
        "confidence": confidence,
        "attributes": {"cross_referenced": cross_ref},
    }


# ── Citation linker ──────────────────────────────────────
class TestCitationLinker:
    def test_extract_cited_urls(self):
        text = "Acme Corp was founded in 2010 [SOURCE: https://sec.gov/acme] by John Doe."
        urls = extract_cited_urls(text)
        assert urls == ["https://sec.gov/acme"]

    def test_extract_multiple_urls(self):
        text = "Fact one [SOURCE: https://a.com] and fact two [SOURCE: https://b.com]."
        urls = extract_cited_urls(text)
        assert len(urls) == 2

    def test_link_claim_populates_source_urls(self):
        claim = _make_claim("CEO is John Doe [SOURCE: https://linkedin.com/in/johndoe]")
        linked = link_claim(claim)
        assert "https://linkedin.com/in/johndoe" in linked["source_urls"]

    def test_grounding_rate_all_grounded(self):
        claims = [
            _make_claim("Claim A", source_urls=["https://a.com"]),
            _make_claim("Claim B", source_urls=["https://b.com"]),
        ]
        assert grounding_rate(claims) == 1.0

    def test_grounding_rate_partial(self):
        claims = [
            _make_claim("Claim A", source_urls=["https://a.com"]),
            _make_claim("Claim B ungrounded"),
        ]
        assert grounding_rate(claims) == 0.5

    def test_flag_ungrounded_marks_claims(self):
        claims = [
            _make_claim("Has source", source_urls=["https://a.com"]),
            _make_claim("No source"),
        ]
        flagged = flag_ungrounded(claims)
        assert flagged[0]["flagged"] is False
        assert flagged[1]["flagged"] is True


# ── Confidence scorer ────────────────────────────────────
class TestConfidenceScorer:
    def test_ungrounded_claim_low_confidence(self):
        claim = _make_claim("Ungrounded claim", source_urls=[])
        score = score_claim(claim, {})
        assert score <= 0.15

    def test_authoritative_source_boosts_confidence(self):
        claim = _make_claim("SEC filing claim", source_urls=["https://sec.gov/filing"])
        score = score_claim(claim, {"https://sec.gov/filing": "sec_edgar"})
        assert score >= 0.6

    def test_multiple_sources_increase_confidence(self):
        claim = _make_claim(
            "Multi-source claim",
            source_urls=["https://a.com", "https://b.com", "https://c.com"],
        )
        url_map = {
            "https://a.com": "web",
            "https://b.com": "newsapi",
            "https://c.com": "gdelt_news",
        }
        score = score_claim(claim, url_map)
        single = score_claim(_make_claim("Single", source_urls=["https://a.com"]), {"https://a.com": "web"})
        assert score > single

    def test_overall_score_empty_returns_zero(self):
        assert score_overall([], []) == 0.0

    def test_overall_score_with_cross_referenced_entities(self):
        entities = [_make_entity(confidence=0.9, cross_ref=True, sources=["a", "b"])]
        claims   = [_make_claim("Claim", source_urls=["https://a.com"], confidence=0.8)]
        score    = score_overall(claims, entities)
        assert 0.0 < score <= 1.0
