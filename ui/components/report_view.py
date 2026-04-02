from __future__ import annotations
import streamlit as st
import re


CONFIDENCE_COLOR = {
    "high":   "#1D9E75",
    "medium": "#BA7517",
    "low":    "#D85A30",
}

def _conf_label(score: float) -> tuple[str, str]:
    if score >= 0.75:
        return "high",   CONFIDENCE_COLOR["high"]
    elif score >= 0.50:
        return "medium", CONFIDENCE_COLOR["medium"]
    return "low", CONFIDENCE_COLOR["low"]


def render_report(report: dict):
    """Render the full OSINTReport in the Streamlit report panel."""
    if not report:
        st.info("No report available yet.")
        return

    # ── Header ─────────────────────────────────────────────
    level, color = _conf_label(report.get("confidence_overall", 0))
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Entities found",    len(report.get("entities", [])))
    col2.metric("Relationships",     len(report.get("relationships", [])))
    col3.metric("Claims",            len(report.get("claims", [])))
    col4.metric("Sources",           len(report.get("source_urls", [])))

    st.markdown(
        f"**Overall confidence:** "
        f"<span style='color:{color};font-weight:600'>{level.upper()} ({report.get('confidence_overall', 0):.0%})</span>",
        unsafe_allow_html=True,
    )

    # ── Executive Summary ───────────────────────────────────
    st.subheader("Executive summary")
    summary = report.get("summary", "No summary available.")
    # Highlight [SOURCE: ...] citations
    highlighted = re.sub(
        r'\[SOURCE: (https?://[^\]]+)\]',
        r'<a href="\1" target="_blank" style="font-size:11px;color:#185FA5">[src]</a>',
        summary
    )
    st.markdown(highlighted, unsafe_allow_html=True)

    # ── Entities ────────────────────────────────────────────
    st.subheader("Discovered entities")
    entities = report.get("entities", [])
    if entities:
        type_order = ["PERSON", "ORG", "DOMAIN", "IP", "EMAIL", "LOCATION", "EVENT"]
        by_type: dict[str, list] = {}
        for e in entities:
            by_type.setdefault(e["type"], []).append(e)

        for etype in type_order:
            group = by_type.get(etype, [])
            if not group:
                continue
            with st.expander(f"{etype} ({len(group)})", expanded=etype in ("PERSON", "ORG")):
                for ent in sorted(group, key=lambda x: x["confidence"], reverse=True):
                    lvl, col = _conf_label(ent["confidence"])
                    src_count = len(ent.get("sources", []))
                    cross_ref = ent.get("attributes", {}).get("cross_referenced", False)
                    badge = "✓ cross-referenced" if cross_ref else ""
                    st.markdown(
                        f"**{ent['name']}** "
                        f"<span style='color:{col};font-size:12px'>{ent['confidence']:.0%}</span> "
                        f"<span style='color:#888;font-size:11px'>{src_count} source{'s' if src_count != 1 else ''} {badge}</span>",
                        unsafe_allow_html=True,
                    )
    else:
        st.write("No entities extracted.")

    # ── Claims ──────────────────────────────────────────────
    st.subheader("Intelligence claims")
    claims = report.get("claims", [])
    flagged = [c for c in claims if c.get("flagged")]
    supported = [c for c in claims if not c.get("flagged")]

    if flagged:
        st.warning(f"{len(flagged)} claim(s) flagged by critic as potentially unsupported")
        with st.expander("Flagged claims"):
            for c in flagged:
                _render_claim(c, flagged=True)

    for claim in sorted(supported, key=lambda x: x["confidence"], reverse=True):
        _render_claim(claim)

    # ── Intelligence gaps ────────────────────────────────────
    gaps = report.get("gaps", [])
    if gaps:
        st.subheader("Intelligence gaps")
        for gap in gaps:
            st.markdown(f"- {gap}")

    # ── Sources ─────────────────────────────────────────────
    with st.expander(f"All sources ({len(report.get('source_urls', []))})"):
        for url in report.get("source_urls", []):
            st.markdown(f"- [{url}]({url})", unsafe_allow_html=True)


def _render_claim(claim: dict, flagged: bool = False):
    lvl, col = _conf_label(claim["confidence"])
    border = "#D85A30" if flagged else col
    urls   = claim.get("source_urls", [])
    src_html = " ".join(
        f'<a href="{u}" target="_blank" style="font-size:11px;color:#185FA5">[src]</a>'
        for u in urls[:3]
    )
    text = re.sub(
        r'\[SOURCE: (https?://[^\]]+)\]',
        r'<a href="\1" target="_blank" style="font-size:11px;color:#185FA5">[src]</a>',
        claim["text"]
    )
    st.markdown(
        f"""<div style='border-left:3px solid {border};padding:6px 12px;margin:4px 0;'>
        <span style='font-size:14px'>{text}</span> {src_html}
        <span style='color:{col};font-size:11px;margin-left:6px'>{claim['confidence']:.0%}</span>
        {"<span style='color:#D85A30;font-size:11px'> ⚠ flagged</span>" if flagged else ""}
        </div>""",
        unsafe_allow_html=True,
    )
