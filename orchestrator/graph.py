from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from .state import OSINTState
from .router import (
    route_entry,
    route_after_critic,
    route_after_image_intel,
)

from agents.planner_agent import PlannerAgent
from agents.web_collector_agent import WebCollectorAgent
from agents.dns_agent import DNSAgent
from agents.github_agent import GitHubAgent
from agents.news_agent import NewsAgent
from agents.legal_agent import LegalAgent
from agents.geo_agent import GeoAgent
from agents.email_agent import EmailAgent
from agents.entity_extractor_agent import EntityExtractorAgent
from agents.crossreference_agent import CrossReferenceAgent
from agents.synthesis_agent import SynthesisAgent
from agents.critic_agent import CriticAgent
from agents.image_intel_agent import ImageIntelAgent
from agents.image_search_agent import ImageSearchAgent

import os


def _make_graph(checkpointer=None) -> StateGraph:
    planner   = PlannerAgent()
    web       = WebCollectorAgent()
    dns       = DNSAgent()
    github    = GitHubAgent()
    news      = NewsAgent()
    legal     = LegalAgent()
    geo       = GeoAgent()
    email     = EmailAgent()
    entity_ex = EntityExtractorAgent()
    crossref  = CrossReferenceAgent()
    synthesis = SynthesisAgent()
    critic    = CriticAgent()
    image_intel   = ImageIntelAgent()
    image_search  = ImageSearchAgent()

    graph = StateGraph(OSINTState)

    # ── Register nodes ──────────────────────────────────────
    graph.add_node("planner_agent",        planner.run)
    graph.add_node("web_collector_agent",  web.run)
    graph.add_node("dns_agent",            dns.run)
    graph.add_node("github_agent",         github.run)
    graph.add_node("news_agent",           news.run)
    graph.add_node("legal_agent",          legal.run)
    graph.add_node("geo_agent",            geo.run)
    graph.add_node("email_agent",          email.run)
    graph.add_node("entity_extractor_agent", entity_ex.run)
    graph.add_node("crossreference_agent", crossref.run)
    graph.add_node("synthesis_agent",      synthesis.run)
    graph.add_node("critic_agent",         critic.run)
    graph.add_node("image_intel_agent",    image_intel.run)
    graph.add_node("image_search_agent",   image_search.run)
    graph.add_node("finalise",             _finalise)

    # ── Entry point ─────────────────────────────────────────
    graph.set_conditional_entry_point(
        route_entry,
        {
            "image_intel_agent": "image_intel_agent",
            "planner_agent":     "planner_agent",
        }
    )

    # ── Image intel → planner ───────────────────────────────
    graph.add_conditional_edges(
        "image_intel_agent",
        route_after_image_intel,
        {"planner_agent": "planner_agent"}
    )

    # ── Planner → parallel collectors (always fan-out to all 7) ─
    # Each collector skips gracefully if it has no relevant tasks.
    # Using direct edges avoids LangGraph partial-fan-out deadlocks
    # where entity_extractor waits forever for collectors that were
    # never dispatched.
    graph.add_edge("planner_agent", "web_collector_agent")
    graph.add_edge("planner_agent", "dns_agent")
    graph.add_edge("planner_agent", "github_agent")
    graph.add_edge("planner_agent", "news_agent")
    graph.add_edge("planner_agent", "legal_agent")
    graph.add_edge("planner_agent", "geo_agent")
    graph.add_edge("planner_agent", "email_agent")
    graph.add_edge("planner_agent", "image_search_agent")

    # ── All collectors → entity extractor ───────────────────
    for collector in ["web_collector_agent", "dns_agent", "github_agent", "news_agent",
                      "legal_agent", "geo_agent", "email_agent", "image_search_agent"]:
        graph.add_edge(collector, "entity_extractor_agent")

    # ── Entity extractor → cross-reference ──────────────────
    graph.add_edge("entity_extractor_agent", "crossreference_agent")

    # ── Cross-reference → synthesis ─────────────────────────
    graph.add_edge("crossreference_agent", "synthesis_agent")

    # ── Synthesis → critic ───────────────────────────────────
    graph.add_edge("synthesis_agent", "critic_agent")

    # ── Critic → finalise OR re-plan ────────────────────────
    graph.add_conditional_edges(
        "critic_agent",
        route_after_critic,
        {
            "finalise":      "finalise",
            "planner_agent": "planner_agent",
        }
    )

    # ── Finalise → END ──────────────────────────────────────
    graph.add_edge("finalise", END)

    return graph.compile(checkpointer=checkpointer)


def _finalise(state: OSINTState) -> dict:
    """Promotes draft_report to final_report and marks status done."""
    draft = state.get("draft_report") or {}
    image_results = state.get("image_results") or []
    final = {**draft, "image_results": image_results}
    return {
        "final_report": final,
        "status": "done",
        "agent_trace": [{
            "agent":         "finalise",
            "action":        "Report finalised",
            "finding_count": len(state.get("findings", [])),
            "entity_count":  len(state.get("entities", [])),
            "image_count":   len(image_results),
        }]
    }


async def build_graph_with_checkpointer(db_url: str):
    """Build graph with async PostgreSQL checkpointer for production use."""
    checkpointer = AsyncPostgresSaver.from_conn_string(db_url)
    await checkpointer.setup()
    return _make_graph(checkpointer=checkpointer)


def build_graph_in_memory():
    """Build graph without persistence — for dev/testing."""
    from langgraph.checkpoint.memory import MemorySaver
    return _make_graph(checkpointer=MemorySaver())
