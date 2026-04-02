from __future__ import annotations
import pytest
import respx
import httpx
from agents.web_collector_agent import WebCollectorAgent


@pytest.fixture
def agent():
    return WebCollectorAgent()


@respx.mock
@pytest.mark.asyncio
async def test_fetch_page_extracts_text(agent):
    url = "https://example.com/test"
    respx.get(url).mock(return_value=httpx.Response(
        200,
        text="<html><head><title>Test Page</title></head>"
             "<body><p>Acme Corp is a leading company.</p></body></html>",
    ))
    result = await agent._fetch_one(
        httpx.AsyncClient(base_url="https://example.com"), url
    )
    assert result is not None
    assert "Acme Corp" in result["raw_text"]
    assert result["title"] == "Test Page"
    assert result["source_type"] == "web"


@respx.mock
@pytest.mark.asyncio
async def test_fetch_page_handles_404(agent):
    url = "https://example.com/missing"
    respx.get(url).mock(return_value=httpx.Response(404))
    result = await agent._fetch_one(
        httpx.AsyncClient(base_url="https://example.com"), url
    )
    assert result is None


def test_email_extraction(agent):
    text = "Contact us at info@acme.com or support@acme.org for help."
    emails = agent._extract_emails(text)
    assert "info@acme.com" in emails
    assert "support@acme.org" in emails


def test_deduplication_removes_identical_urls(agent):
    from orchestrator.state import FindingRecord
    import uuid

    def make_finding(url: str, text: str) -> FindingRecord:
        return {
            "id": str(uuid.uuid4()), "source_type": "web",
            "source_url": url, "raw_text": text,
            "title": "test", "timestamp": "", "metadata": {},
        }

    f1 = make_finding("https://a.com", "Acme Corp founded in 2010 by John Doe")
    f2 = make_finding("https://a.com", "Acme Corp founded in 2010 by John Doe")  # duplicate URL
    f3 = make_finding("https://b.com", "Completely different content about something else")

    agent._seen.clear()
    agent._lsh = __import__("datasketch").MinHashLSH(threshold=0.7, num_perm=128)

    result = agent._deduplicate([f1, f2, f3])
    urls = [r["source_url"] for r in result]
    assert urls.count("https://a.com") == 1
    assert "https://b.com" in urls
