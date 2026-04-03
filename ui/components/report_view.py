from __future__ import annotations
import streamlit as st
import re


def _conf_badge(score: float) -> tuple[str, str, str]:
    """Returns (label, bg_color, text_color)."""
    if score >= 0.75:
        return "HIGH",   "#00ff88", "#0a0e17"
    elif score >= 0.50:
        return "MEDIUM", "#ff9500", "#0a0e17"
    return "LOW", "#ff3366", "#ffffff"


def _section_header(title: str):
    st.markdown(
        f"<div style='font-family:monospace;font-size:13px;font-weight:700;"
        f"color:#00d4ff;letter-spacing:3px;text-transform:uppercase;"
        f"border-bottom:1px solid #1a2535;padding-bottom:6px;margin:18px 0 10px'>"
        f"// {title}</div>",
        unsafe_allow_html=True,
    )


def render_report(report: dict):
    if not report:
        st.markdown(
            "<div style='font-family:monospace;color:#ff3366;padding:20px'>"
            "> NO REPORT DATA IN BUFFER</div>",
            unsafe_allow_html=True,
        )
        return

    conf     = report.get("confidence_overall", 0)
    label, bg, fg = _conf_badge(conf)

    # ── Header metrics ────────────────────────────────────────
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:12px;margin-bottom:12px'>"
        f"<span style='font-family:monospace;font-size:11px;color:#7a8fa6;"
        f"letter-spacing:2px'>CONFIDENCE:</span>"
        f"<span style='background:{bg};color:{fg};font-family:monospace;"
        f"font-size:11px;font-weight:700;padding:2px 10px;border-radius:3px;"
        f"letter-spacing:2px'>{label} {conf:.0%}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    for col, label_txt, val in [
        (c1, "ENTITIES",  len(report.get("entities", []))),
        (c2, "LINKS",     len(report.get("relationships", []))),
        (c3, "CLAIMS",    len(report.get("claims", []))),
        (c4, "SOURCES",   len(report.get("source_urls", []))),
    ]:
        col.markdown(
            f"<div style='background:#0f1520;border:1px solid #1a2535;"
            f"border-top:2px solid #00d4ff;border-radius:4px;padding:10px;"
            f"text-align:center'>"
            f"<div style='font-family:monospace;font-size:20px;font-weight:700;"
            f"color:#00ff88'>{val}</div>"
            f"<div style='font-family:monospace;font-size:10px;color:#7a8fa6;"
            f"letter-spacing:2px;margin-top:2px'>{label_txt}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Executive Summary ─────────────────────────────────────
    _section_header("Executive Summary")
    summary = report.get("summary", "No summary available.")
    highlighted = re.sub(
        r'\[SOURCE: (https?://[^\]]+)\]',
        r'<a href="\1" target="_blank" style="font-size:11px;color:#00d4ff;'
        r'font-family:monospace">[SRC]</a>',
        summary,
    )
    st.markdown(
        f"<div style='background:#0f1520;border:1px solid #1a2535;"
        f"border-left:3px solid #00ff88;padding:14px;border-radius:4px;"
        f"font-size:14px;line-height:1.7;color:#c8d8e8'>{highlighted}</div>",
        unsafe_allow_html=True,
    )

    # ── Image Intelligence ────────────────────────────────────
    images = report.get("image_results", [])
    if images:
        _section_header("Image Intelligence")
        img_cols = st.columns(len(images))
        for col, img in zip(img_cols, images):
            thumbnail = img.get("thumbnail") or img.get("original", "")
            source    = img.get("source_url", "#")
            title     = img.get("title", "")[:48]
            if thumbnail:
                col.markdown(
                    f"<a href='{source}' target='_blank' style='text-decoration:none'>"
                    f"<div style='background:#0f1520;border:1px solid #1a2535;"
                    f"border-top:2px solid #00d4ff;border-radius:4px;overflow:hidden;"
                    f"transition:border-color 0.2s'>"
                    f"<img src='{thumbnail}' style='width:100%;height:120px;"
                    f"object-fit:cover;display:block' />"
                    f"<div style='padding:5px 6px;font-family:monospace;font-size:10px;"
                    f"color:#7a8fa6;letter-spacing:1px;white-space:nowrap;"
                    f"overflow:hidden;text-overflow:ellipsis'>{title}</div>"
                    f"</div></a>",
                    unsafe_allow_html=True,
                )

    # ── Entities ──────────────────────────────────────────────
    _section_header("Identified Entities")
    entities  = report.get("entities", [])
    type_order = ["PERSON", "ORG", "DOMAIN", "IP", "EMAIL", "LOCATION", "EVENT"]
    TYPE_ICONS = {
        "PERSON": "◈", "ORG": "⬡", "DOMAIN": "◉", "IP": "▣",
        "EMAIL": "◎", "LOCATION": "◆", "EVENT": "◇",
    }
    TYPE_ACCENT = {
        "PERSON": "#00ff88", "ORG": "#00d4ff", "DOMAIN": "#7b2fff",
        "IP": "#ff3366", "EMAIL": "#ff9500", "LOCATION": "#39ff14", "EVENT": "#ff2d78",
    }

    if entities:
        by_type: dict[str, list] = {}
        for e in entities:
            by_type.setdefault(e["type"], []).append(e)

        for etype in type_order:
            group = by_type.get(etype, [])
            if not group:
                continue
            accent = TYPE_ACCENT.get(etype, "#7a8fa6")
            icon   = TYPE_ICONS.get(etype, "◦")
            with st.expander(
                f"{icon} {etype}  [{len(group)}]",
                expanded=etype in ("PERSON", "ORG"),
            ):
                for ent in sorted(group, key=lambda x: x["confidence"], reverse=True):
                    conf_l, conf_bg, conf_fg = _conf_badge(ent["confidence"])
                    src_count = len(ent.get("sources", []))
                    cross_ref = ent.get("attributes", {}).get("cross_referenced", False)
                    st.markdown(
                        f"<div style='display:flex;align-items:center;gap:8px;"
                        f"padding:5px 0;border-bottom:1px solid #1a2535'>"
                        f"<span style='color:{accent};font-family:monospace;font-size:13px'>{icon}</span>"
                        f"<span style='color:#e0e8f0;font-family:monospace;font-size:13px'>{ent['name']}</span>"
                        f"<span style='background:{conf_bg};color:{conf_fg};font-family:monospace;"
                        f"font-size:10px;padding:1px 6px;border-radius:2px;margin-left:4px'>{ent['confidence']:.0%}</span>"
                        f"<span style='color:#334455;font-family:monospace;font-size:10px;margin-left:auto'>"
                        f"{src_count} src{'s' if src_count != 1 else ''}</span>"
                        + (f"<span style='color:#ffdd00;font-family:monospace;font-size:10px'>⬡ VERIFIED</span>"
                           if cross_ref else "")
                        + "</div>",
                        unsafe_allow_html=True,
                    )
    else:
        st.markdown(
            "<div style='font-family:monospace;color:#ff9500'>WARN: NO ENTITIES EXTRACTED</div>",
            unsafe_allow_html=True,
        )

    # ── Intelligence claims ───────────────────────────────────
    _section_header("Intelligence Claims")
    claims   = report.get("claims", [])
    flagged  = [c for c in claims if c.get("flagged")]
    supported = [c for c in claims if not c.get("flagged")]

    if flagged:
        st.markdown(
            f"<div style='background:#1a0810;border:1px solid #ff3366;"
            f"border-left:3px solid #ff3366;padding:8px 12px;border-radius:4px;"
            f"font-family:monospace;font-size:12px;color:#ff3366;margin-bottom:8px'>"
            f"⚠ {len(flagged)} CLAIM(S) FLAGGED — INSUFFICIENT EVIDENCE</div>",
            unsafe_allow_html=True,
        )
        with st.expander("// FLAGGED CLAIMS"):
            for c in flagged:
                _render_claim(c, flagged=True)

    for claim in sorted(supported, key=lambda x: x["confidence"], reverse=True):
        _render_claim(claim)

    # ── Intelligence gaps ─────────────────────────────────────
    gaps = report.get("gaps", [])
    if gaps:
        _section_header("Intelligence Gaps")
        for gap in gaps:
            st.markdown(
                f"<div style='font-family:monospace;font-size:13px;color:#ff9500;"
                f"padding:3px 0'>◦ {gap}</div>",
                unsafe_allow_html=True,
            )

    # ── Sources ───────────────────────────────────────────────
    source_urls = report.get("source_urls", [])
    with st.expander(f"// SOURCE REGISTRY  [{len(source_urls)}]"):
        for url in source_urls:
            st.markdown(
                f"<div style='font-family:monospace;font-size:11px;color:#7a8fa6;"
                f"padding:2px 0'>▸ <a href='{url}' target='_blank' "
                f"style='color:#00d4ff;text-decoration:none'>{url}</a></div>",
                unsafe_allow_html=True,
            )


def _render_claim(claim: dict, flagged: bool = False):
    conf = claim.get("confidence", 0)
    _, conf_bg, conf_fg = _conf_badge(conf)
    border = "#ff3366" if flagged else "#1a2535"
    left_bar = "#ff3366" if flagged else "#00ff88"

    urls = claim.get("source_urls", [])
    src_html = " ".join(
        f'<a href="{u}" target="_blank" style="font-family:monospace;'
        f'font-size:10px;color:#00d4ff;text-decoration:none">[SRC]</a>'
        for u in urls[:3]
    )
    text = re.sub(
        r'\[SOURCE: (https?://[^\]]+)\]',
        r'<a href="\1" target="_blank" style="font-family:monospace;'
        r'font-size:10px;color:#00d4ff;text-decoration:none">[SRC]</a>',
        claim.get("text", ""),
    )
    st.markdown(
        f"<div style='background:#0f1520;border:1px solid {border};"
        f"border-left:3px solid {left_bar};padding:8px 12px;"
        f"margin:4px 0;border-radius:0 4px 4px 0'>"
        f"<span style='font-size:13px;color:#c8d8e8;line-height:1.6'>{text}</span> {src_html}"
        f"<span style='background:{conf_bg};color:{conf_fg};font-family:monospace;"
        f"font-size:10px;padding:1px 6px;border-radius:2px;margin-left:8px'>{conf:.0%}</span>"
        + (f"<span style='color:#ff3366;font-family:monospace;font-size:10px;"
           f"margin-left:6px'>⚠ FLAGGED</span>" if flagged else "")
        + "</div>",
        unsafe_allow_html=True,
    )
