from __future__ import annotations
from pathlib import Path
from pyvis.network import Network

from orchestrator.state import EntityRecord, RelationshipRecord


ENTITY_COLORS = {
    "PERSON":   "#534AB7",
    "ORG":      "#0F6E56",
    "DOMAIN":   "#185FA5",
    "IP":       "#993C1D",
    "EMAIL":    "#BA7517",
    "LOCATION": "#3B6D11",
    "EVENT":    "#993556",
}


def export_graph_html(
    entities:      list[EntityRecord],
    relationships: list[RelationshipRecord],
    output_path:   str = "./data/graph_export.html",
    min_confidence: float = 0.3,
) -> str:
    """
    Export a PyVis interactive HTML graph from entities and relationships.
    Returns the path to the generated HTML file.
    """
    net = Network(height="700px", width="100%", bgcolor="#ffffff",
                  font_color="#2C2C2A", directed=True)
    net.set_options("""
    {
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -8000,
          "centralGravity": 0.3,
          "springLength": 130,
          "springConstant": 0.04
        },
        "stabilization": {"iterations": 150}
      },
      "nodes": {
        "font": {"size": 12, "face": "Inter, sans-serif"},
        "borderWidth": 1.5
      },
      "edges": {
        "font": {"size": 9, "face": "Inter, sans-serif"},
        "arrows": {"to": {"enabled": true, "scaleFactor": 0.6}},
        "smooth": {"type": "dynamic"}
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100,
        "hideEdgesOnDrag": true
      }
    }
    """)

    entity_ids: set[str] = set()

    for ent in entities:
        if ent["confidence"] < min_confidence:
            continue
        color  = ENTITY_COLORS.get(ent["type"], "#888780")
        size   = 12 + int(ent["confidence"] * 22)
        cross  = ent.get("attributes", {}).get("cross_referenced", False)
        border = "#EF9F27" if cross else "#ffffff"
        title  = (
            f"<b>{ent['name']}</b><br>"
            f"Type: {ent['type']}<br>"
            f"Confidence: {ent['confidence']:.0%}<br>"
            f"Sources: {len(ent.get('sources', []))}<br>"
            f"{'✓ Cross-referenced' if cross else ''}"
        )
        net.add_node(
            ent["id"],
            label       = ent["name"][:28],
            title       = title,
            color       = {"background": color, "border": border,
                           "highlight": {"background": color, "border": "#EF9F27"}},
            size        = size,
            borderWidth = 2.5 if cross else 1,
            font        = {"color": "#ffffff"},
        )
        entity_ids.add(ent["id"])

    # Build name → id map for string-based relation resolution
    name_to_id = {e["name"].lower(): e["id"] for e in entities if e["id"] in entity_ids}

    edge_count = 0
    for rel in relationships:
        src = rel["source_entity_id"]
        tgt = rel["target_entity_id"]
        if src not in entity_ids:
            src = name_to_id.get(src.lower(), "")
        if tgt not in entity_ids:
            tgt = name_to_id.get(tgt.lower(), "")
        if not (src and tgt and src in entity_ids and tgt in entity_ids):
            continue

        width = 1 + int(rel["confidence"] * 4)
        net.add_edge(
            src, tgt,
            title  = f"{rel['label']} ({rel['confidence']:.0%})\n{rel.get('evidence', '')[:80]}",
            label  = rel["label"].replace("_", " ").lower(),
            width  = width,
            color  = {"color": "#B4B2A9", "highlight": "#534AB7"},
        )
        edge_count += 1

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    net.save_graph(output_path)
    return output_path
