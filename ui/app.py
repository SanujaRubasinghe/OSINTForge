from __future__ import annotations
import time
import json
from datetime import datetime, timezone

import requests
import streamlit as st

from ui.components.report_view import render_report
from ui.components.graph_view import render_graph
from ui.components.agent_trace import render_trace

# ── Config ──────────────────────────────────────────────────
API_BASE    = "http://localhost:8000"
POLL_MS     = 1200   # ms between state refreshes while running
MAX_HISTORY = 20


# ════════════════════════════════════════════════════════════
#  Page setup
# ════════════════════════════════════════════════════════════
st.set_page_config(
    page_title = "OSINTForge",
    page_icon  = "🔍",
    layout     = "wide",
    initial_sidebar_state = "expanded",
)

# Inject minimal global CSS
st.markdown("""
<style>
[data-testid="stSidebar"] { min-width: 300px; max-width: 340px; }
.stTabs [data-baseweb="tab-list"] { gap: 8px; }
.stTabs [data-baseweb="tab"] { padding: 6px 16px; border-radius: 6px; }
div[data-testid="metric-container"] > label { font-size: 12px !important; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
#  Session state initialisation
# ════════════════════════════════════════════════════════════
def _init_state():
    defaults = {
        "task_id":     None,
        "status":      "idle",      # idle | running | done | failed
        "report":      None,
        "agent_trace": [],
        "errors":      [],
        "query":       "",
        "history":     [],          # list of {task_id, query, status, ts}
        "image_path":  None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ════════════════════════════════════════════════════════════
#  Loading progress
# ════════════════════════════════════════════════════════════
_PIPELINE = [
    ("planner",          "Planning collection tasks",       0.08),
    ("web_collector",    "Collecting from the web",         0.22),
    ("dns_agent",        "Querying DNS & certificates",     0.36),
    ("github_agent",     "Scanning GitHub",                 0.48),
    ("news_agent",       "Searching news sources",          0.58),
    ("entity_extractor", "Extracting entities (NLP)",       0.68),
    ("crossreference",   "Cross-referencing findings",      0.78),
    ("synthesis",        "Synthesising report",             0.88),
    ("critic",           "Critic reviewing draft",          0.94),
    ("finalise",         "Finalising",                      1.00),
]

_AGENT_LABELS = {
    "planner":          "Planner",
    "web_collector":    "Web",
    "dns_agent":        "DNS",
    "github_agent":     "GitHub",
    "news_agent":       "News",
    "entity_extractor": "Entity NLP",
    "crossreference":   "Cross-ref",
    "synthesis":        "Synthesis",
    "critic":           "Critic",
    "finalise":         "Finalise",
}

_AGENT_COLORS = {
    "planner":          ("#EEEDFE", "#3C3489"),
    "web_collector":    ("#E1F5EE", "#085041"),
    "dns_agent":        ("#E6F1FB", "#0C447C"),
    "github_agent":     ("#F1EFE8", "#444441"),
    "news_agent":       ("#FAEEDA", "#633806"),
    "entity_extractor": ("#CECBF6", "#26215C"),
    "crossreference":   ("#9FE1CB", "#04342C"),
    "synthesis":        ("#F5C4B3", "#4A1B0C"),
    "critic":           ("#FAECE7", "#4A1B0C"),
    "finalise":         ("#C0DD97", "#173404"),
}


def _render_loading(trace: list[dict], errors: list[str]):
    """Comprehensive loading view shown while the graph is running."""

    # ── Derive state from trace ──────────────────────────────
    completed_agents: set[str] = set()
    latest_agent  = None
    latest_action = ""
    findings_so_far  = 0
    entities_so_far  = 0
    tasks_planned    = 0
    trace_errors: list[str] = []

    for step in trace:
        agent  = step.get("agent", "")
        action = step.get("action", "")
        # Normalise agent key (strip "_agent" suffix for lookup)
        key = agent.replace("_agent", "").replace("web_collector", "web_collector")
        # Use the raw agent name for completed set
        completed_agents.add(agent)
        latest_agent  = agent
        latest_action = action
        findings_so_far  = max(findings_so_far,  step.get("count", step.get("finding_count", 0)) or 0)
        entities_so_far  = max(entities_so_far,  step.get("entity_count", 0) or 0)
        tasks_planned    = max(tasks_planned,     step.get("task_count", 0) or 0)
        if step.get("error"):
            trace_errors.append(f"[{_AGENT_LABELS.get(agent, agent)}] {step['error']}")

    # ── Progress percentage ──────────────────────────────────
    progress = 0.04  # always show a sliver immediately
    current_label = "Initialising agents..."
    for key, label, pct in _PIPELINE:
        # match by checking if the key appears anywhere in the completed agent names
        if any(key in a for a in completed_agents):
            progress = pct
            current_label = label

    # If the latest agent is still running, advance label to next stage
    if latest_agent:
        for i, (key, label, pct) in enumerate(_PIPELINE):
            if key in latest_agent and i + 1 < len(_PIPELINE):
                next_label = _PIPELINE[i + 1][1]
                current_label = f"{label}..."
                break

    # ── Header ───────────────────────────────────────────────
    st.markdown(
        "<p style='font-size:13px;font-weight:500;color:#5F5E5A;margin-bottom:6px'>"
        "⟳ Agents are running — report will appear here when complete</p>",
        unsafe_allow_html=True,
    )

    # ── Progress bar ─────────────────────────────────────────
    st.progress(min(progress, 1.0), text=f"**{current_label}**  ({int(progress * 100)}%)")

    # ── Live stats ───────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tasks planned",  tasks_planned   or "—")
    c2.metric("Findings so far", findings_so_far or "—")
    c3.metric("Entities found",  entities_so_far or "—")
    c4.metric("Steps completed", len(trace)      or "—")

    st.markdown("")

    # ── Agent status tiles ───────────────────────────────────
    st.caption("Pipeline stages")
    cols = st.columns(len(_PIPELINE))
    for col, (key, label, _pct) in zip(cols, _PIPELINE):
        bg, fg = _AGENT_COLORS.get(key, ("#F1EFE8", "#444441"))
        is_active    = latest_agent and key in latest_agent
        is_completed = any(key in a for a in completed_agents)
        is_error     = any(
            key in step.get("agent", "") and step.get("error")
            for step in trace
        )

        if is_error:
            border  = "2px solid #E24B4A"
            opacity = "1"
            icon    = "✗"
        elif is_active:
            border  = f"2px solid {fg}"
            opacity = "1"
            icon    = "⟳"
        elif is_completed:
            border  = f"1px solid {fg}"
            opacity = "0.9"
            icon    = "✓"
        else:
            border  = "1px solid #D3D1C7"
            opacity = "0.35"
            icon    = ""

        col.markdown(
            f"<div style='background:{bg};color:{fg};"
            f"border:{border};border-radius:6px;"
            f"padding:5px 2px;text-align:center;"
            f"font-size:11px;font-weight:500;opacity:{opacity};line-height:1.5'>"
            f"{icon} {_AGENT_LABELS.get(key, label)}</div>",
            unsafe_allow_html=True,
        )

    # ── Errors ───────────────────────────────────────────────
    all_errors = list(errors) + trace_errors
    if all_errors:
        st.markdown("")
        st.markdown(
            "<p style='font-size:12px;font-weight:600;color:#501313;margin-bottom:4px'>"
            "⚠ Errors detected</p>",
            unsafe_allow_html=True,
        )
        for err in all_errors:
            st.markdown(
                f"<div style='background:#FCEBEB;color:#501313;"
                f"border-left:3px solid #E24B4A;padding:6px 10px;"
                f"font-size:12px;border-radius:0 4px 4px 0;margin-bottom:4px'>"
                f"{err}</div>",
                unsafe_allow_html=True,
            )


# ════════════════════════════════════════════════════════════
#  API helpers
# ════════════════════════════════════════════════════════════
def _submit_query(query: str, target_type: str, image_file=None) -> str | None:
    try:
        if image_file:
            resp = requests.post(
                f"{API_BASE}/query/with-image",
                data  = {"query": query, "target_type": target_type},
                files = {"image": (image_file.name, image_file.getvalue(), image_file.type)},
                timeout = 10,
            )
        else:
            resp = requests.post(
                f"{API_BASE}/query/",
                json    = {"query": query, "target_type": target_type},
                timeout = 10,
            )
        resp.raise_for_status()
        return resp.json()["task_id"]
    except Exception as e:
        st.error(f"Failed to submit query: {e}")
        return None


def _fetch_report(task_id: str) -> dict | None:
    try:
        resp = requests.get(f"{API_BASE}/report/{task_id}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _refresh_running_state():
    """Fetch latest task state from API and update session_state in-place.

    Called at the top of each Streamlit rerun while a task is running.
    Avoids background threads (which can't reliably write session_state
    in Streamlit ≥ 1.28 without add_script_run_ctx).
    """
    task_id = st.session_state.get("task_id")
    if not task_id or st.session_state.get("status") != "running":
        return
    data = _fetch_report(task_id)
    if not data:
        return
    st.session_state["agent_trace"] = [
        {**step.get("data", {}), "agent": step["agent"], "action": step["action"],
         "timestamp": step.get("timestamp")}
        for step in data.get("agent_trace", [])
    ]
    st.session_state["errors"] = data.get("errors", [])
    st.session_state["status"] = data.get("status", "running")
    if data.get("report"):
        st.session_state["report"] = data["report"]


# ════════════════════════════════════════════════════════════
#  Sidebar
# ════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## OSINTForge 🔍")
    st.caption("Multi-agent OSINT synthesis")
    st.markdown("---")

    # ── Query form ──────────────────────────────────────────
    with st.form("query_form", clear_on_submit=False):
        query = st.text_input(
            "Target entity",
            placeholder = "Acme Corp / john.doe@example.com / acme.com",
            value       = st.session_state.get("query", ""),
        )
        target_type = st.selectbox(
            "Entity type",
            ["org", "person", "domain", "topic"],
            index = 0,
        )
        image_file = st.file_uploader(
            "Image (optional)",
            type    = ["jpg", "jpeg", "png", "webp"],
            help    = "Upload a photo to run image intelligence",
        )
        submitted = st.form_submit_button(
            "Run OSINT →",
            type = "primary",
            use_container_width = True,
            disabled = (st.session_state["status"] == "running"),
        )

    if submitted and query.strip():
        task_id = _submit_query(query.strip(), target_type, image_file)
        if task_id:
            st.session_state.update({
                "task_id":     task_id,
                "status":      "running",
                "report":      None,
                "agent_trace": [],
                "errors":      [],
                "query":       query.strip(),
            })
            st.session_state["history"].insert(0, {
                "task_id": task_id,
                "query":   query.strip(),
                "status":  "running",
                "ts":      datetime.now(timezone.utc).strftime("%H:%M:%S"),
            })
            st.session_state["history"] = st.session_state["history"][:MAX_HISTORY]
            st.rerun()

    # ── Status indicator ────────────────────────────────────
    if st.session_state["task_id"]:
        status = st.session_state["status"]
        color_map = {
            "running": "#BA7517",
            "done":    "#0F6E56",
            "failed":  "#993C1D",
            "idle":    "#888780",
        }
        col = color_map.get(status, "#888780")
        spinner = "⟳ " if status == "running" else ""
        st.markdown(
            f"<div style='margin-top:8px;padding:6px 10px;"
            f"background:#F1EFE8;border-radius:6px;font-size:13px'>"
            f"<span style='color:{col};font-weight:500'>{spinner}{status.upper()}</span><br>"
            f"<span style='color:#5F5E5A;font-size:11px'>{st.session_state['query'][:40]}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        trace = st.session_state["agent_trace"]
        if trace:
            step_count = len(trace)
            entity_count = next(
                (s.get("entity_count", 0) for s in reversed(trace) if "entity_count" in s), 0
            )
            c1, c2 = st.columns(2)
            c1.metric("Steps", step_count)
            c2.metric("Entities", entity_count)

    # ── History ─────────────────────────────────────────────
    if st.session_state["history"]:
        st.markdown("---")
        st.caption("Recent queries")
        for item in st.session_state["history"][:8]:
            status_icon = {"done": "✓", "failed": "✗", "running": "⟳"}.get(item["status"], "•")
            if st.button(
                f"{status_icon} {item['query'][:28]} ({item['ts']})",
                key             = f"hist_{item['task_id']}",
                use_container_width = True,
            ):
                st.session_state["task_id"] = item["task_id"]
                st.session_state["query"]   = item["query"]
                data = _fetch_report(item["task_id"])
                if data:
                    st.session_state["status"]      = data.get("status", "done")
                    st.session_state["report"]      = data.get("report")
                    st.session_state["agent_trace"] = [
                        {**s.get("data", {}), "agent": s["agent"],
                         "action": s["action"], "timestamp": s.get("timestamp")}
                        for s in data.get("agent_trace", [])
                    ]
                st.rerun()

    st.markdown("---")
    st.caption("OSINTForge v1.0 · LangGraph + Claude Sonnet")


# ════════════════════════════════════════════════════════════
#  Main content
# ════════════════════════════════════════════════════════════
if not st.session_state["task_id"]:
    # ── Landing state ───────────────────────────────────────
    st.markdown("## Welcome to OSINTForge")
    st.markdown(
        "Enter a target entity in the sidebar to start a multi-agent "
        "OSINT collection run. The swarm will automatically gather intelligence "
        "from web, news, DNS, GitHub, and more — then synthesise it into a "
        "structured report with citations."
    )

    col1, col2, col3 = st.columns(3)
    col1.info("**Persons** — name, employer, email, social presence")
    col2.info("**Organisations** — structure, leadership, exposure, news")
    col3.info("**Domains** — DNS, certificates, subdomains, hosting")

    st.markdown("---")
    st.caption(
        "All collection is limited to publicly available sources. "
        "No facial recognition. No authenticated access to third-party services."
    )

else:
    # ── Active / completed run ──────────────────────────────
    _refresh_running_state()   # fetch latest state on every rerun

    query  = st.session_state["query"]
    status = st.session_state["status"]
    report = st.session_state["report"]
    trace  = st.session_state["agent_trace"]
    errors = st.session_state["errors"]

    # Header
    st.markdown(f"### {query}")
    if status == "running":
        st.markdown(
            "<div style='display:inline-block;padding:3px 10px;"
            "background:#FAEEDA;color:#633806;border-radius:4px;"
            "font-size:12px;font-weight:500'>⟳ Collecting intelligence...</div>",
            unsafe_allow_html=True,
        )
    elif status == "done":
        conf = report.get("confidence_overall", 0) if report else 0
        st.markdown(
            f"<div style='display:inline-block;padding:3px 10px;"
            f"background:#E1F5EE;color:#085041;border-radius:4px;"
            f"font-size:12px;font-weight:500'>✓ Complete — {conf:.0%} confidence</div>",
            unsafe_allow_html=True,
        )
    elif status == "failed":
        st.error("Run failed. " + ("; ".join(errors) if errors else "Check agent trace for details."))

    st.markdown("")

    # ── Three-panel tabs ─────────────────────────────────────
    tab_report, tab_graph, tab_trace = st.tabs(["📄 Report", "🕸 Graph", "🔬 Agent trace"])

    with tab_report:
        if status == "running" and not report:
            _render_loading(trace, errors)
            time.sleep(POLL_MS / 1000)
            st.rerun()
        elif report:
            render_report(report)
        else:
            st.info("No report available.")

    with tab_graph:
        if report:
            render_graph(report)
        else:
            st.info("Knowledge graph will appear once the report is ready.")

    with tab_trace:
        render_trace(trace, status=status)
        if status == "running":
            time.sleep(POLL_MS / 1000)
            st.rerun()
