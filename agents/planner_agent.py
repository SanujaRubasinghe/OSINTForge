from __future__ import annotations
import json
import os
import uuid
from datetime import datetime, timezone

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

from orchestrator.state import OSINTState, CollectionTask


VALID_TASK_TYPES = {"web", "dns", "github", "news", "geo", "legal"}

SYSTEM_PROMPT = """You are an OSINT planning agent. Given a target entity and context, decompose the intelligence-gathering task into a list of specific collection sub-tasks.

VALID task types (use ONLY these exact strings): web, dns, github, news, geo, legal

Each task object must have exactly these fields:
- "type": one of the valid types above (NEVER use: academic, linkedin, shodan, whois, certificate)
- "query": the exact search string, domain, or handle to look up
- "priority": integer 1 (critical), 2 (standard), or 3 (optional)

Task generation rules by entity type:
- person:  web(full name), web(full name + job title), news(full name), geo(city/country if known), legal(full name)
- org:     web(org name), news(org name), github(org handle), dns(primary domain), legal(org name)
- domain:  dns(domain), web(domain site:domain.com), web(domain whois), news(domain), github(domain owner)
- topic:   web(topic), news(topic), web(topic latest news), web(topic site:reddit.com)

Always generate AT LEAST 3 tasks. For dns tasks, the query must be a bare domain (e.g. "acme.com"), not a URL.

Return ONLY a valid JSON array. No explanation, no markdown, no wrapper object.

Example:
[
  {"type": "web", "query": "Acme Corp CEO founder", "priority": 1},
  {"type": "news", "query": "Acme Corp", "priority": 1},
  {"type": "github", "query": "AcmeCorp", "priority": 2},
  {"type": "dns", "query": "acme.com", "priority": 1},
  {"type": "legal", "query": "Acme Corporation filings", "priority": 3}
]"""


class PlannerAgent:
    def __init__(self):
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.llm = ChatOllama(model="qwen2.5:3b", base_url=ollama_url, temperature=0, format="json")

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
                and t["type"] in VALID_TASK_TYPES
            ]
            # Ensure at least one web task so collectors are never starved
            if not any(t["type"] == "web" for t in tasks):
                tasks.insert(0, {"id": str(uuid.uuid4()), "type": "web", "query": query, "priority": 1, "status": "pending"})
            if not any(t["type"] == "news" for t in tasks):
                tasks.append({"id": str(uuid.uuid4()), "type": "news", "query": query, "priority": 2, "status": "pending"})
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, AttributeError) as e:
            print(f"[planner] parse error: {e} | raw response: {response.content[:300]}")
            # Fallback: generate minimal tasks so collectors aren't starved
            tasks = [
                {"id": str(uuid.uuid4()), "type": "web",  "query": query, "priority": 1, "status": "pending"},
                {"id": str(uuid.uuid4()), "type": "news", "query": query, "priority": 1, "status": "pending"},
            ]
            return {
                "errors": [f"PlannerAgent JSON parse error: {e}"],
                "collection_tasks": tasks,
                "status": "collecting",
                "agent_trace": [{"agent": "planner", "action": "parse_error", "error": str(e),
                                 "task_count": len(tasks), "tasks": [{"type": t["type"], "query": t["query"]} for t in tasks]}],
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
