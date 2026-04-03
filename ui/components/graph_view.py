from __future__ import annotations
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network
import json


ENTITY_COLORS = {
    "PERSON":   {"bg": "#00ff88", "border": "#00cc6a", "font": "#0a0e17"},
    "ORG":      {"bg": "#00d4ff", "border": "#00a8cc", "font": "#0a0e17"},
    "DOMAIN":   {"bg": "#7b2fff", "border": "#5c1fcc", "font": "#ffffff"},
    "IP":       {"bg": "#ff3366", "border": "#cc1a44", "font": "#ffffff"},
    "EMAIL":    {"bg": "#ff9500", "border": "#cc7700", "font": "#0a0e17"},
    "LOCATION": {"bg": "#39ff14", "border": "#2acc10", "font": "#0a0e17"},
    "EVENT":    {"bg": "#ff2d78", "border": "#cc1a55", "font": "#ffffff"},
}

RELATION_COLORS = {
    "WORKS_AT":       "#00ff88",
    "OWNS":           "#00d4ff",
    "HOSTED_BY":      "#7b2fff",
    "ARRESTED":       "#ff3366",
    "SUED":           "#ff6b35",
    "PARTNERS_WITH":  "#39ff14",
    "INVESTED_IN":    "#ff9500",
    "FOUNDED":        "#00ffcc",
    "ACQUIRED":       "#ff00aa",
    "LOCATED_IN":     "#aaffdd",
    "LEADS":          "#ffdd00",
    "EMPLOYED_BY":    "#00bbff",
    "MENTIONED_WITH": "#556677",
}

_GRAPH_OPTIONS = json.dumps({
    "physics": {
        "barnesHut": {
            "gravitationalConstant": -12000,
            "centralGravity": 0.3,
            "springLength": 160,
            "springConstant": 0.04,
            "damping": 0.09,
        },
        "stabilization": {"iterations": 150, "fit": True},
    },
    "nodes": {
        "font": {"size": 13, "face": "monospace"},
        "shape": "dot",
        "shadow": {"enabled": True, "color": "rgba(0,255,136,0.4)", "size": 12},
    },
    "edges": {
        "font": {"size": 10, "face": "monospace", "color": "#7a8fa6", "align": "middle"},
        "smooth": {"type": "curvedCW", "roundness": 0.2},
        "shadow": {"enabled": True, "color": "rgba(0,212,255,0.3)", "size": 6},
        "arrows": {"to": {"enabled": True, "scaleFactor": 0.6}},
    },
    "interaction": {
        "hover": True,
        "tooltipDelay": 100,
        "navigationButtons": False,
        "keyboard": {"enabled": True},
    },
    "background": {"color": "#0a0e17"},
})


def render_graph(report: dict):
    if not report:
        st.markdown(
            "<div style='color:#00ff88;font-family:monospace;padding:20px'>"
            "> NO GRAPH DATA IN BUFFER</div>",
            unsafe_allow_html=True,
        )
        return

    all_entities  = report.get("entities", [])
    relationships = report.get("relationships", [])

    if not all_entities:
        st.markdown(
            "<div style='color:#ff3366;font-family:monospace;padding:20px'>"
            "> ENTITY REGISTRY EMPTY — NO NODES TO RENDER</div>",
            unsafe_allow_html=True,
        )
        return

    # ── Controls ─────────────────────────────────────────────
    st.markdown(
        "<p style='font-family:monospace;color:#00d4ff;font-size:12px;"
        "letter-spacing:2px;margin-bottom:4px'>// FILTER PARAMETERS</p>",
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns(2)
    min_conf   = col1.slider("Min confidence threshold", 0.0, 1.0, 0.3, 0.05,
                              help="Nodes below this confidence are hidden")
    show_types = col2.multiselect(
        "Entity types",
        options=list(ENTITY_COLORS.keys()),
        default=["PERSON", "ORG", "DOMAIN", "EMAIL"],
    )

    # ── Filter visible nodes ─────────────────────────────────
    filtered_entities = [
        e for e in all_entities
        if e["confidence"] >= min_conf and e["type"] in show_types
    ]

    if not filtered_entities:
        st.markdown(
            "<div style='color:#ff9500;font-family:monospace;padding:12px'>"
            "> WARNING: NO ENTITIES MATCH CURRENT FILTER PARAMETERS</div>",
            unsafe_allow_html=True,
        )
        return

    visible_ids: set[str] = {e["id"] for e in filtered_entities}

    # Build name→id lookup from ALL entities (unfiltered) so relationship
    # endpoints that got filtered out can still be resolved before the
    # edge-visibility check
    all_name_to_id: dict[str, str] = {e["name"].lower(): e["id"] for e in all_entities}

    # ── Build graph ──────────────────────────────────────────
    net = Network(height="600px", width="100%", bgcolor="#0a0e17", font_color="#e0e8f0")
    net.set_options(_GRAPH_OPTIONS)

    for ent in filtered_entities:
        cfg      = ENTITY_COLORS.get(ent["type"], {"bg": "#445566", "border": "#334455", "font": "#ffffff"})
        size     = 14 + int(ent["confidence"] * 22)
        src_cnt  = len(ent.get("sources", []))
        cross    = ent.get("attributes", {}).get("cross_referenced", False)
        border   = "#ffdd00" if cross else cfg["border"]

        title = (
            f"<div style='font-family:monospace;background:#0f1520;"
            f"border:1px solid {cfg['bg']};padding:8px;border-radius:4px'>"
            f"<b style='color:{cfg['bg']}'>{ent['name']}</b><br>"
            f"<span style='color:#7a8fa6'>TYPE:</span> <span style='color:#e0e8f0'>{ent['type']}</span><br>"
            f"<span style='color:#7a8fa6'>CONF:</span> <span style='color:#00ff88'>{ent['confidence']:.0%}</span><br>"
            f"<span style='color:#7a8fa6'>SRCS:</span> <span style='color:#e0e8f0'>{src_cnt}</span>"
            + (f"<br><span style='color:#ffdd00'>⬡ CROSS-VERIFIED</span>" if cross else "")
            + "</div>"
        )

        net.add_node(
            ent["id"],
            label       = ent["name"][:22],
            title       = title,
            color       = {
                "background": cfg["bg"],
                "border":     border,
                "highlight":  {"background": cfg["bg"], "border": "#ffdd00"},
                "hover":      {"background": cfg["bg"], "border": "#ffffff"},
            },
            size        = size,
            font        = {"color": cfg["font"], "size": 12, "face": "monospace"},
            borderWidth = 3 if cross else 2,
        )

    # ── Add edges ─────────────────────────────────────────────
    edge_count = 0
    for rel in relationships:
        src_id = rel.get("source_entity_id", "")
        tgt_id = rel.get("target_entity_id", "")

        # Resolve name strings → UUIDs using all-entity lookup
        if src_id not in visible_ids:
            src_id = all_name_to_id.get(src_id.lower(), src_id)
        if tgt_id not in visible_ids:
            tgt_id = all_name_to_id.get(tgt_id.lower(), tgt_id)

        # Only draw edge if both endpoints are visible
        if src_id not in visible_ids or tgt_id not in visible_ids:
            continue

        label      = rel.get("label", "RELATED")
        edge_color = RELATION_COLORS.get(label, "#334455")
        conf       = rel.get("confidence", 0.5)
        width      = max(1, int(conf * 4))
        evidence   = rel.get("evidence", "")[:120]

        title = (
            f"<div style='font-family:monospace;background:#0f1520;"
            f"border:1px solid {edge_color};padding:6px;border-radius:4px'>"
            f"<b style='color:{edge_color}'>{label}</b><br>"
            f"<span style='color:#7a8fa6'>CONF:</span> <span style='color:#00ff88'>{conf:.0%}</span>"
            + (f"<br><span style='color:#7a8fa6;font-size:10px'>{evidence}</span>" if evidence else "")
            + "</div>"
        )

        net.add_edge(
            src_id, tgt_id,
            title  = title,
            label  = label.replace("_", " ").lower(),
            color  = {"color": edge_color, "highlight": "#ffdd00", "hover": "#ffffff",
                      "opacity": 0.8},
            width  = width,
        )
        edge_count += 1

    # ── Stats bar ────────────────────────────────────────────
    st.markdown(
        f"<div style='font-family:monospace;font-size:11px;color:#7a8fa6;"
        f"letter-spacing:1px;margin-bottom:6px'>"
        f"NODES: <span style='color:#00ff88'>{len(filtered_entities)}</span>"
        f"  &nbsp;  EDGES: <span style='color:#00d4ff'>{edge_count}</span>"
        f"  &nbsp;  TOTAL_ENTITIES: <span style='color:#7a8fa6'>{len(all_entities)}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Render ───────────────────────────────────────────────
    html = net.generate_html()
    # Force graph background to match theme
    html = html.replace(
        "background-color:#ffffff",
        "background-color:#0a0e17",
    ).replace(
        'body {',
        'body { background-color:#0a0e17; color:#e0e8f0;',
    )
    components.html(html, height=620, scrolling=False)

    # ── Legend ───────────────────────────────────────────────
    with st.expander("// NODE TYPE LEGEND"):
        cols = st.columns(len(ENTITY_COLORS))
        for i, (etype, cfg) in enumerate(ENTITY_COLORS.items()):
            cols[i].markdown(
                f"<span style='background:{cfg['bg']};color:{cfg['font']};"
                f"padding:2px 8px;border-radius:3px;font-size:11px;"
                f"font-family:monospace;font-weight:600'>{etype}</span>",
                unsafe_allow_html=True,
            )
