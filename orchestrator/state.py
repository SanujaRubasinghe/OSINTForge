from __future__ import annotations
from typing import TypedDict, Optional, Annotated
import operator


class CollectionTask(TypedDict):
    id: str
    type: str          # web | dns | github | news | reddit | image | email | geo | legal
    query: str
    priority: int      # 1 = high, 2 = medium, 3 = low
    status: str        # pending | running | done | failed


class FindingRecord(TypedDict):
    id: str
    source_type: str   # which collector produced this
    source_url: str
    raw_text: str
    title: str
    timestamp: str
    metadata: dict


class EntityRecord(TypedDict):
    id: str
    type: str          # PERSON | ORG | DOMAIN | IP | EMAIL | LOCATION | EVENT
    name: str
    aliases: list[str]
    sources: list[str]
    confidence: float
    attributes: dict


class RelationshipRecord(TypedDict):
    id: str
    source_entity_id: str
    target_entity_id: str
    label: str         # WORKS_AT | OWNS | HOSTED_BY | MENTIONED_WITH | ARRESTED | etc.
    evidence: str
    sources: list[str]
    confidence: float


class ClaimRecord(TypedDict):
    id: str
    text: str
    source_urls: list[str]
    confidence: float
    flagged: bool      # critic flagged as unsupported


class OSINTReport(TypedDict):
    target: str
    summary: str
    entities: list[EntityRecord]
    relationships: list[RelationshipRecord]
    claims: list[ClaimRecord]
    source_urls: list[str]
    gaps: list[str]
    confidence_overall: float
    generated_at: str


# Annotated list fields use operator.add so LangGraph can merge parallel updates
class OSINTState(TypedDict):
    # ── Input ──────────────────────────────────────────────
    query: str
    target_type: str                          # person | org | domain | topic
    input_image_path: Optional[str]

    # ── Planning ───────────────────────────────────────────
    collection_tasks: list[CollectionTask]
    planner_notes: str

    # ── Raw collection ─────────────────────────────────────
    findings: Annotated[list[FindingRecord], operator.add]

    # ── NLP layer ──────────────────────────────────────────
    entities: Annotated[list[EntityRecord], operator.add]
    relationships: Annotated[list[RelationshipRecord], operator.add]

    # ── Image intelligence (optional) ──────────────────────
    exif_data: Optional[dict]
    reverse_search_urls: Optional[list[str]]
    visual_analysis: Optional[dict]
    ocr_text: Optional[str]
    detected_logos: Optional[list[dict]]

    # ── Synthesis ──────────────────────────────────────────
    draft_report: Optional[OSINTReport]
    critic_feedback: Optional[str]
    refinement_count: int                     # max 3 before forced exit

    # ── Final output ───────────────────────────────────────
    final_report: Optional[OSINTReport]

    # ── Control flow ───────────────────────────────────────
    errors: Annotated[list[str], operator.add]
    agent_trace: Annotated[list[dict], operator.add]  # step-by-step log for UI
    status: str                               # planning | collecting | extracting | synthesising | done | failed
