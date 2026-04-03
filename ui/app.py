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
POLL_MS     = 1200
MAX_HISTORY = 20


# ════════════════════════════════════════════════════════════
#  Page setup
# ════════════════════════════════════════════════════════════
st.set_page_config(
    page_title = "OSINTForge // CLASSIFIED",
    page_icon  = "◈",
    layout     = "wide",
    initial_sidebar_state = "expanded",
)

# ── Cyberpunk CSS ────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

/* ── Global background & text ── */
.stApp {
    background-color: #0a0e17 !important;
    color: #c8d8e8 !important;
}
.stApp > div { background-color: #0a0e17 !important; }

/* Scanline overlay */
.stApp::before {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: repeating-linear-gradient(
        0deg,
        transparent,
        transparent 2px,
        rgba(0,0,0,0.08) 2px,
        rgba(0,0,0,0.08) 4px
    );
    pointer-events: none;
    z-index: 9999;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background-color: #080c14 !important;
    border-right: 1px solid #1a2535 !important;
    min-width: 300px !important;
    max-width: 340px !important;
}
[data-testid="stSidebar"] * { color: #c8d8e8 !important; }
[data-testid="stSidebar"] .stMarkdown p { color: #7a8fa6 !important; }

/* ── All text inputs ── */
.stTextInput input, .stSelectbox select, .stFileUploader {
    background-color: #0f1520 !important;
    color: #00ff88 !important;
    border: 1px solid #1a2535 !important;
    border-radius: 3px !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 13px !important;
}
.stTextInput input:focus {
    border-color: #00ff88 !important;
    box-shadow: 0 0 8px rgba(0,255,136,0.2) !important;
}
.stTextInput label, .stSelectbox label, .stFileUploader label {
    color: #7a8fa6 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
}

/* ── Selectbox ── */
[data-baseweb="select"] {
    background-color: #0f1520 !important;
    border: 1px solid #1a2535 !important;
}
[data-baseweb="select"] * { color: #00ff88 !important; font-family: monospace !important; }

/* ── Primary button ── */
.stButton > button[kind="primary"] {
    background: transparent !important;
    border: 1px solid #00ff88 !important;
    color: #00ff88 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 12px !important;
    letter-spacing: 3px !important;
    text-transform: uppercase !important;
    border-radius: 3px !important;
    transition: all 0.2s !important;
}
.stButton > button[kind="primary"]:hover {
    background: rgba(0,255,136,0.1) !important;
    box-shadow: 0 0 16px rgba(0,255,136,0.3) !important;
}
.stButton > button[kind="primary"]:disabled {
    border-color: #334455 !important;
    color: #334455 !important;
}

/* ── Secondary buttons (history) ── */
.stButton > button {
    background: transparent !important;
    border: 1px solid #1a2535 !important;
    color: #7a8fa6 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 11px !important;
    border-radius: 3px !important;
    text-align: left !important;
}
.stButton > button:hover {
    border-color: #00d4ff !important;
    color: #00d4ff !important;
    background: rgba(0,212,255,0.05) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px !important;
    background-color: #080c14 !important;
    border-bottom: 1px solid #1a2535 !important;
    padding: 0 4px !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    color: #334455 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 2px !important;
    padding: 8px 16px !important;
    border-radius: 0 !important;
}
.stTabs [aria-selected="true"] {
    color: #00ff88 !important;
    border-bottom: 2px solid #00ff88 !important;
    background: rgba(0,255,136,0.05) !important;
}
.stTabs [data-baseweb="tab-panel"] {
    background-color: #0a0e17 !important;
    padding-top: 16px !important;
}

/* ── Metrics ── */
[data-testid="metric-container"] {
    background: #0f1520 !important;
    border: 1px solid #1a2535 !important;
    border-top: 2px solid #00d4ff !important;
    border-radius: 4px !important;
    padding: 10px !important;
}
[data-testid="metric-container"] > label {
    color: #334455 !important;
    font-family: monospace !important;
    font-size: 10px !important;
    letter-spacing: 2px !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #00ff88 !important;
    font-family: monospace !important;
    font-size: 22px !important;
}

/* ── Progress bar ── */
.stProgress > div > div { background-color: #00ff88 !important; }
.stProgress > div { background-color: #1a2535 !important; border-radius: 2px !important; }

/* ── Expander ── */
details {
    background-color: #0f1520 !important;
    border: 1px solid #1a2535 !important;
    border-radius: 4px !important;
}
details > summary {
    color: #7a8fa6 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 1px !important;
    padding: 8px 12px !important;
    cursor: pointer !important;
}
details > summary:hover { color: #00d4ff !important; }

/* ── Alerts / info ── */
.stAlert {
    background-color: #0f1520 !important;
    border: 1px solid #1a2535 !important;
    color: #7a8fa6 !important;
    font-family: monospace !important;
    border-radius: 4px !important;
}
[data-testid="stInfoAlertContent"] { color: #7a8fa6 !important; }
[data-testid="stWarningAlertContent"] { color: #ff9500 !important; }
[data-testid="stErrorAlertContent"] { color: #ff3366 !important; }

/* ── Slider ── */
.stSlider > div > div > div { background: #1a2535 !important; }
.stSlider > div > div > div > div { background: #00ff88 !important; }

/* ── Multiselect ── */
[data-baseweb="tag"] {
    background-color: rgba(0,255,136,0.1) !important;
    border: 1px solid #00ff88 !important;
    color: #00ff88 !important;
    font-family: monospace !important;
    font-size: 11px !important;
}

/* ── Dividers ── */
hr { border-color: #1a2535 !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #080c14; }
::-webkit-scrollbar-thumb { background: #1a2535; border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: #00ff88; }

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background-color: #0f1520 !important;
    border: 1px dashed #1a2535 !important;
    border-radius: 4px !important;
}
[data-testid="stFileUploader"]:hover { border-color: #00ff88 !important; }

/* ── Form ── */
[data-testid="stForm"] {
    background: transparent !important;
    border: 1px solid #1a2535 !important;
    border-radius: 4px !important;
    padding: 12px !important;
}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
#  Session state
# ════════════════════════════════════════════════════════════
def _init_state():
    defaults = {
        "task_id":     None,
        "status":      "idle",
        "report":      None,
        "agent_trace": [],
        "errors":      [],
        "query":       "",
        "history":     [],
        "image_path":  None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ════════════════════════════════════════════════════════════
#  Pipeline config
# ════════════════════════════════════════════════════════════
_PIPELINE = [
    ("planner",          "PLANNING",      0.08),
    ("web_collector",    "WEB-COLLECT",   0.22),
    ("dns_agent",        "DNS-SCAN",      0.34),
    ("github_agent",     "GITHUB-SCAN",   0.44),
    ("news_agent",       "NEWS-SCAN",     0.54),
    ("legal_agent",      "LEGAL-SCAN",    0.62),
    ("entity_extractor", "NLP-EXTRACT",   0.72),
    ("crossreference",   "CROSS-REF",     0.82),
    ("synthesis",        "SYNTHESIS",     0.91),
    ("critic",           "CRITIQUE",      0.96),
    ("finalise",         "FINALISE",      1.00),
]

_AGENT_LABELS = {k: v for k, v, _ in _PIPELINE}

_STAGE_COLORS = {
    "planner":          "#7b2fff",
    "web_collector":    "#00ff88",
    "dns_agent":        "#00d4ff",
    "github_agent":     "#39ff14",
    "news_agent":       "#ff9500",
    "legal_agent":      "#ff2d78",
    "entity_extractor": "#7b2fff",
    "crossreference":   "#00ff88",
    "synthesis":        "#00d4ff",
    "critic":           "#ff9500",
    "finalise":         "#00ff88",
}


def _render_loading(trace: list[dict], errors: list[str]):
    completed_agents: set[str] = set()
    latest_agent   = None
    findings_count = 0
    entities_count = 0
    tasks_count    = 0
    trace_errors: list[str] = []

    for step in trace:
        agent  = step.get("agent", "")
        action = step.get("action", "")
        completed_agents.add(agent)
        latest_agent    = agent
        findings_count  = max(findings_count, step.get("count", step.get("finding_count", 0)) or 0)
        entities_count  = max(entities_count, step.get("entity_count", 0) or 0)
        tasks_count     = max(tasks_count,    step.get("task_count", 0) or 0)
        if step.get("error"):
            trace_errors.append(f"[{agent.upper()}] {step['error']}")

    progress = 0.04
    current_label = "INITIALISING AGENT SWARM..."
    for key, label, pct in _PIPELINE:
        if any(key in a for a in completed_agents):
            progress      = pct
            current_label = label

    # ── Status header ────────────────────────────────────────
    st.markdown(
        "<div style='font-family:monospace;font-size:12px;color:#00ff88;"
        "letter-spacing:2px;margin-bottom:8px'>"
        "⟳ AGENT SWARM ACTIVE — COLLECTING INTELLIGENCE</div>",
        unsafe_allow_html=True,
    )

    # ── Progress bar ─────────────────────────────────────────
    st.progress(
        min(progress, 1.0),
        text=f"**`{current_label}`**  `{int(progress * 100):03d}%`",
    )

    # ── Live counters ─────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("TASKS PLANNED",   tasks_count    or "—")
    c2.metric("FINDINGS",        findings_count or "—")
    c3.metric("ENTITIES",        entities_count or "—")
    c4.metric("PIPELINE STEPS",  len(trace)     or "—")

    st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)

    # ── Stage tiles ───────────────────────────────────────────
    st.markdown(
        "<div style='font-family:monospace;font-size:10px;color:#334455;"
        "letter-spacing:2px;margin-bottom:6px'>// PIPELINE STATUS</div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(len(_PIPELINE))
    for col, (key, label, _pct) in zip(cols, _PIPELINE):
        color       = _STAGE_COLORS.get(key, "#334455")
        is_active   = latest_agent and key in latest_agent
        is_done     = any(key in a for a in completed_agents)
        is_error    = any(key in s.get("agent", "") and s.get("error") for s in trace)

        if is_error:
            bg, border_c, text_c, icon = "#14000a", "#ff3366", "#ff3366", "✗"
        elif is_active:
            bg      = f"rgba({_hex_to_rgb(color)},0.12)"
            border_c = color
            text_c   = color
            icon     = "⟳"
        elif is_done:
            bg      = f"rgba({_hex_to_rgb(color)},0.06)"
            border_c = color
            text_c   = color
            icon     = "✓"
        else:
            bg, border_c, text_c, icon = "#0f1520", "#1a2535", "#334455", ""

        col.markdown(
            f"<div style='background:{bg};color:{text_c};"
            f"border:1px solid {border_c};border-radius:3px;"
            f"padding:5px 2px;text-align:center;"
            f"font-family:monospace;font-size:9px;font-weight:700;"
            f"letter-spacing:1px;line-height:1.6'>{icon} {label}</div>",
            unsafe_allow_html=True,
        )

    # ── Errors ───────────────────────────────────────────────
    all_errors = list(errors) + trace_errors
    if all_errors:
        st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)
        for err in all_errors:
            st.markdown(
                f"<div style='background:#14000a;border-left:2px solid #ff3366;"
                f"padding:6px 10px;font-family:monospace;font-size:11px;"
                f"color:#ff3366;border-radius:0 4px 4px 0;margin-bottom:4px'>"
                f"ERROR: {err}</div>",
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
                data    = {"query": query, "target_type": target_type},
                files   = {"image": (image_file.name, image_file.getvalue(), image_file.type)},
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
        st.error(f"CONN ERROR: {e}")
        return None


def _fetch_report(task_id: str) -> dict | None:
    try:
        resp = requests.get(f"{API_BASE}/report/{task_id}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _refresh_running_state():
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


def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"{r},{g},{b}"
    except Exception:
        return "100,100,100"


# ════════════════════════════════════════════════════════════
#  Sidebar
# ════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        "<div style='font-family:monospace;margin-bottom:2px'>"
        "<span style='color:#00ff88;font-size:18px;font-weight:700;letter-spacing:3px'>"
        "OSINT</span><span style='color:#00d4ff;font-size:18px;font-weight:700;"
        "letter-spacing:3px'>FORGE</span>"
        "</div>"
        "<div style='font-family:monospace;font-size:10px;color:#334455;"
        "letter-spacing:3px;margin-bottom:12px'>MULTI-AGENT INTEL PLATFORM</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div style='font-family:monospace;font-size:10px;color:#1a2535;"
        "border-top:1px solid #1a2535;padding-top:10px;margin-bottom:10px'>"
        "── INPUT PARAMETERS ──</div>",
        unsafe_allow_html=True,
    )

    with st.form("query_form", clear_on_submit=False):
        query = st.text_input(
            "Target entity",
            placeholder = "corp.com / John Doe / acme.corp",
            value       = st.session_state.get("query", ""),
        )
        target_type = st.selectbox(
            "Entity type",
            ["org", "person", "domain", "topic"],
            index = 0,
        )
        image_file = st.file_uploader(
            "Image intel (optional)",
            type = ["jpg", "jpeg", "png", "webp"],
        )
        submitted = st.form_submit_button(
            "▸ INITIATE COLLECTION",
            type                = "primary",
            use_container_width = True,
            disabled            = (st.session_state["status"] == "running"),
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

    # ── Status panel ─────────────────────────────────────────
    if st.session_state["task_id"]:
        status = st.session_state["status"]
        status_map = {
            "running": ("#ff9500", "⟳ COLLECTING"),
            "done":    ("#00ff88", "✓ COMPLETE"),
            "failed":  ("#ff3366", "✗ FAILED"),
            "idle":    ("#334455", "— IDLE"),
        }
        s_color, s_label = status_map.get(status, ("#334455", "UNKNOWN"))
        st.markdown(
            f"<div style='background:#0f1520;border:1px solid #1a2535;"
            f"border-left:2px solid {s_color};border-radius:4px;"
            f"padding:8px 10px;margin-top:10px'>"
            f"<div style='font-family:monospace;font-size:11px;"
            f"font-weight:700;color:{s_color};letter-spacing:2px'>{s_label}</div>"
            f"<div style='font-family:monospace;font-size:10px;color:#7a8fa6;"
            f"margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'>"
            f"{st.session_state['query'][:38]}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        trace = st.session_state["agent_trace"]
        if trace:
            entity_count = next(
                (s.get("entity_count", 0) for s in reversed(trace) if "entity_count" in s), 0
            )
            c1, c2 = st.columns(2)
            c1.metric("STEPS", len(trace))
            c2.metric("ENTITIES", entity_count)

    # ── History ──────────────────────────────────────────────
    if st.session_state["history"]:
        st.markdown(
            "<div style='font-family:monospace;font-size:10px;color:#1a2535;"
            "border-top:1px solid #1a2535;padding-top:10px;margin-top:10px;"
            "margin-bottom:6px'>── QUERY HISTORY ──</div>",
            unsafe_allow_html=True,
        )
        for item in st.session_state["history"][:8]:
            icon = {"done": "✓", "failed": "✗", "running": "⟳"}.get(item["status"], "◦")
            if st.button(
                f"{icon} {item['query'][:26]}  {item['ts']}",
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

    st.markdown(
        "<div style='font-family:monospace;font-size:9px;color:#1a2535;"
        "border-top:1px solid #1a2535;padding-top:10px;margin-top:10px;"
        "letter-spacing:1px'>OSINTForge v1.0 // LangGraph + Claude Sonnet</div>",
        unsafe_allow_html=True,
    )


# ════════════════════════════════════════════════════════════
#  Main content
# ════════════════════════════════════════════════════════════
if not st.session_state["task_id"]:
    # ── Landing ──────────────────────────────────────────────
    st.markdown(
        "<div style='font-family:monospace;margin:40px 0 8px'>"
        "<span style='font-size:32px;font-weight:700;color:#00ff88;"
        "letter-spacing:4px'>OSINT</span>"
        "<span style='font-size:32px;font-weight:700;color:#00d4ff;"
        "letter-spacing:4px'>FORGE</span>"
        "</div>"
        "<div style='font-family:monospace;font-size:12px;color:#334455;"
        "letter-spacing:4px;margin-bottom:32px'>"
        "MULTI-AGENT OPEN-SOURCE INTELLIGENCE PLATFORM</div>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    for col, icon, label, desc in [
        (c1, "◈", "PERSONS",      "Name • Employer • Email • Social footprint"),
        (c2, "⬡", "ORGANISATIONS","Structure • Leadership • Exposure • Filings"),
        (c3, "◉", "DOMAINS",      "DNS • Certs • Subdomains • Hosting"),
        (c4, "◆", "TOPICS",       "Web • News • Academic • Geopolitical"),
    ]:
        col.markdown(
            f"<div style='background:#0f1520;border:1px solid #1a2535;"
            f"border-top:2px solid #00d4ff;border-radius:4px;padding:16px;"
            f"height:110px'>"
            f"<div style='font-family:monospace;font-size:20px;color:#00d4ff;"
            f"margin-bottom:6px'>{icon}</div>"
            f"<div style='font-family:monospace;font-size:11px;font-weight:700;"
            f"color:#00ff88;letter-spacing:2px;margin-bottom:4px'>{label}</div>"
            f"<div style='font-family:monospace;font-size:11px;color:#7a8fa6;"
            f"line-height:1.5'>{desc}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<div style='font-family:monospace;font-size:10px;color:#1a2535;"
        "border-top:1px solid #1a2535;padding-top:12px;margin-top:32px;"
        "letter-spacing:1px'>"
        "// COLLECTION LIMITED TO PUBLICLY AVAILABLE SOURCES &nbsp;·&nbsp; "
        "NO AUTHENTICATED ACCESS &nbsp;·&nbsp; NO FACIAL RECOGNITION"
        "</div>",
        unsafe_allow_html=True,
    )

else:
    # ── Active / completed run ────────────────────────────────
    _refresh_running_state()

    query  = st.session_state["query"]
    status = st.session_state["status"]
    report = st.session_state["report"]
    trace  = st.session_state["agent_trace"]
    errors = st.session_state["errors"]

    status_map = {
        "running": ("#ff9500", "⟳ COLLECTING"),
        "done":    ("#00ff88", "✓ INTEL COMPLETE"),
        "failed":  ("#ff3366", "✗ COLLECTION FAILED"),
    }
    s_color, s_label = status_map.get(status, ("#334455", status.upper()))

    conf_str = ""
    if status == "done" and report:
        conf = report.get("confidence_overall", 0)
        conf_str = f" &nbsp;·&nbsp; CONF: {conf:.0%}"

    st.markdown(
        f"<div style='display:flex;align-items:baseline;gap:12px;margin-bottom:8px'>"
        f"<span style='font-family:monospace;font-size:20px;font-weight:700;"
        f"color:#e0e8f0'>{query}</span>"
        f"<span style='font-family:monospace;font-size:11px;color:{s_color};"
        f"letter-spacing:2px'>{s_label}{conf_str}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    if status == "failed":
        st.markdown(
            f"<div style='background:#14000a;border-left:2px solid #ff3366;"
            f"padding:8px 12px;font-family:monospace;font-size:12px;color:#ff3366'>"
            f"FAILURE: {'; '.join(errors) if errors else 'CHECK AGENT TRACE'}</div>",
            unsafe_allow_html=True,
        )

    tab_report, tab_graph, tab_trace = st.tabs(
        ["◈  REPORT", "⬡  ENTITY GRAPH", "▣  AGENT TRACE"]
    )

    with tab_report:
        if status == "running" and not report:
            _render_loading(trace, errors)
            time.sleep(POLL_MS / 1000)
            st.rerun()
        elif report:
            render_report(report)
        else:
            st.markdown(
                "<div style='font-family:monospace;color:#7a8fa6;padding:20px'>"
                "> NO REPORT DATA AVAILABLE</div>",
                unsafe_allow_html=True,
            )

    with tab_graph:
        if report:
            render_graph(report)
        else:
            st.markdown(
                "<div style='font-family:monospace;color:#7a8fa6;padding:20px'>"
                "> ENTITY GRAPH WILL RENDER WHEN COLLECTION IS COMPLETE</div>",
                unsafe_allow_html=True,
            )

    with tab_trace:
        render_trace(trace, status=status)
        if status == "running":
            time.sleep(POLL_MS / 1000)
            st.rerun()
