from __future__ import annotations

import json
from datetime import datetime, timezone
import os

from anthropic import Anthropic

from orchestrator.state import OSINTState

CRITIC_PROMPT = """You are a strict OSINT report quality critic.

Review the provided intelligence report and identify:
1. Claims that have NO source citation [SOURCE: url]  
2. Claims that appear to be hallucinated or unsupported
3. Contradictions between different claims
4. Critical intelligence gaps that could be filled with more collection

Return a JSON object:
{
  "has_issues": true/false,
  "unsupported_claims": ["claim text that has no citation"],
  "contradictions": ["description of contradiction"],
  "collection_gaps": ["specific gap — e.g. No DNS data found", "No financial records"],
  "overall_assessment": "brief assessment",
  "pass": true/false
}

If the report is well-grounded and complete, return {"has_issues": false, "pass": true, ...}"""


class CriticAgent:
    CONFIDENCE_THRESHOLD = 0.65

    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def run(self, state: OSINTState) -> dict:
        draft = state.get("draft_report")
        if not draft:
            return {
                "critic_feedback": "No draft report to review.",
                "agent_trace": [{"agent": "critic", "action": "no_draft"}],
            }

        refinement_count = state.get("refinement_count", 0)

        # Serialise the report for review
        report_text = (
            f"SUMMARY:\n{draft['summary']}\n\n"
            f"CLAIMS:\n" + "\n".join(f"- {c['text']}" for c in draft.get("claims", [])) + "\n\n"
            "GAPS NOTED BY SYNTHESIS:\n" + "\n".join(draft.get("gaps", [])) + "\n\n"
            f"OVERALL CONFIDENCE: {draft.get('confidence_overall', 0)}"
        )

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=CRITIC_PROMPT,
                messages=[{"role": "user", "content": f"Review this report:\n\n{report_text}"}],
            )
            raw = response.content[0].text.strip()

            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            # Extract the JSON object even if there is trailing text
            brace = raw.find("{")
            if brace != -1:
                raw = raw[brace:]
            last = raw.rfind("}")
            if last != -1:
                raw = raw[: last + 1]

            critique = json.loads(raw)

            passed = critique.get("pass", False)
            has_issues = critique.get("has_issues", True)

            # Build a gap description string for re-planning
            gaps = critique.get("collection_gaps", [])
            unsupported = critique.get("unsupported_claims", [])
            feedback = ""

            if not passed and has_issues and refinement_count < 3:
                parts = []
                if gaps:
                    parts.append("Missing data: " + "; ".join(gaps))
                if unsupported:
                    parts.append("Unsupported claims need evidence: " + "; ".join(unsupported[:3]))
                feedback = "\n".join(parts)

                # Flag unsupported claims in the draft
                if draft.get("claims"):
                    for claim in draft["claims"]:
                        if any(claim["text"][:50] in u for u in unsupported):
                            claim["flagged"] = True

            return {
                "critic_feedback": feedback,
                "draft_report":    draft,          # updated with flagged claims
                "refinement_count": refinement_count + 1,
                "agent_trace": [{
                    "agent":       "critic",
                    "action":      "review_complete",
                    "passed":      passed,
                    "has_issues":  has_issues,
                    "gaps_found":  len(gaps),
                    "unsupported": len(unsupported),
                    "feedback":    feedback[:200] if feedback else "None",
                    "timestamp":   datetime.now(timezone.utc).isoformat(),
                }],
            }

        except Exception as e:
            # On critic failure — don't block, just pass through
            return {
                "critic_feedback": "",
                "errors": [f"CriticAgent error: {e}"],
                "agent_trace": [{"agent": "critic", "action": "error", "error": str(e)}],
            }
