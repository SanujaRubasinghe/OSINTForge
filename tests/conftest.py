from __future__ import annotations
import uuid
import pytest
from orchestrator.state import OSINTState, FindingRecord, EntityRecord


# ── Shared state fixtures ─────────────────────────────────

@pytest.fixture
def empty_state() -> OSINTState:
    return {
        "query":               "Acme Corp",
        "target_type":         "org",
        "input_image_path":    None,
        "collection_tasks":    [],
        "planner_notes":       "",
        "findings":            [],
        "entities":            [],
        "relationships":       [],
        "exif_data":           None,
        "reverse_search_urls": None,
        "visual_analysis":     None,
        "ocr_text":            None,
        "detected_logos":      None,
        "draft_report":        None,
        "critic_feedback":     None,
        "refinement_count":    0,
        "final_report":        None,
        "errors":              [],
        "agent_trace":         [],
        "status":              "planning",
    }


@pytest.fixture
def sample_finding() -> FindingRecord:
    return {
        "id":          str(uuid.uuid4()),
        "source_type": "web",
        "source_url":  "https://example.com/acme",
        "raw_text": (
            "Acme Corporation is a leading software company headquartered in "
            "San Francisco, California. CEO Jane Smith founded the company in 2010. "
            "Contact: info@acme.com"
        ),
        "title":     "About Acme Corp",
        "timestamp": "2024-01-01T00:00:00Z",
        "metadata":  {"emails": ["info@acme.com"]},
    }


@pytest.fixture
def sample_entity() -> EntityRecord:
    return {
        "id":         str(uuid.uuid4()),
        "type":       "ORG",
        "name":       "Acme Corporation",
        "aliases":    ["Acme Corp", "ACME"],
        "sources":    ["https://example.com", "https://sec.gov/acme"],
        "confidence": 0.85,
        "attributes": {"cross_referenced": True, "source_types": ["web", "sec_edgar"]},
    }


@pytest.fixture
def state_with_findings(empty_state, sample_finding) -> OSINTState:
    state = dict(empty_state)
    state["findings"] = [sample_finding]
    state["collection_tasks"] = [
        {"id": str(uuid.uuid4()), "type": "web",
         "query": "Acme Corp", "priority": 1, "status": "pending"}
    ]
    return state


@pytest.fixture
def state_with_entities(state_with_findings, sample_entity) -> OSINTState:
    state = dict(state_with_findings)
    state["entities"] = [sample_entity]
    return state
