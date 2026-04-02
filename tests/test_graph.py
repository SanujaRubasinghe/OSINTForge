from __future__ import annotations
import uuid
import pytest
import tempfile
import os

from knowledge_graph.graph_store import GraphStore
from orchestrator.state import EntityRecord, RelationshipRecord


def _entity(name: str, etype: str = "ORG", confidence: float = 0.8) -> EntityRecord:
    return {
        "id":         str(uuid.uuid4()),
        "type":       etype,
        "name":       name,
        "aliases":    [],
        "sources":    ["https://example.com"],
        "confidence": confidence,
        "attributes": {"cross_referenced": False},
    }


def _relationship(src_id: str, tgt_id: str, label: str = "WORKS_AT") -> RelationshipRecord:
    return {
        "id":               str(uuid.uuid4()),
        "source_entity_id": src_id,
        "target_entity_id": tgt_id,
        "label":            label,
        "evidence":         "Test evidence sentence.",
        "sources":          ["https://example.com"],
        "confidence":       0.75,
    }


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_kuzu")
        s = GraphStore(path=db_path)
        yield s


class TestGraphStore:
    def test_upsert_and_query_entity(self, store):
        ent = _entity("Acme Corp")
        store.upsert_entity(ent)
        result = store.find_cross_referenced(min_sources=1)
        names = [r["e.name"] for r in result]
        assert "Acme Corp" in names

    def test_upsert_duplicate_does_not_error(self, store):
        ent = _entity("Acme Corp")
        store.upsert_entity(ent)
        store.upsert_entity(ent)  # should not raise

    def test_upsert_relationship(self, store):
        person = _entity("Jane Smith", etype="PERSON")
        org    = _entity("Acme Corp", etype="ORG")
        store.upsert_entity(person)
        store.upsert_entity(org)
        rel = _relationship(person["id"], org["id"], label="WORKS_AT")
        store.upsert_relationship(rel)  # should not raise

    def test_find_cross_referenced_filters_by_confidence(self, store):
        high = _entity("HighConf Corp", confidence=0.9)
        low  = _entity("LowConf Corp",  confidence=0.2)
        store.upsert_entity(high)
        store.upsert_entity(low)
        result = store.find_cross_referenced(min_sources=1)
        names  = [r["e.name"] for r in result]
        assert "HighConf Corp" in names
        assert "LowConf Corp" not in names

    def test_clear_removes_all_data(self, store):
        ent = _entity("Temp Entity")
        store.upsert_entity(ent)
        store.clear()
        result = store.find_cross_referenced(min_sources=1)
        assert len(result) == 0

    def test_get_neighbours_empty_for_unknown_id(self, store):
        result = store.get_neighbours("nonexistent-id-1234")
        assert isinstance(result, list)
