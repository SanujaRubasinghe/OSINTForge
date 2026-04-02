from __future__ import annotations
from .state import OSINTState


def route_entry(state: OSINTState) -> str:
    """Entry point: if image provided run image intel first, else go to planner."""
    if state.get("input_image_path"):
        return "image_intel_agent"
    return "planner_agent"


def route_after_planner(state: OSINTState) -> list[str]:
    """
    Fan-out: dispatch all enabled collection tasks in parallel.
    Returns a list of node names for LangGraph Send() parallel dispatch.
    """
    task_types = {t["type"] for t in state["collection_tasks"] if t["status"] == "pending"}
    node_map = {
        "web":    "web_collector_agent",
        "dns":    "dns_agent",
        "github": "github_agent",
        "news":   "news_agent",
        "reddit": "reddit_agent",
        "email":  "email_agent",
        "geo":    "geo_agent",
        "legal":  "legal_agent",
    }
    return [node_map[t] for t in task_types if t in node_map]


def route_after_extraction(state: OSINTState) -> str:
    """After entity extraction: always go to cross-reference."""
    return "crossreference_agent"


def route_after_crossref(state: OSINTState) -> str:
    """After cross-reference: always synthesise."""
    return "synthesis_agent"


def route_after_synthesis(state: OSINTState) -> str:
    """After synthesis: always run critic."""
    return "critic_agent"


def route_after_critic(state: OSINTState) -> str:
    """
    Critic decision:
    - If feedback is empty / confidence OK → finalise
    - If refinement count < 3 → re-collect targeted gaps
    - If max retries hit → force finalise
    """
    feedback = state.get("critic_feedback", "")
    refinement_count = state.get("refinement_count", 0)

    if not feedback or feedback.strip().lower() in ("none", "no issues", ""):
        return "finalise"

    if refinement_count >= 3:
        return "finalise"          # hard stop — prevents infinite loops

    return "planner_agent"         # targeted re-collection pass


def route_after_image_intel(state: OSINTState) -> str:
    """Image intel always flows into planner (with enriched state)."""
    return "planner_agent"
