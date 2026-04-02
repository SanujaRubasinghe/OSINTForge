from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from api.schemas import QueryRequest, TaskStatus
from orchestrator.graph import build_graph_in_memory
from orchestrator.state import OSINTState

router = APIRouter(prefix="/query", tags=["query"])

# In-memory task store (replace with Redis/DB in production)
_tasks: dict[str, dict] = {}


@router.post("/", response_model=TaskStatus)
async def submit_query(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
):
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "status":     "pending",
        "query":      request.query,
        "state":      None,
        "created_at": datetime.now(timezone.utc),
    }
    background_tasks.add_task(_run_graph, task_id, request)
    return TaskStatus(
        task_id    = task_id,
        status     = "pending",
        created_at = _tasks[task_id]["created_at"],
        query      = request.query,
    )


@router.post("/with-image", response_model=TaskStatus)
async def submit_query_with_image(
    background_tasks: BackgroundTasks,
    query:       str        = Form(...),
    target_type: str        = Form("org"),
    image:       UploadFile = File(...),
):
    import os, tempfile, shutil
    task_id = str(uuid.uuid4())

    # Save uploaded image to temp file
    suffix = os.path.splitext(image.filename)[1] or ".jpg"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    shutil.copyfileobj(image.file, tmp)
    tmp.close()

    req = QueryRequest(query=query, target_type=target_type, image_path=tmp.name)
    _tasks[task_id] = {
        "status":     "pending",
        "query":      query,
        "state":      None,
        "created_at": datetime.now(timezone.utc),
    }
    background_tasks.add_task(_run_graph, task_id, req)
    return TaskStatus(
        task_id    = task_id,
        status     = "pending",
        created_at = _tasks[task_id]["created_at"],
        query      = query,
    )


@router.get("/{task_id}/status")
async def get_status(task_id: str) -> TaskStatus:
    task = _tasks.get(task_id)
    if not task:
        from fastapi import HTTPException
        raise HTTPException(404, "Task not found")
    return TaskStatus(
        task_id    = task_id,
        status     = task["status"],
        created_at = task["created_at"],
        query      = task["query"],
    )


@router.get("/{task_id}/stream")
async def stream_task(request: Request, task_id: str):
    """SSE endpoint — streams agent trace steps as they arrive."""
    task = _tasks.get(task_id)
    if not task:
        from fastapi import HTTPException
        raise HTTPException(404, "Task not found")

    async def event_generator():
        last_sent = 0
        while True:
            if await request.is_disconnected():
                break

            state = task.get("state")
            trace = state.get("agent_trace", []) if state else []
            for step in trace[last_sent:]:
                yield {
                    "event": "trace_step",
                    "data":  json.dumps(step),
                }
                last_sent += 1

            status = task["status"]
            if status == "done":
                yield {"event": "done", "data": json.dumps({"task_id": task_id})}
                break
            elif status == "failed":
                yield {"event": "error", "data": json.dumps({"errors": task.get("errors", [])})}
                break

            import asyncio
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())


async def _run_graph(task_id: str, request: QueryRequest):
    import traceback
    print(f"[graph] START task={task_id} query={request.query!r} type={request.target_type}")
    _tasks[task_id]["status"] = "running"
    try:
        print(f"[graph] building graph...")
        graph = build_graph_in_memory()
        print(f"[graph] graph built OK")
        initial_state: OSINTState = {
            "query":              request.query,
            "target_type":        request.target_type,
            "input_image_path":   request.image_path,
            "collection_tasks":   [],
            "planner_notes":      "",
            "findings":           [],
            "entities":           [],
            "relationships":      [],
            "exif_data":          None,
            "reverse_search_urls": None,
            "visual_analysis":    None,
            "ocr_text":           None,
            "detected_logos":     None,
            "draft_report":       None,
            "critic_feedback":    None,
            "refinement_count":   0,
            "final_report":       None,
            "errors":             [],
            "agent_trace":        [],
            "status":             "planning",
        }
        config = {"configurable": {"thread_id": task_id}}
        step_count = 0
        async for state in graph.astream(initial_state, config=config, stream_mode="values"):
            _tasks[task_id]["state"] = state
            step_count += 1
            trace = state.get("agent_trace", [])
            last  = trace[-1] if trace else {}
            errs  = state.get("errors", [])
            print(
                f"[graph] step={step_count} agent={last.get('agent','?')} "
                f"action={last.get('action','?')} errors={errs}"
            )

        final_state = _tasks[task_id]["state"]
        final_errors = final_state.get("errors", [])
        final_status = final_state.get("status", "done")
        print(f"[graph] DONE task={task_id} status={final_status} errors={final_errors}")
        _tasks[task_id]["status"] = final_status
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[graph] EXCEPTION task={task_id}: {e}\n{tb}")
        _tasks[task_id]["status"] = "failed"
        _tasks[task_id]["errors"] = [str(e)]
