from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from orchestrator.state import OSINTState, CollectionTask


SYSTEM_PROMPT = """You are an OSINT planning agent. Given a target entity and context, 
decompose the intelligence-gathering task into a list of specific collection sub-tasks.

Each task must have:
- type: one of [web, dns, github, news, geo, legal]
- query: the exact search string or domain/handle to use
- priority: 1 (critical), 2 (standard), 3 (optional)

Rules:
- For a PERSON: web search full name + employer, linkedin surface search, news coverage
- For an ORG: web + news + github org + dns + legal filings
- For a DOMAIN: dns + certificate intel + shodan + whois + web
- For a TOPIC: web + news + academic

Return ONLY a valid JSON array of task objects. No other text.

Example output:
[
  {"type": "web", "query": "Acme Corp CEO founder", "priority": 1},
  {"type": "news", "query": "Acme Corp", "priority": 1},
  {"type": "github", "query": "AcmeCorp", "priority": 2},
  {"type": "dns", "query": "acme.com", "priority": 1}
]"""


class PlannerAgent:
    def __init__(self):
        self.llm = ChatOllama(model="qwen2.5:3b", temperature=0, format="json")

    def run(self, state: OSINTState) -> dict:
        query = state["query"]
        target_type = state.get("target_type", "unknown")
        refinement = state.get("refinement_count", 0)
        critic_feedback = state.get("critic_feedback", "")

        # On re-planning passes, focus on gaps the critic identified
        user_prompt = f"Target: {query}\nType: {target_type}"
        if refinement > 0 and critic_feedback:
            user_prompt += f"\n\nThis is refinement pass {refinement}. Focus ONLY on filling these gaps:\n{critic_feedback}"

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        response = self.llm.invoke(messages)

        try:
            raw = json.loads(response.content)
            # Model may wrap the array: {"tasks": [...]} or {"plans": [...]} etc.
            if isinstance(raw, dict):
                raw = next((v for v in raw.values() if isinstance(v, list)), [])
            if not isinstance(raw, list):
                raise ValueError(f"Expected JSON array, got {type(raw).__name__}: {str(raw)[:120]}")
            tasks: list[CollectionTask] = [
                {
                    "id":       str(uuid.uuid4()),
                    "type":     t["type"],
                    "query":    t["query"],
                    "priority": t.get("priority", 2),
                    "status":   "pending",
                }
                for t in raw
                if isinstance(t, dict) and "type" in t and "query" in t
            ]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, AttributeError) as e:
            tasks = []
            print(f"[planner] parse error: {e} | raw response: {response.content[:300]}")
            return {
                "errors": [f"PlannerAgent JSON parse error: {e}"],
                "collection_tasks": [],
                "status": "collecting",
                "agent_trace": [{"agent": "planner", "action": "parse_error", "error": str(e)}],
            }

        return {
            "collection_tasks": tasks,
            "planner_notes": f"Generated {len(tasks)} tasks for '{query}' (pass {refinement + 1})",
            "refinement_count": refinement + 1 if refinement > 0 else 0,
            "status": "collecting",
            "agent_trace": [{
                "agent":       "planner",
                "action":      "tasks_generated",
                "task_count":  len(tasks),
                "tasks":       [{"type": t["type"], "query": t["query"]} for t in tasks],
                "timestamp":   datetime.now(timezone.utc).isoformat(),
                "refinement":  refinement,
            }],
        }
