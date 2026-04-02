from __future__ import annotations
import streamlit as st
from datetime import datetime


AGENT_COLORS = {
    "planner":          {"bg": "#EEEDFE", "text": "#3C3489", "label": "Planner"},
    "web_collector":    {"bg": "#E1F5EE", "text": "#085041", "label": "Web collector"},
    "dns_agent":        {"bg": "#E6F1FB", "text": "#0C447C", "label": "DNS agent"},
    "github_agent":     {"bg": "#F1EFE8", "text": "#444441", "label": "GitHub agent"},
    "news_agent":       {"bg": "#FAEEDA", "text": "#633806", "label": "News agent"},
    "entity_extractor": {"bg": "#CECBF6", "text": "#26215C", "label": "Entity extractor"},
    "crossreference":   {"bg": "#9FE1CB", "text": "#04342C", "label": "Cross-reference"},
    "synthesis":        {"bg": "#F5C4B3", "text": "#4A1B0C", "label": "Synthesis"},
    "critic":           {"bg": "#FAECE7", "text": "#4A1B0C", "label": "Critic"},
    "image_intel":      {"bg": "#F4C0D1", "text": "#4B1528", "label": "Image intel"},
    "finalise":         {"bg": "#C0DD97", "text": "#173404", "label": "Finalise"},
}

ACTION_ICONS = {
    "tasks_generated":   "🗂",
    "collected":         "📥",
    "extracted":         "🔍",
    "cross_referenced":  "🔗",
    "report_generated":  "📄",
    "review_complete":   "✅",
    "analysed":          "🖼",
    "error":             "❌",
    "no_tasks":          "⏭",
    "no_findings":       "⚠️",
    "no_entities":       "⚠️",
    "no_draft":          "⚠️",
    "no_image":          "⏭",
    "parse_error":       "❌",
    "Report finalised":  "🏁",
}


def render_trace(agent_trace: list[dict], status: str = "running"):
    """Render the live agent execution trace."""
    if not agent_trace:
        st.info("Waiting for agents to start...")
        _render_pipeline_overview(active_agent=None)
        return

    _render_pipeline_overview(
        active_agent=agent_trace[-1].get("agent") if status == "running" else None,
        done=(status == "done"),
    )

    st.markdown("---")
    st.caption(f"{len(agent_trace)} step{'s' if len(agent_trace) != 1 else ''} completed")

    for i, step in enumerate(reversed(agent_trace)):
        _render_step(step, index=len(agent_trace) - i)


def _render_pipeline_overview(active_agent: str | None, done: bool = False):
    """Shows the pipeline stages with active stage highlighted."""
    stages = [
        ("planner",          "Plan"),
        ("web_collector",    "Collect"),
        ("entity_extractor", "Extract"),
        ("crossreference",   "Cross-ref"),
        ("synthesis",        "Synthesise"),
        ("critic",           "Critique"),
        ("finalise",         "Done"),
    ]

    cols = st.columns(len(stages))
    for col, (key, label) in zip(cols, stages):
        cfg = AGENT_COLORS.get(key, {"bg": "#F1EFE8", "text": "#444441"})
        is_active = (active_agent and key in (active_agent or ""))
        is_done_stage = done

        if is_active:
            border = f"2px solid {cfg['text']}"
            opacity = "1"
        elif is_done_stage:
            border = f"1px solid {cfg['text']}"
            opacity = "0.9"
        else:
            border = "1px solid #D3D1C7"
            opacity = "0.45"

        col.markdown(
            f"<div style='"
            f"background:{cfg['bg']};color:{cfg['text']};"
            f"border:{border};border-radius:6px;"
            f"padding:5px 4px;text-align:center;"
            f"font-size:11px;font-weight:500;opacity:{opacity};"
            f"'>{label}</div>",
            unsafe_allow_html=True,
        )


def _render_step(step: dict, index: int):
    agent  = step.get("agent", "unknown")
    action = step.get("action", "")
    ts     = step.get("timestamp", "")
    cfg    = AGENT_COLORS.get(agent, {"bg": "#F1EFE8", "text": "#444441", "label": agent})
    icon   = ACTION_ICONS.get(action, "▸")
    label  = cfg.get("label", agent)

    time_str = ""
    if ts:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            time_str = dt.strftime("%H:%M:%S")
        except Exception:
            time_str = ts[:8]

    # Step header
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:8px;margin:6px 0 2px'>"
        f"<span style='font-size:11px;color:#888'>{index:02d}</span>"
        f"<span style='background:{cfg['bg']};color:{cfg['text']};"
        f"padding:2px 8px;border-radius:4px;font-size:11px;font-weight:500'>{label}</span>"
        f"<span style='font-size:13px'>{icon}</span>"
        f"<span style='font-size:12px;color:#5F5E5A'>{action.replace('_', ' ')}</span>"
        f"<span style='margin-left:auto;font-size:11px;color:#B4B2A9;font-family:monospace'>{time_str}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Step metrics (show whatever numeric fields are present)
    metric_keys = [
        ("task_count",        "tasks"),
        ("raw_count",         "raw"),
        ("deduped_count",     "deduped"),
        ("count",             "items"),
        ("entity_count",      "entities"),
        ("relationship_count","relations"),
        ("claim_count",       "claims"),
        ("gap_count",         "gaps"),
        ("cross_ref_count",   "cross-ref'd"),
        ("high_confidence",   "high conf"),
        ("finding_count",     "findings"),
        ("reverse_urls",      "reverse URLs"),
        ("ocr_chars",         "OCR chars"),
        ("gaps_found",        "gaps"),
        ("unsupported",       "unsupported"),
    ]

    metrics = [(label, step[key]) for key, label in metric_keys if key in step and step[key]]
    if metrics:
        mcols = st.columns(min(len(metrics), 5))
        for mcol, (mlabel, mval) in zip(mcols, metrics):
            mcol.metric(mlabel, mval)

    # Boolean flags
    flags = []
    if step.get("passed") is True:
        flags.append(("✓ Passed critic review", "#0F6E56"))
    if step.get("passed") is False:
        flags.append(("✗ Issues found", "#993C1D"))
    if step.get("has_gps"):
        flags.append(("GPS extracted", "#185FA5"))

    if flags:
        flag_html = " ".join(
            f"<span style='font-size:11px;color:{c}'>{t}</span>"
            for t, c in flags
        )
        st.markdown(flag_html, unsafe_allow_html=True)

    # Tasks breakdown (planner output)
    if "tasks" in step and step["tasks"]:
        with st.expander(f"Task breakdown ({len(step['tasks'])})", expanded=False):
            for t in step["tasks"]:
                ttype = t.get("type", "?")
                tcfg  = AGENT_COLORS.get(ttype.replace("_agent", ""), {"bg": "#F1EFE8", "text": "#444441"})
                st.markdown(
                    f"<span style='background:{tcfg['bg']};color:{tcfg['text']};"
                    f"padding:1px 6px;border-radius:3px;font-size:11px'>{ttype}</span> "
                    f"<code style='font-size:11px'>{t.get('query', '')}</code>",
                    unsafe_allow_html=True,
                )

    # Critic feedback
    if step.get("feedback") and step["feedback"] not in ("None", ""):
        st.markdown(
            f"<div style='background:#FAECE7;color:#4A1B0C;"
            f"border-left:3px solid #D85A30;padding:6px 10px;"
            f"font-size:12px;border-radius:0 4px 4px 0;margin-top:4px'>"
            f"Critic feedback: {step['feedback']}</div>",
            unsafe_allow_html=True,
        )

    # Errors
    if step.get("error"):
        st.markdown(
            f"<div style='background:#FCEBEB;color:#501313;"
            f"border-left:3px solid #E24B4A;padding:6px 10px;"
            f"font-size:12px;border-radius:0 4px 4px 0;margin-top:4px'>"
            f"Error: {step['error']}</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<hr style='border:none;border-top:0.5px solid var(--color-border-tertiary,"
        "#E8E6DE);margin:6px 0'>",
        unsafe_allow_html=True,
    )
