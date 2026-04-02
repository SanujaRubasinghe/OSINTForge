from __future__ import annotations
import spacy
from orchestrator.state import EntityRecord, FindingRecord
import uuid

_nlp = None

TYPE_MAP = {
    "PERSON":  "PERSON",
    "ORG":     "ORG",
    "GPE":     "LOCATION",
    "LOC":     "LOCATION",
    "NORP":    "ORG",
    "FAC":     "LOCATION",
    "PRODUCT": "ORG",
    "EVENT":   "EVENT",
}


def get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_trf")
    return _nlp


def extract_entities(text: str, source_url: str = "") -> list[EntityRecord]:
    nlp = get_nlp()
    doc = nlp(text[:5000])
    entities = []
    for ent in doc.ents:
        mapped = TYPE_MAP.get(ent.label_)
        if not mapped:
            continue
        entities.append({
            "id":         str(uuid.uuid4()),
            "type":       mapped,
            "name":       ent.text.strip(),
            "aliases":    [],
            "sources":    [source_url] if source_url else [],
            "confidence": 0.70,
            "attributes": {"spacy_label": ent.label_},
        })
    return entities


def extract_entities_from_findings(findings: list[FindingRecord]) -> list[EntityRecord]:
    all_entities = []
    for f in findings:
        ents = extract_entities(f["raw_text"], f["source_url"])
        all_entities.extend(ents)
    return all_entities
