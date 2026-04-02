from __future__ import annotations
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network


ENTITY_COLORS = {
    "PERSON":   "#534AB7",
    "ORG":      "#0F6E56",
    "DOMAIN":   "#185FA5",
    "IP":       "#993C1D",
    "EMAIL":    "#BA7517",
    "LOCATION": "#3B6D11",
    "EVENT":    "#993556",
}

RELATION_COLORS = {
    "WORKS_AT":       "#534AB7",
    "OWNS":           "#0F6E56",
    "HOSTED_BY":      "#185FA5",
    "ARRESTED":       "#993C1D",
    "SUED":           "#D85A30",
    "PARTNERS_WITH":  "#1D9E75",
    "INVESTED_IN":    "#BA7517",
}


def render_graph(report: dict):
    """Build and render the PyVis knowledge graph."""
    if not report:
        st.info("No graph data available yet.")
        return

    entities      = report.get("entities", [])
    relationships = report.get("relationships", [])

    if not entities:
        st.info("No entities to visualise.")
        return

    # ── Controls ────────────────────────────────────────────
    col1, col2 = st.columns(2)
    min_conf   = col1.slider("Min entity confidence", 0.0, 1.0, 0.3, 0.05)
    show_types = col2.multiselect(
        "Entity types to show",
        options=list(ENTITY_COLORS.keys()),
        default=["PERSON", "ORG", "DOMAIN", "EMAIL"],
    )

    # ── Filter entities ─────────────────────────────────────
    filtered_entities = [
        e for e in entities
        if e["confidence"] >= min_conf and e["type"] in show_types
    ]

    if not filtered_entities:
        st.warning("No entities match current filters.")
        return

    entity_ids = {e["id"] for e in filtered_entities}
    # Also index by name for relationship lookup
    name_to_id: dict[str, str] = {e["name"].lower(): e["id"] for e in filtered_entities}

    # ── Build PyVis graph ───────────────────────────────────
    net = Network(height="550px", width="100%", bgcolor="#ffffff", font_color="#2C2C2A")
    net.set_options("""
    {
      "physics": {
        "barnesHut": {"gravitationalConstant": -8000, "springLength": 120},
        "stabilization": {"iterations": 100}
      },
      "nodes": {"font": {"size": 12}},
      "edges": {"font": {"size": 10}, "smooth": {"type": "dynamic"}}
    }
    """)

    for ent in filtered_entities:
        size     = 15 + int(ent["confidence"] * 20)
        color    = ENTITY_COLORS.get(ent["type"], "#888780")
        src_cnt  = len(ent.get("sources", []))
        cross    = ent.get("attributes", {}).get("cross_referenced", False)
        border   = "#ffffff" if not cross else "#EF9F27"
        title    = (
            f"<b>{ent['name']}</b><br>"
            f"Type: {ent['type']}<br>"
            f"Confidence: {ent['confidence']:.0%}<br>"
            f"Sources: {src_cnt}<br>"
            f"{'✓ Cross-referenced' if cross else ''}"
        )
        net.add_node(
            ent["id"],
            label       = ent["name"][:24],
            title       = title,
            color       = {"background": color, "border": border, "highlight": {"border": "#EF9F27"}},
            size        = size,
            borderWidth = 2 if cross else 1,
        )

    # ── Add edges ────────────────────────────────────────────
    edge_count = 0
    for rel in relationships:
        src_id = rel["source_entity_id"]
        tgt_id = rel["target_entity_id"]

        # Try to resolve by name if IDs are name strings (from LLM extraction)
        if src_id not in entity_ids:
            src_id = name_to_id.get(src_id.lower(), "")
        if tgt_id not in entity_ids:
            tgt_id = name_to_id.get(tgt_id.lower(), "")

        if src_id and tgt_id and src_id in entity_ids and tgt_id in entity_ids:
            edge_color = RELATION_COLORS.get(rel["label"], "#B4B2A9")
            width      = 1 + int(rel["confidence"] * 4)
            net.add_edge(
                src_id, tgt_id,
                title  = f"{rel['label']} ({rel['confidence']:.0%})\n{rel.get('evidence', '')[:100]}",
                label  = rel["label"].replace("_", " ").lower(),
                color  = edge_color,
                width  = width,
                arrows = "to",
            )
            edge_count += 1

    # ── Stats ────────────────────────────────────────────────
    st.caption(f"Showing {len(filtered_entities)} entities, {edge_count} relationships")

    # ── Render ───────────────────────────────────────────────
    html = net.generate_html()
    components.html(html, height=580, scrolling=False)

    # ── Legend ───────────────────────────────────────────────
    with st.expander("Legend"):
        cols = st.columns(len(ENTITY_COLORS))
        for i, (etype, col_hex) in enumerate(ENTITY_COLORS.items()):
            cols[i].markdown(
                f"<span style='background:{col_hex};color:#fff;"
                f"padding:2px 8px;border-radius:4px;font-size:12px'>{etype}</span>",
                unsafe_allow_html=True,
            )
