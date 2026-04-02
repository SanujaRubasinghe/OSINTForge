from __future__ import annotations
import uuid
import pytest

from synthesis.citation_linker import (
    extract_cited_urls,
    link_all_claims,
    flag_ungrounded,
    grounding_rate,
)
from synthesis.confidence_scorer import score_claim, score_overall
from synthesis.report_builder import build_report


def _claim(text: str, urls=None, confidence=0.6):
    return {
        "id":          str(uuid.uuid4()),
        "text":        text,
        "source_urls": urls or [],
        "confidence":  confidence,
        "flagged":     False,
    }


def _entity(name: str, conf=0.8, cross_ref=False, sources=None):
    return {
        "id":         str(uuid.uuid4()),
        "type":       "ORG",
        "name":       name,
        "aliases":    [],
        "sources":    sources or ["https://a.com"],
        "confidence": conf,
        "attributes": {"cross_referenced": cross_ref},
    }


def _finding(url: str, source_type: str = "web"):
    return {
        "id":          str(uuid.uuid4()),
        "source_type": source_type,
        "source_url":  url,
        "raw_text":    f"Raw content from {url}",
        "title":       "Test finding",
        "timestamp":   "2024-01-01T00:00:00Z",
        "metadata":    {},
    }


class TestCitationLinker:
    def test_inline_source_tag_extracted(self):
        text = "Acme Corp was founded in 2010 [SOURCE: https://sec.gov/filing]."
        assert extract_cited_urls(text) == ["https://sec.gov/filing"]

    def test_no_tags_returns_empty(self):
        assert extract_cited_urls("No citations here.") == []

    def test_link_all_claims_populates_urls(self):
        claims = [_claim("Founded 2010 [SOURCE: https://sec.gov]")]
        linked = link_all_claims(claims)
        assert "https://sec.gov" in linked[0]["source_urls"]

    def test_flag_ungrounded_sets_flag(self):
        claims = [
            _claim("Has source", urls=["https://a.com"]),
            _claim("No source"),
        ]
        flagged = flag_ungrounded(claims)
        assert flagged[0]["flagged"] is False
        assert flagged[1]["flagged"] is True

    def test_grounding_rate_calculation(self):
        claims = [
            _claim("Grounded", urls=["https://a.com"]),
            _claim("Grounded 2", urls=["https://b.com"]),
            _claim("Not grounded"),
        ]
        rate = grounding_rate(claims)
        assert abs(rate - 0.667) < 0.01

    def test_grounding_rate_empty_list(self):
        assert grounding_rate([]) == 0.0


class TestConfidenceScorer:
    def test_empty_sources_very_low(self):
        claim = _claim("Unsupported claim", urls=[])
        assert score_claim(claim, {}) <= 0.15

    def test_high_trust_source_boosts_score(self):
        claim = _claim("SEC filing", urls=["https://sec.gov/filing"])
        score = score_claim(claim, {"https://sec.gov/filing": "sec_edgar"})
        assert score >= 0.60

    def test_low_trust_source_lower_score(self):
        claim_reddit = _claim("Reddit claim", urls=["https://reddit.com/r/test"])
        claim_sec    = _claim("SEC claim",    urls=["https://sec.gov/filing"])
        url_map_r = {"https://reddit.com/r/test": "reddit"}
        url_map_s = {"https://sec.gov/filing":    "sec_edgar"}
        assert score_claim(claim_reddit, url_map_r) < score_claim(claim_sec, url_map_s)

    def test_more_sources_higher_confidence(self):
        one   = _claim("One",   urls=["https://a.com"])
        three = _claim("Three", urls=["https://a.com", "https://b.com", "https://c.com"])
        url_map = {"https://a.com": "web", "https://b.com": "newsapi", "https://c.com": "gdelt_news"}
        assert score_claim(three, url_map) > score_claim(one, {"https://a.com": "web"})

    def test_overall_score_zero_without_claims(self):
        assert score_overall([], []) == 0.0

    def test_overall_score_bounded(self):
        entities = [_entity("Acme", conf=0.95, cross_ref=True)]
        claims   = [_claim("Well sourced", urls=["https://a.com"], confidence=0.9)]
        score    = score_overall(claims, entities)
        assert 0.0 <= score <= 1.0

    def test_cross_referenced_entities_improve_overall(self):
        entities_no  = [_entity("A", conf=0.8, cross_ref=False)]
        entities_yes = [_entity("A", conf=0.8, cross_ref=True)]
        claims = [_claim("Claim", urls=["https://a.com"], confidence=0.8)]
        assert score_overall(claims, entities_yes) >= score_overall(claims, entities_no)


class TestReportBuilder:
    def _make_state(self):
        return {
            "query":         "Acme Corp",
            "target_type":   "org",
            "collection_tasks": [],
            "findings":      [_finding("https://sec.gov/acme", "sec_edgar"),
                              _finding("https://news.com/acme", "newsapi")],
            "entities":      [_entity("Acme Corp", conf=0.85, cross_ref=True)],
            "relationships": [],
            "input_image_path": None,
            "exif_data":     None,
            "reverse_search_urls": None,
            "visual_analysis": None,
            "ocr_text":      None,
            "detected_logos": None,
            "draft_report":  None,
            "critic_feedback": None,
            "refinement_count": 0,
            "final_report":  None,
            "errors":        [],
            "agent_trace":   [],
            "status":        "synthesising",
            "planner_notes": "",
        }

    def test_report_has_required_fields(self):
        state = self._make_state()
        raw_claims = [
            {"text": "Acme Corp is a software company [SOURCE: https://sec.gov/acme]",
             "source_urls": ["https://sec.gov/acme"], "confidence": 0.85},
        ]
        report = build_report(state, raw_claims)
        assert report["target"] == "Acme Corp"
        assert "entities" in report
        assert "claims" in report
        assert "source_urls" in report
        assert "confidence_overall" in report
        assert 0.0 <= report["confidence_overall"] <= 1.0

    def test_ungrounded_claims_are_flagged(self):
        state = self._make_state()
        raw_claims = [
            {"text": "No citation here at all", "source_urls": [], "confidence": 0.5},
        ]
        report = build_report(state, raw_claims)
        assert all(c["flagged"] for c in report["claims"] if not c["source_urls"])

    def test_source_urls_deduped(self):
        state = self._make_state()
        report = build_report(state, [])
        assert len(report["source_urls"]) == len(set(report["source_urls"]))

    def test_empty_claims_list_ok(self):
        state  = self._make_state()
        report = build_report(state, [])
        assert report["claims"] == []
        assert report["confidence_overall"] == 0.0
