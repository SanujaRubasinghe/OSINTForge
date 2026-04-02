# OSINTForge

**Multi-agent LLM swarm for automated Open Source Intelligence synthesis**

A production-grade OSINT platform that dispatches a coordinated swarm of
specialised AI agents to collect, extract, cross-reference, and synthesise
intelligence from 15+ public data sources into a structured, citation-linked report.

---

## Architecture

```
User query
    │
    ▼
PlannerAgent  ──────────────────────────────────────┐
(LangGraph StateGraph)                              │
    │                                               │
    ├─► WebCollectorAgent    ──┐                    │
    ├─► DNSAgent             ──┤                    │
    ├─► GitHubAgent          ──┼─► EntityExtractor  │
    ├─► NewsAgent            ──┤     │              │
    ├─► RedditAgent          ──┤     ▼              │
    ├─► EmailAgent           ──┘  CrossRef          │
    └─► LegalAgent                 │                │
                                   ▼                │
                            SynthesisAgent          │
                                   │                │
                                   ▼                │
                             CriticAgent ───────────┘
                             (max 3 refinement passes)
                                   │
                                   ▼
                            Final OSINTReport
                            (entities, claims, citations, gaps)
```

## Key features

- **10 specialised agents** — each owns a distinct intelligence source
- **LangGraph orchestration** — stateful cycles, human-in-the-loop gates, PostgreSQL checkpointing
- **Self-critique loop** — CriticAgent reviews every synthesis draft and triggers targeted re-collection
- **Citation-grounded claims** — every claim in the final report cites a source URL; unflagged claims are rejected
- **Knowledge graph** — Kuzu embedded graph stores all entity-relationship triples for neighbourhood traversal
- **Image intelligence** — EXIF GPS extraction, multimodal LLM scene analysis, OCR, and reverse image search
- **Confidence scoring** — source-type weighted, cross-reference boosted confidence per entity and claim
- **FastAPI + SSE** — stream live agent traces to the UI as each step completes
- **Streamlit dashboard** — three-panel UI: structured report, interactive knowledge graph, agent trace viewer

## Intelligence sources

| Route | Sources |
|---|---|
| Web surface | DuckDuckGo, SerpAPI, Crunchbase, Wayback Machine |
| News & events | GDELT, NewsAPI, RSS feeds, Semantic Scholar, arXiv |
| Social | Reddit API, Pastebin/paste sites |
| Documents | SEC EDGAR, UK Companies House, OpenCorporates, CourtListener |
| Sanctions | OFAC SDN list, OpenSanctions PEP database |
| DNS & network | WHOIS, DNS records, crt.sh CT logs, Shodan |
| GitHub | Org members, repo metadata, commit emails, secret scanning |
| Email | Hunter.io domain search, HIBP breach database |
| Geospatial | Nominatim geocoding, OSM Overpass, GSV metadata |
| Image intel | EXIF, Yandex reverse search, Claude Vision, Tesseract OCR |

## Tech stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph, LangChain |
| Local LLM | Ollama + qwen2.5:14b |
| Synthesis & critic | Anthropic Claude Sonnet |
| NLP | spaCy en_core_web_trf, sentence-transformers |
| Deduplication | datasketch MinHash LSH |
| Knowledge graph | Kuzu (embedded), PyVis |
| API | FastAPI, SSE-Starlette |
| UI | Streamlit |
| Storage | PostgreSQL, Redis |
| Containers | Docker Compose |
| CI/CD | GitHub Actions |

## Quick start

```bash
# 1. Clone and configure
git clone https://github.com/yourusername/osintforge
cd osintforge
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY at minimum

# 2. Start the stack
docker compose up --build -d

# 3. Pull the local LLM
docker exec osintforge-ollama-1 ollama pull qwen2.5:3b

# 4. Open the UI
open http://localhost:8501

# 5. Or use the CLI
python run.py --query "Acme Corp" --type org
python run.py --query "acme.com" --type domain --json --output report.json
```

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m spacy download en_core_web_trf

# Start only infrastructure
docker compose up postgres redis ollama -d

# Run API
uvicorn api.main:app --reload

# Run UI
streamlit run ui/app.py

# Run tests
pytest
```

## Project structure

```
osintforge/
├── agents/          # 10 LangGraph agent nodes
├── orchestrator/    # StateGraph, router, state TypedDict, checkpointer
├── collectors/      # Thin async I/O clients (no LLM logic)
├── nlp/             # spaCy NER, embeddings, dedup, relation extraction
│   └── image_intel/ # EXIF, OCR, reverse search, logo detection
├── knowledge_graph/ # Kuzu graph store, schema, PyVis export
├── synthesis/       # Report builder, citation linker, confidence scorer
├── api/             # FastAPI routes and Pydantic schemas
├── ui/              # Streamlit app and components
├── tests/           # pytest test suite
└── configs/         # YAML config + LLM prompt files
```

## Evaluation results (demo corpus — 10 public entities)

| Metric | Result |
|---|---|
| Entity recall | 78% |
| Relation F1 | 0.61 |
| Citation grounding rate | 89% |
| Critic pass rate (1st draft) | 62% |
| Avg end-to-end latency | 4m 12s |
| Sources per report | 24 avg |

## Ethical scope

This system collects only publicly available information. It does not:
- Perform facial recognition or biometric identification
- Access authenticated accounts or private data
- Bypass robots.txt or ToS restrictions
- Store personal data beyond the active session

Image analysis is scoped to metadata, scene context, and text extraction.

## Licence

MIT
