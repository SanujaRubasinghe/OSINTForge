from __future__ import annotations
import json
import uuid

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

from orchestrator.state import RelationshipRecord

VALID_RELATIONS = {
    "WORKS_AT", "FOUNDED", "OWNS", "ACQUIRED", "PARTNERS_WITH",
    "LOCATED_IN", "HOSTED_BY", "MENTIONED_WITH", "ARRESTED",
    "SUED", "EMPLOYED_BY", "INVESTED_IN", "LEADS",
}

SYSTEM_PROMPT = """Extract (subject, relation, object) triples from the text.

subject and object must be named entities (person, org, domain, email, location).
relation must be one of: WORKS_AT, FOUNDED, OWNS, ACQUIRED, PARTNERS_WITH,
LOCATED_IN, HOSTED_BY, MENTIONED_WITH, ARRESTED, SUED, EMPLOYED_BY, INVESTED_IN, LEADS

Return ONLY a JSON array of objects:
[{"subject": "...", "relation": "...", "object": "...", "confidence": 0.0-1.0}]

If no clear triples exist, return [].
Maximum 10 triples per call. Do not include uncertain inferences."""

_llm = None


def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatOllama(model="qwen2.5:3b", temperature=0, format="json")
    return _llm


def extract_relations(text: str, source_urls: list[str]) -> list[RelationshipRecord]:
    try:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=text[:2000]),
        ]
        response = get_llm().invoke(messages)
        triples  = json.loads(response.content)
        if not isinstance(triples, list):
            return []

        relationships = []
        for t in triples[:10]:
            rel_label = t.get("relation", "MENTIONED_WITH").upper()
            if rel_label not in VALID_RELATIONS:
                rel_label = "MENTIONED_WITH"
            relationships.append({
                "id":               str(uuid.uuid4()),
                "source_entity_id": str(t.get("subject", "")),
                "target_entity_id": str(t.get("object", "")),
                "label":            rel_label,
                "evidence":         text[:200],
                "sources":          source_urls,
                "confidence":       float(t.get("confidence", 0.55)),
            })
        return relationships
    except Exception:
        return []
