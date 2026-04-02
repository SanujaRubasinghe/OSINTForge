from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from orchestrator.state import EntityRecord, OSINTState

SOURCE_TYPE_WEIGHTS = {
    "sec_edgar":              0.35,
    "companies_house":        0.35,
    "whois":                  0.30,
    "github_org":             0.25,
    "github_user":            0.20,
    "certificate_transparency": 0.20,
    "gdelt_news":             0.15,
    "newsapi":                0.15,
    "rss":                    0.10,
    "web":                    0.10,
    "reddit":                 0.08,
    "github_secret_scan":     0.25,  # risk findings
}


class CrossReferenceAgent:
    def run(self, state: OSINTState) -> dict:
        entities = state.get("entities", [])
        findings = state.get("findings", [])

        if not entities:
            return {"agent_trace": [{"agent": "crossref", "action": "no_entities"}]}

        # ── Group entities by normalised name ────────────────
        name_groups: dict[str, list[EntityRecord]] = defaultdict(list)
        for ent in entities:
            key = f"{ent['type']}:{ent['name'].lower().strip()}"
            name_groups[key].append(ent)

        # ── Build source-type lookup from findings ───────────
        url_to_source_type: dict[str, str] = {
            f["source_url"]: f["source_type"] for f in findings
        }

        # ── Merge duplicates and score confidence ────────────
        merged: list[EntityRecord] = []
        cross_ref_count = 0

        for key, group in name_groups.items():
            if not group:
                continue

            # Merge all sources
            all_sources = list({src for e in group for src in e["sources"]})
            source_types = list({url_to_source_type.get(s, "web") for s in all_sources})

            # Base confidence = highest in group
            base = max(e["confidence"] for e in group)

            # Cross-reference boost: each unique independent source adds weight
            boost = sum(SOURCE_TYPE_WEIGHTS.get(st, 0.05) for st in source_types)
            boost = min(boost, 0.4)  # cap total boost

            final_confidence = min(1.0, base + boost)

            if len(all_sources) > 1:
                cross_ref_count += 1

            representative = group[0]
            merged.append({
                **representative,
                "sources":    all_sources,
                "confidence": round(final_confidence, 3),
                "attributes": {
                    **representative.get("attributes", {}),
                    "cross_referenced":    len(all_sources) > 1,
                    "source_types":        source_types,
                    "independent_sources": len(all_sources),
                },
            })

        # Sort by confidence descending
        merged.sort(key=lambda e: e["confidence"], reverse=True)

        return {
            "entities": merged,
            "agent_trace": [{
                "agent":            "crossreference",
                "action":           "cross_referenced",
                "total_entities":   len(merged),
                "cross_ref_count":  cross_ref_count,
                "high_confidence":  sum(1 for e in merged if e["confidence"] >= 0.8),
                "timestamp":        datetime.now(timezone.utc).isoformat(),
            }],
        }
