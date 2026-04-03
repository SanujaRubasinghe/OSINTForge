from __future__ import annotations
import uuid
import json
import os
from datetime import datetime, timezone

import spacy
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

from orchestrator.state import OSINTState, EntityRecord, RelationshipRecord, FindingRecord


RELATION_PROMPT = """You are an OSINT relation extraction agent.
Given a text passage, extract all (subject, relation, object) triples.

Subject and object must be named entities (person, org, domain, location, email).
Relation must be one of: WORKS_AT, FOUNDED, OWNS, ACQUIRED, PARTNERS_WITH,
LOCATED_IN, HOSTED_BY, MENTIONED_WITH, ARRESTED, SUED, EMPLOYED_BY, INVESTED_IN, LEADS

Return ONLY a JSON array. Each item: {"subject": "...", "relation": "...", "object": "...", "confidence": 0.0-1.0}
If no clear triples, return [].
Limit to 10 most confident triples.

Text:
"""


class EntityExtractorAgent:
    BATCH_SIZE = 5     # findings per LLM call to stay within context window

    def __init__(self):
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.nlp = spacy.load("en_core_web_trf")
        self.llm = ChatOllama(model="qwen2.5:3b", base_url=ollama_url, temperature=0, format="json")

    def run(self, state: OSINTState) -> dict:
        findings = state.get("findings", [])
        if not findings:
            return {"agent_trace": [{"agent": "entity_extractor", "action": "no_findings"}]}

        all_entities:      list[EntityRecord]      = []
        all_relationships: list[RelationshipRecord] = []

        entity_registry: dict[str, EntityRecord] = {}

        for finding in findings:
            text = finding["raw_text"][:3000]  # cap per finding

            # ── spaCy NER ──────────────────────────────────
            spacy_entities = self._spacy_ner(text, finding)
            for ent in spacy_entities:
                key = f"{ent['type']}:{ent['name'].lower()}"
                if key in entity_registry:
                    # Merge: add source, boost confidence
                    existing = entity_registry[key]
                    if finding["source_url"] not in existing["sources"]:
                        existing["sources"].append(finding["source_url"])
                        existing["confidence"] = min(1.0, existing["confidence"] + 0.1)
                else:
                    entity_registry[key] = ent
                    all_entities.append(ent)

        # Build name → id lookup so relations can be resolved to real UUIDs
        name_to_id: dict[str, str] = {
            ent["name"].lower().strip(): ent["id"]
            for ent in entity_registry.values()
        }

        # ── LLM relation extraction (batched) ─────────────
        for i in range(0, len(findings), self.BATCH_SIZE):
            batch = findings[i:i + self.BATCH_SIZE]
            combined_text = "\n\n---\n\n".join(f["raw_text"][:500] for f in batch)
            rels = self._extract_relations(combined_text, batch, name_to_id)
            all_relationships.extend(rels)

        return {
            "entities":      all_entities,
            "relationships": all_relationships,
            "agent_trace": [{
                "agent":             "entity_extractor",
                "action":            "extracted",
                "entity_count":      len(all_entities),
                "relationship_count": len(all_relationships),
                "finding_count":     len(findings),
                "timestamp":         datetime.now(timezone.utc).isoformat(),
            }],
        }

    def _spacy_ner(self, text: str, finding: FindingRecord) -> list[EntityRecord]:
        doc = self.nlp(text)
        entities = []
        TYPE_MAP = {
            "PERSON": "PERSON", "ORG": "ORG", "GPE": "LOCATION",
            "LOC": "LOCATION", "NORP": "ORG", "FAC": "LOCATION",
            "PRODUCT": "ORG", "EVENT": "EVENT",
        }
        for ent in doc.ents:
            mapped = TYPE_MAP.get(ent.label_)
            if not mapped:
                continue
            entities.append({
                "id":         str(uuid.uuid4()),
                "type":       mapped,
                "name":       ent.text.strip(),
                "aliases":    [],
                "sources":    [finding["source_url"]],
                "confidence": 0.7,
                "attributes": {"spacy_label": ent.label_},
            })
        # Also extract emails from metadata
        for email in finding.get("metadata", {}).get("emails", []):
            entities.append({
                "id":         str(uuid.uuid4()),
                "type":       "EMAIL",
                "name":       email,
                "aliases":    [],
                "sources":    [finding["source_url"]],
                "confidence": 0.95,
                "attributes": {},
            })
        return entities

    def _extract_relations(self,
                            text: str,
                            findings: list[FindingRecord],
                            name_to_id: dict[str, str]) -> list[RelationshipRecord]:
        try:
            messages = [
                SystemMessage(content=RELATION_PROMPT + text[:2000]),
                HumanMessage(content="Extract triples from the above text."),
            ]
            response = self.llm.invoke(messages)
            raw = json.loads(response.content)

            # Model may wrap the array: {"triples": [...]} or {"relations": [...]}
            if isinstance(raw, dict):
                raw = next((v for v in raw.values() if isinstance(v, list)), [])
            if not isinstance(raw, list):
                return []

            source_urls = [f["source_url"] for f in findings]
            relationships = []
            for t in raw[:10]:
                subj = (t.get("subject") or "").lower().strip()
                obj  = (t.get("object")  or "").lower().strip()
                if not subj or not obj:
                    continue

                # Resolve names to UUIDs — try exact match first, then partial
                src_id = name_to_id.get(subj) or self._fuzzy_resolve(subj, name_to_id)
                tgt_id = name_to_id.get(obj)  or self._fuzzy_resolve(obj,  name_to_id)
                if not src_id or not tgt_id or src_id == tgt_id:
                    continue

                relationships.append({
                    "id":               str(uuid.uuid4()),
                    "source_entity_id": src_id,
                    "target_entity_id": tgt_id,
                    "label":            t.get("relation", "MENTIONED_WITH"),
                    "evidence":         text[:200],
                    "sources":          source_urls,
                    "confidence":       float(t.get("confidence", 0.6)),
                })
            return relationships
        except Exception:
            return []

    @staticmethod
    def _fuzzy_resolve(name: str, name_to_id: dict[str, str]) -> str | None:
        """Return entity ID if name is a substring of a known entity or vice-versa."""
        for known, eid in name_to_id.items():
            if name in known or known in name:
                return eid
        return None
