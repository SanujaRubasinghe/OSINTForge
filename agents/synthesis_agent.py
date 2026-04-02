from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
import os

from anthropic import Anthropic

from orchestrator.state import OSINTState, OSINTReport, ClaimRecord


SYNTHESIS_PROMPT = """You are an OSINT synthesis analyst. You will receive:
1. A target entity name
2. A list of extracted entities with confidence scores
3. A list of relationships between entities
4. A list of source URLs

Your task: Write a structured intelligence report as a JSON object.

CRITICAL RULES:
- Every claim in the report MUST include a source citation from the provided URLs
- Format citations inline as [SOURCE: url]
- Do NOT invent facts not supported by the provided data
- If you cannot support a claim with a source, do not include it
- Flag any areas where data is missing or contradictory

Return ONLY a JSON object with this exact schema:
{
  "summary": "2-3 sentence executive summary with [SOURCE: url] citations",
  "claims": [
    {
      "text": "Claim text with [SOURCE: url] inline",
      "source_urls": ["url1", "url2"],
      "confidence": 0.0-1.0
    }
  ],
  "gaps": ["List of areas where intelligence is missing or weak"],
  "confidence_overall": 0.0-1.0
}"""


class SynthesisAgent:
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def run(self, state: OSINTState) -> dict:
        query         = state["query"]
        entities      = state.get("entities", [])
        relationships = state.get("relationships", [])
        findings      = state.get("findings", [])

        # Build context payload for the LLM
        source_urls = list({f["source_url"] for f in findings if f["source_url"]})[:30]

        entity_summary = "\n".join(
            f"- [{e['type']}] {e['name']} (confidence: {e['confidence']:.2f}, sources: {len(e['sources'])})"
            for e in entities[:40]
        )
        rel_summary = "\n".join(
            f"- {r['source_entity_id']} --[{r['label']}]--> {r['target_entity_id']} (conf: {r['confidence']:.2f})"
            for r in relationships[:30]
        )
        sources_text = "\n".join(f"- {url}" for url in source_urls)

        user_content = (
            f"Target: {query}\n\n"
            f"EXTRACTED ENTITIES:\n{entity_summary}\n\n"
            f"RELATIONSHIPS:\n{rel_summary}\n\n"
            f"AVAILABLE SOURCES:\n{sources_text}\n\n"
            "Generate the intelligence report JSON."
        )

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=SYNTHESIS_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            raw = response.content[0].text
            # Strip markdown fences if present
            if raw.strip().startswith("```"):
                raw = raw.strip().split("\n", 1)[1].rsplit("```", 1)[0]

            data = json.loads(raw)

            claims: list[ClaimRecord] = [
                {
                    "id":          str(uuid.uuid4()),
                    "text":        c["text"],
                    "source_urls": c.get("source_urls", []),
                    "confidence":  float(c.get("confidence", 0.5)),
                    "flagged":     False,
                }
                for c in data.get("claims", [])
            ]

            report: OSINTReport = {
                "target":             query,
                "summary":            data.get("summary", ""),
                "entities":           entities,
                "relationships":      relationships,
                "claims":             claims,
                "source_urls":        source_urls,
                "gaps":               data.get("gaps", []),
                "confidence_overall": float(data.get("confidence_overall", 0.5)),
                "generated_at":       datetime.now(timezone.utc).isoformat(),
            }

            return {
                "draft_report": report,
                "status": "synthesising",
                "agent_trace": [{
                    "agent":       "synthesis",
                    "action":      "report_generated",
                    "claim_count": len(claims),
                    "gap_count":   len(data.get("gaps", [])),
                    "confidence":  report["confidence_overall"],
                    "timestamp":   datetime.now(timezone.utc).isoformat(),
                }],
            }

        except Exception as e:
            return {
                "errors": [f"SynthesisAgent error: {e}"],
                "agent_trace": [{"agent": "synthesis", "action": "error", "error": str(e)}],
            }
