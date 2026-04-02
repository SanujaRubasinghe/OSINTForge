from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query:       str               = Field(..., description="Target entity name or topic")
    target_type: str               = Field("org", description="person | org | domain | topic")
    image_path:  Optional[str]     = Field(None, description="Optional uploaded image path")


class TaskStatus(BaseModel):
    task_id:    str
    status:     str                # pending | running | done | failed
    created_at: datetime
    query:      str


class EntityOut(BaseModel):
    id:         str
    type:       str
    name:       str
    aliases:    list[str]
    sources:    list[str]
    confidence: float
    attributes: dict


class RelationshipOut(BaseModel):
    id:               str
    source_entity_id: str
    target_entity_id: str
    label:            str
    evidence:         str
    confidence:       float


class ClaimOut(BaseModel):
    id:          str
    text:        str
    source_urls: list[str]
    confidence:  float
    flagged:     bool


class OSINTReportOut(BaseModel):
    target:             str
    summary:            str
    entities:           list[EntityOut]
    relationships:      list[RelationshipOut]
    claims:             list[ClaimOut]
    source_urls:        list[str]
    gaps:               list[str]
    confidence_overall: float
    generated_at:       str


class AgentTraceStep(BaseModel):
    agent:      str
    action:     str
    timestamp:  Optional[str] = None
    data:       dict          = Field(default_factory=dict)


class ReportResponse(BaseModel):
    task_id:     str
    status:      str
    report:      Optional[OSINTReportOut] = None
    agent_trace: list[AgentTraceStep]    = Field(default_factory=list)
    errors:      list[str]               = Field(default_factory=list)
