from __future__ import annotations
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class EntityType(str, Enum):
    PERSON   = "PERSON"
    ORG      = "ORG"
    DOMAIN   = "DOMAIN"
    IP       = "IP"
    EMAIL    = "EMAIL"
    LOCATION = "LOCATION"
    EVENT    = "EVENT"


class RelationLabel(str, Enum):
    WORKS_AT       = "WORKS_AT"
    FOUNDED        = "FOUNDED"
    OWNS           = "OWNS"
    ACQUIRED       = "ACQUIRED"
    PARTNERS_WITH  = "PARTNERS_WITH"
    LOCATED_IN     = "LOCATED_IN"
    HOSTED_BY      = "HOSTED_BY"
    MENTIONED_WITH = "MENTIONED_WITH"
    ARRESTED       = "ARRESTED"
    SUED           = "SUED"
    EMPLOYED_BY    = "EMPLOYED_BY"
    INVESTED_IN    = "INVESTED_IN"
    LEADS          = "LEADS"


class EntityModel(BaseModel):
    id:          str         = Field(default_factory=lambda: str(uuid.uuid4()))
    type:        EntityType
    name:        str
    aliases:     list[str]   = Field(default_factory=list)
    sources:     list[str]   = Field(default_factory=list)
    confidence:  float       = Field(ge=0.0, le=1.0, default=0.5)
    attributes:  dict        = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class RelationshipModel(BaseModel):
    id:               str          = Field(default_factory=lambda: str(uuid.uuid4()))
    source_entity_id: str
    target_entity_id: str
    label:            RelationLabel
    evidence:         str          = ""
    sources:          list[str]    = Field(default_factory=list)
    confidence:       float        = Field(ge=0.0, le=1.0, default=0.5)
    timestamp:        Optional[str] = None

    class Config:
        use_enum_values = True


# ── Kuzu DDL strings (used by GraphStore._setup_schema) ─────────────────────
ENTITY_NODE_DDL = """
CREATE NODE TABLE IF NOT EXISTS Entity (
    id         STRING PRIMARY KEY,
    type       STRING,
    name       STRING,
    confidence DOUBLE,
    sources    STRING,
    attributes STRING
)
"""

RELATIONSHIP_REL_DDL = """
CREATE REL TABLE IF NOT EXISTS Relationship (
    FROM Entity TO Entity,
    id         STRING,
    label      STRING,
    confidence DOUBLE,
    evidence   STRING,
    sources    STRING
)
"""
