from __future__ import annotations
import kuzu
import os
from orchestrator.state import EntityRecord, RelationshipRecord


DB_PATH = os.getenv("KUZU_PATH", "./data/kuzu_graph")


class GraphStore:
    def __init__(self, path: str = DB_PATH):
        os.makedirs(path, exist_ok=True)
        self.db   = kuzu.Database(path)
        self.conn = kuzu.Connection(self.db)
        self._setup_schema()

    def _setup_schema(self):
        self.conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Entity (
                id         STRING PRIMARY KEY,
                type       STRING,
                name       STRING,
                confidence DOUBLE,
                sources    STRING,
                attributes STRING
            )
        """)
        self.conn.execute("""
            CREATE REL TABLE IF NOT EXISTS Relationship (
                FROM Entity TO Entity,
                id         STRING,
                label      STRING,
                confidence DOUBLE,
                evidence   STRING,
                sources    STRING
            )
        """)

    def upsert_entity(self, entity: EntityRecord):
        import json
        existing = self.conn.execute(
            "MATCH (e:Entity {id: $id}) RETURN e.id", {"id": entity["id"]}
        ).get_as_df()

        if existing.empty:
            self.conn.execute(
                """
                CREATE (e:Entity {
                    id:         $id,
                    type:       $type,
                    name:       $name,
                    confidence: $confidence,
                    sources:    $sources,
                    attributes: $attributes
                })
                """,
                {
                    "id":         entity["id"],
                    "type":       entity["type"],
                    "name":       entity["name"],
                    "confidence": entity["confidence"],
                    "sources":    json.dumps(entity["sources"]),
                    "attributes": json.dumps(entity.get("attributes", {})),
                },
            )
        else:
            self.conn.execute(
                """
                MATCH (e:Entity {id: $id})
                SET e.confidence = $confidence,
                    e.sources    = $sources
                """,
                {
                    "id":         entity["id"],
                    "confidence": entity["confidence"],
                    "sources":    json.dumps(entity["sources"]),
                },
            )

    def upsert_relationship(self, rel: RelationshipRecord):
        import json
        self.conn.execute(
            """
            MATCH (a:Entity {id: $src}), (b:Entity {id: $tgt})
            CREATE (a)-[:Relationship {
                id:         $id,
                label:      $label,
                confidence: $confidence,
                evidence:   $evidence,
                sources:    $sources
            }]->(b)
            """,
            {
                "src":        rel["source_entity_id"],
                "tgt":        rel["target_entity_id"],
                "id":         rel["id"],
                "label":      rel["label"],
                "confidence": rel["confidence"],
                "evidence":   rel.get("evidence", "")[:300],
                "sources":    json.dumps(rel.get("sources", [])),
            },
        )

    def get_neighbours(self, entity_id: str, hops: int = 1) -> dict:
        result = self.conn.execute(
            """
            MATCH (a:Entity {id: $id})-[r:Relationship*1..2]->(b:Entity)
            RETURN a.name, r.label, b.name, b.type, b.confidence
            LIMIT 50
            """,
            {"id": entity_id},
        ).get_as_df()
        return result.to_dict(orient="records")

    def find_cross_referenced(self, min_sources: int = 2) -> list[dict]:
        """Return entities confirmed by at least N independent sources."""
        result = self.conn.execute(
            """
            MATCH (e:Entity)
            WHERE e.confidence >= 0.7
            RETURN e.id, e.type, e.name, e.confidence, e.sources
            ORDER BY e.confidence DESC
            LIMIT 100
            """,
        ).get_as_df()
        return result.to_dict(orient="records")

    def clear(self):
        self.conn.execute("MATCH (e:Entity) DELETE e")
        self.conn.execute("MATCH ()-[r:Relationship]->() DELETE r")
