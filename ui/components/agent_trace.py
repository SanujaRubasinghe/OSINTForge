from __future__ import annotations
import streamlit as st
from datetime import datetime


AGENT_CFG = {
    "planner":          {"color": "#7b2fff", "label": "PLANNER",         "icon": "◈"},
    "web_collector":    {"color": "#00ff88", "label": "WEB-COLLECTOR",   "icon": "◉"},
    "dns_agent":        {"color": "#00d4ff", "label": "DNS-AGENT",       "icon": "▣"},
    "github_agent":     {"color": "#39ff14", "label": "GITHUB-AGENT",    "icon": "⬡"},
    "news_agent":       {"color": "#ff9500", "label": "NEWS-AGENT",      "icon": "◎"},
    "legal_agent":      {"color": "#ff2d78", "label": "LEGAL-AGENT",     "icon": "◆"},
    "geo_agent":        {"color": "#00ffcc", "label": "GEO-AGENT",       "icon": "◇"},
    "email_agent":      {"color": "#ffdd00", "label": "EMAIL-AGENT",     "icon": "◈"},
    "entity_extractor": {"color": "#7b2fff", "label": "ENTITY-EXTRACT",  "icon": "◉"},
    "crossreference":   {"color": "#00ff88", "label": "CROSS-REF",       "icon": "⬡"},
    "synthesis":        {"color": "#00d4ff", "label": "SYNTHESIS",       "icon": "▣"},
    "critic":           {"color": "#ff9500", "label": "CRITIC",          "icon": "◆"},
    "image_intel":      {"color": "#ff2d78", "label": "IMAGE-INTEL",     "icon": "◎"},
    "image_search":     {"color": "#ffdd00", "label": "IMAGE-SEARCH",    "icon": "◎"},
    "finalise":         {"color": "#00ff88", "label": "FINALISE",        "icon": "⬡"},
}

ACTION_ICONS = {
    "tasks_generated":   "▸",
    "collected":         "▸",
    "extracted":         "▸",
    "cross_referenced":  "▸",
    "report_generated":  "▸",
    "review_complete":   "▸",
    "analysed":          "▸",
    "error":             "✗",
    "no_tasks":          "—",
    "no_findings":       "—",
    "no_entities":       "—",
    "no_draft":          "—",
    "no_image":          "—",
    "parse_error":       "✗",
    "Report finalised":  "✓",
}

_PIPELINE_STAGES = [
    ("planner",          "PLAN"),
    ("web_collector",    "COLLECT"),
    ("entity_extractor", "EXTRACT"),
    ("crossreference",   "XREF"),
    ("synthesis",        "SYNTH"),
    ("critic",           "REVIEW"),
    ("finalise",         "DONE"),
]


def render_trace(agent_trace: list[dict], status: str = "running"):
    if not agent_trace:
        st.markdown(
            "<div style='font-family:monospace;color:#7a8fa6;padding:12px'>"
            "> WAITING FOR AGENT SIGNALS...</div>",
            unsafe_allow_html=True,
        )
        _render_pipeline_bar(active_agent=None)
        return

    _render_pipeline_bar(
        active_agent=agent_trace[-1].get("agent") if status == "running" else None,
        done=(status == "done"),
    )

    st.markdown(
        f"<div style='font-family:monospace;font-size:11px;color:#334455;"
        f"letter-spacing:2px;margin:10px 0 6px'>"
        f"── LOG ENTRIES: <span style='color:#7a8fa6'>{len(agent_trace)}</span> ──</div>",
        unsafe_allow_html=True,
    )

    for i, step in enumerate(reversed(agent_trace)):
        _render_step(step, index=len(agent_trace) - i)


def _render_pipeline_bar(active_agent: str | None, done: bool = False):
    cols = st.columns(len(_PIPELINE_STAGES))
    for col, (key, label) in zip(cols, _PIPELINE_STAGES):
        cfg       = AGENT_CFG.get(key, {"color": "#334455"})
        is_active = active_agent and key in (active_agent or "")
        color     = cfg["color"]

        if is_active:
            border  = f"1px solid {color}"
            bg      = f"rgba({_hex_to_rgb(color)},0.15)"
            text_c  = color
            opacity = "1"
            prefix  = "⟳ "
        elif done:
            border  = f"1px solid {color}"
            bg      = f"rgba({_hex_to_rgb(color)},0.08)"
            text_c  = color
            opacity = "0.8"
            prefix  = "✓ "
        else:
            border  = "1px solid #1a2535"
            bg      = "#0f1520"
            text_c  = "#334455"
            opacity = "0.6"
            prefix  = ""

        col.markdown(
            f"<div style='background:{bg};color:{text_c};border:{border};"
            f"border-radius:3px;padding:5px 2px;text-align:center;"
            f"font-family:monospace;font-size:10px;font-weight:700;"
            f"letter-spacing:1px;opacity:{opacity}'>{prefix}{label}</div>",
            unsafe_allow_html=True,
        )


def _render_step(step: dict, index: int):
    agent  = step.get("agent", "unknown")
    action = step.get("action", "")
    ts     = step.get("timestamp", "")

    # Match agent key (strip _agent suffix for lookup)
    cfg_key = agent
    if cfg_key not in AGENT_CFG:
        cfg_key = agent.replace("_agent", "")
    cfg   = AGENT_CFG.get(cfg_key, {"color": "#334455", "label": agent.upper(), "icon": "◦"})
    color = cfg["color"]
    icon  = ACTION_ICONS.get(action, "▸")
    is_error = action in ("error", "parse_error") or bool(step.get("error"))

    time_str = ""
    if ts:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            time_str = dt.strftime("%H:%M:%S")
        except Exception:
            time_str = ts[:8]

    status_color = "#ff3366" if is_error else color

    st.markdown(
        f"<div style='display:flex;align-items:center;gap:8px;"
        f"padding:6px 0;border-bottom:1px solid #0f1520'>"
        f"<span style='font-family:monospace;font-size:10px;color:#334455'>{index:03d}</span>"
        f"<span style='color:{status_color};font-family:monospace;font-size:12px'>{cfg['icon']}</span>"
        f"<span style='color:{status_color};font-family:monospace;font-size:11px;"
        f"font-weight:700;letter-spacing:1px'>{cfg['label']}</span>"
        f"<span style='color:{status_color};font-family:monospace;font-size:11px'>{icon}</span>"
        f"<span style='font-family:monospace;font-size:11px;color:#7a8fa6'>"
        f"{action.replace('_', '-').upper()}</span>"
        f"<span style='margin-left:auto;font-family:monospace;font-size:10px;"
        f"color:#334455'>{time_str}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Metrics row
    metric_keys = [
        ("task_count",         "TASKS"),
        ("raw_count",          "RAW"),
        ("deduped_count",      "DEDUPED"),
        ("count",              "ITEMS"),
        ("entity_count",       "ENTITIES"),
        ("relationship_count", "LINKS"),
        ("claim_count",        "CLAIMS"),
        ("gap_count",          "GAPS"),
        ("cross_ref_count",    "XREF"),
        ("high_confidence",    "HIGH-CONF"),
        ("finding_count",      "FINDINGS"),
        ("gaps_found",         "GAPS"),
        ("unsupported",        "UNSUPPORTED"),
    ]

    metrics = [(lbl, step[key]) for key, lbl in metric_keys if step.get(key)]
    if metrics:
        mcols = st.columns(min(len(metrics), 6))
        for mcol, (mlabel, mval) in zip(mcols, metrics):
            mcol.markdown(
                f"<div style='text-align:center;padding:4px'>"
                f"<div style='font-family:monospace;font-size:16px;"
                f"font-weight:700;color:{color}'>{mval}</div>"
                f"<div style='font-family:monospace;font-size:9px;"
                f"color:#334455;letter-spacing:1px'>{mlabel}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # Pass/fail badge
    if step.get("passed") is True:
        st.markdown(
            f"<span style='font-family:monospace;font-size:10px;color:#00ff88;"
            f"letter-spacing:1px'>✓ CRITIC-PASS</span>",
            unsafe_allow_html=True,
        )
    elif step.get("passed") is False:
        st.markdown(
            f"<span style='font-family:monospace;font-size:10px;color:#ff9500;"
            f"letter-spacing:1px'>⚠ ISSUES-DETECTED</span>",
            unsafe_allow_html=True,
        )

    # Task breakdown
    if step.get("tasks"):
        with st.expander(f"TASK BREAKDOWN [{len(step['tasks'])}]"):
            for t in step["tasks"]:
                ttype = t.get("type", "?").upper()
                tcfg  = AGENT_CFG.get(t.get("type", ""), {"color": "#334455"})
                st.markdown(
                    f"<span style='color:{tcfg['color']};font-family:monospace;"
                    f"font-size:11px;font-weight:700'>[{ttype}]</span> "
                    f"<code style='font-size:11px;color:#7a8fa6'>{t.get('query', '')}</code>",
                    unsafe_allow_html=True,
                )

    # Critic feedback
    if step.get("feedback") and step["feedback"] not in ("None", ""):
        st.markdown(
            f"<div style='background:#140d00;border-left:2px solid #ff9500;"
            f"padding:6px 10px;font-family:monospace;font-size:11px;"
            f"color:#ff9500;margin-top:4px'>CRITIC: {step['feedback']}</div>",
            unsafe_allow_html=True,
        )

    # Error
    if step.get("error"):
        st.markdown(
            f"<div style='background:#14000a;border-left:2px solid #ff3366;"
            f"padding:6px 10px;font-family:monospace;font-size:11px;"
            f"color:#ff3366;margin-top:4px'>ERROR: {step['error']}</div>",
            unsafe_allow_html=True,
        )


def _hex_to_rgb(hex_color: str) -> str:
    """Convert '#rrggbb' to 'r,g,b' string for rgba()."""
    h = hex_color.lstrip("#")
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"{r},{g},{b}"
    except Exception:
        return "100,100,100"
