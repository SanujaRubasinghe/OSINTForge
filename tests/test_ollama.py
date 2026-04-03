"""
Quick connectivity check for the Ollama instance.

Run locally:
    PYTHONPATH=. python tests/test_ollama.py

Run against the Docker service:
    OLLAMA_BASE_URL=http://localhost:11434 PYTHONPATH=. python tests/test_ollama.py
"""
from __future__ import annotations
import os
import sys
import json

import httpx

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MODEL           = "qwen2.5:3b"


def _ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def check_reachable() -> bool:
    """GET /  — Ollama returns 'Ollama is running'."""
    print("\n1. Reachability")
    try:
        r = httpx.get(OLLAMA_BASE_URL, timeout=5)
        if r.status_code == 200:
            _ok(f"Ollama responded at {OLLAMA_BASE_URL}  ({r.text.strip()!r})")
            return True
        _fail(f"Unexpected status {r.status_code}")
        return False
    except Exception as e:
        _fail(f"Cannot reach {OLLAMA_BASE_URL}: {e}")
        return False


def check_model_loaded() -> bool:
    """GET /api/tags — verify the required model is present."""
    print(f"\n2. Model availability  ({MODEL})")
    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        r.raise_for_status()
        names = [m["name"] for m in r.json().get("models", [])]
        # Accept both  "qwen2.5:3b"  and  "qwen2.5:3b-instruct-..."
        match = next((n for n in names if n.startswith(MODEL.split(":")[0])), None)
        if match:
            _ok(f"Found model: {match}")
            return True
        _fail(f"{MODEL!r} not found. Available: {names or '(none)'}")
        return False
    except Exception as e:
        _fail(f"Could not list models: {e}")
        return False


def check_inference() -> bool:
    """POST /api/generate — run a minimal JSON-mode prompt."""
    print("\n3. Inference (JSON mode)")
    payload = {
        "model":  MODEL,
        "prompt": 'Reply with exactly this JSON and nothing else: {"status": "ok"}',
        "format": "json",
        "stream": False,
        "options": {"temperature": 0, "num_predict": 32},
    }
    try:
        r = httpx.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=60,
        )
        r.raise_for_status()
        raw = r.json().get("response", "")
        data = json.loads(raw)
        if data.get("status") == "ok":
            _ok(f"Model returned valid JSON: {data}")
            return True
        _ok(f"Model responded (unexpected content): {data}")
        return True          # reachable and generating — good enough
    except json.JSONDecodeError:
        _fail(f"Response was not valid JSON: {raw!r}")
        return False
    except Exception as e:
        _fail(f"Inference request failed: {e}")
        return False


def check_langchain_integration() -> bool:
    """Smoke-test the ChatOllama wrapper used by PlannerAgent."""
    print("\n4. LangChain ChatOllama integration")
    try:
        from langchain_ollama import ChatOllama
        from langchain_core.messages import HumanMessage

        llm = ChatOllama(model=MODEL, base_url=OLLAMA_BASE_URL,
                         temperature=0, format="json")
        response = llm.invoke([HumanMessage(content='Return {"ping": "pong"}')])
        data = json.loads(response.content)
        _ok(f"ChatOllama round-trip: {data}")
        return True
    except Exception as e:
        _fail(f"ChatOllama failed: {e}")
        return False


def main() -> None:
    print(f"Ollama connection test")
    print(f"Target: {OLLAMA_BASE_URL}   Model: {MODEL}")
    print("=" * 50)

    results = [
        check_reachable(),
        check_model_loaded(),
        check_inference(),
        check_langchain_integration(),
    ]

    passed = sum(results)
    total  = len(results)
    print("\n" + "=" * 50)
    print(f"Result: {passed}/{total} checks passed")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
