from __future__ import annotations

from fastapi import APIRouter, HTTPException
from api.schemas import ReportResponse, OSINTReportOut, AgentTraceStep, EntityOut, RelationshipOut, ClaimOut
from api.routes.query import _tasks

router = APIRouter(prefix="/report", tags=["report"])


@router.get("/{task_id}", response_model=ReportResponse)
async def get_report(task_id: str) -> ReportResponse:
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    state      = task.get("state") or {}
    status     = task.get("status", "pending")
    errors     = state.get("errors", [])
    trace_raw  = state.get("agent_trace", [])

    trace = [
        AgentTraceStep(
            agent     = step.get("agent", "unknown"),
            action    = step.get("action", ""),
            timestamp = step.get("timestamp"),
            data      = {k: v for k, v in step.items() if k not in ("agent", "action", "timestamp")},
        )
        for step in trace_raw
    ]

    report_out = None
    final = state.get("final_report")
    if final:
        report_out = OSINTReportOut(
            target             = final["target"],
            summary            = final["summary"],
            entities           = [EntityOut(**e) for e in final.get("entities", [])],
            relationships      = [RelationshipOut(**r) for r in final.get("relationships", [])],
            claims             = [ClaimOut(**c) for c in final.get("claims", [])],
            source_urls        = final.get("source_urls", []),
            gaps               = final.get("gaps", []),
            confidence_overall = final.get("confidence_overall", 0.0),
            generated_at       = final.get("generated_at", ""),
        )

    return ReportResponse(
        task_id     = task_id,
        status      = status,
        report      = report_out,
        agent_trace = trace,
        errors      = errors,
    )
