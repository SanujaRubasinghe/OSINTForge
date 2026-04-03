from __future__ import annotations
import asyncio
from datetime import datetime, timezone

from collectors.image_search import fetch_images
from orchestrator.state import OSINTState


class ImageSearchAgent:
    def run(self, state: OSINTState) -> dict:
        query = state["query"]
        try:
            results = asyncio.run(fetch_images(query))
        except Exception as e:
            return {
                "image_results": [],
                "agent_trace": [{"agent": "image_search", "action": "error", "error": str(e)}],
            }

        return {
            "image_results": results,
            "agent_trace": [{
                "agent":     "image_search",
                "action":    "collected",
                "count":     len(results),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }
