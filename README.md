# OSINTForge

A multi-agent LLM swarm for automated open-source intelligence (OSINT) synthesis. Submit a target entity — organisation, person, domain, or topic — and a coordinated pipeline of specialised agents collects, extracts, cross-references, and synthesises publicly available intelligence into a structured, source-cited report.

---

## How it works

```
                      ┌─────────────┐
   optional image ───►│ Image Intel │ (Claude Vision — EXIF, OCR, scene analysis)
                      └──────┬──────┘
                             │
                      ┌──────▼──────┐
                      │   Planner   │  qwen2.5:3b — breaks target into typed tasks
                      └──────┬──────┘
                             │  parallel fan-out
          ┌──────────┬───────┴────────┬──────────┐
          ▼          ▼                ▼           ▼
       Web         DNS            GitHub        News
     Collector    Agent           Agent         Agent
          └──────────┴───────┬────────┴──────────┘
                             │  merge (all complete)
                      ┌──────▼──────┐
                      │   Entity    │  spaCy en_core_web_trf + qwen2.5:3b
                      │  Extractor  │
                      └──────┬──────┘
                      ┌──────▼──────┐
                      │Cross-Refer- │
                      │   ence      │
                      └──────┬──────┘
                      ┌──────▼──────┐
                      │  Synthesis  │  Claude Sonnet — JSON report with citations
                      └──────┬──────┘
                      ┌──────▼──────┐
                      │   Critic    │  Claude Sonnet — validates, flags gaps
                      └──────┬──────┘
                    pass?     │    fail (max 3x)
                      ┌───yes─┘└─no──► re-plan
                      ▼
                  ┌──────────┐
                  │ Finalise │
                  └──────────┘
```

### Agent roles

| Agent | Model | What it does |
|---|---|---|
| **Image Intel** | Claude Sonnet (vision) | EXIF GPS, Tesseract OCR, scene/logo analysis via multimodal LLM |
| **Planner** | qwen2.5:3b (Ollama) | Decomposes target into typed collection tasks (`web`, `dns`, `github`, `news`) |
| **Web Collector** | — | DuckDuckGo search + async HTML scraping, MinHash LSH deduplication |
| **DNS Agent** | — | DNS records, WHOIS, certificate transparency via crt.sh |
| **GitHub Agent** | — | Org/user enumeration, repo metadata, commit email harvesting, secret-pattern scanning |
| **News Agent** | — | GDELT, NewsAPI, RSS feeds (Reuters, BBC) |
| **Entity Extractor** | spaCy + qwen2.5:3b | NER for persons/orgs/locations/emails + relation triple extraction |
| **Cross-Reference** | — | Deduplicates entities across sources, boosts confidence on corroboration |
| **Synthesis** | Claude Sonnet | Writes JSON intelligence report with inline `[SOURCE: url]` citations |
| **Critic** | Claude Sonnet | Validates citation coverage, detects hallucinations, identifies collection gaps |
| **Finalise** | — | Promotes draft to `final_report`, marks run `done` |

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | |
| [Ollama](https://ollama.com) | For local LLM inference |
| `qwen2.5:3b` model | `ollama pull qwen2.5:3b` |
| Anthropic API key | For Synthesis, Critic, and Image Intel agents |

---

## Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd OSINTForge

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
PYTHONPATH=. python -m spacy download en_core_web_trf
```

### 2. Configure credentials

Create a `.env` file in the project root:

```dotenv
# ── Required ────────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...

# ── Optional (collectors degrade gracefully without these) ──
GITHUB_TOKEN=github_pat_...          # removes GitHub rate limits
NEWSAPI_KEY=...                      # NewsAPI article search
SHODAN_API_KEY=...                   # Shodan host scanning
COMPANIES_HOUSE_KEY=...              # UK Companies House
HUNTER_API_KEY=...                   # Hunter.io email discovery (disabled by default)
SERPAPI_API_KEY=...                  # SerpAPI web search fallback
```

### 3. Pull the local LLM

```bash
ollama pull qwen2.5:3b
```

---

## Running

### CLI

```bash
PYTHONPATH=. python run.py --query "Acme Corp" --type org
PYTHONPATH=. python run.py --query "john.doe@example.com" --type person
PYTHONPATH=. python run.py --query "acme.com" --type domain
PYTHONPATH=. python run.py --query "ransomware-as-a-service 2024" --type topic

# With image intelligence
PYTHONPATH=. python run.py --query "Acme Corp" --type org --image ./photo.jpg

# Output as JSON / save to file
PYTHONPATH=. python run.py --query "Acme Corp" --type org --json --output report.json
```

### Web UI + API (local)

```bash
# Terminal 1 — API server
PYTHONPATH=. uvicorn api.main:app --reload --port 8000

# Terminal 2 — Streamlit UI
PYTHONPATH=. streamlit run ui/app.py
```

Open [http://localhost:8501](http://localhost:8501).

### Docker Compose (full stack)

```bash
# First run — build images, start services, pull LLM
docker compose up --build -d
docker compose exec ollama ollama pull qwen2.5:3b

# Subsequent runs
docker compose up -d
```

The `./` directory is bind-mounted into the `api` and `ui` containers, so code changes are reflected immediately without a rebuild. Only `Dockerfile` or `requirements.txt` changes require `docker compose build`.

Services:

| Service | URL | Description |
|---|---|---|
| Streamlit UI | http://localhost:8501 | Web dashboard |
| FastAPI | http://localhost:8000 | REST API + SSE stream |
| Ollama | http://localhost:11434 | Local LLM server |
| PostgreSQL | localhost:5432 | LangGraph checkpoint store |
| Redis | localhost:6379 | Task queue (async workers) |

---

## Project layout

```
OSINTForge/
│
├── agents/                        # LangGraph node implementations
│   ├── planner_agent.py
│   ├── web_collector_agent.py
│   ├── dns_agent.py
│   ├── github_agent.py
│   ├── news_agent.py
│   ├── entity_extractor_agent.py
│   ├── crossreference_agent.py
│   ├── synthesis_agent.py
│   ├── critic_agent.py
│   └── image_intel_agent.py
│
├── orchestrator/
│   ├── graph.py                   # StateGraph wiring
│   ├── state.py                   # OSINTState TypedDict and all record types
│   └── router.py                  # Conditional edge routing functions
│
├── nlp/
│   └── relation_extractor.py      # Standalone (subject, relation, object) extractor
│
├── collectors/                    # Low-level async data clients
│   ├── dns_whois.py
│   ├── certificate_intel.py
│   ├── geo_intel.py
│   └── ...
│
├── api/
│   ├── main.py                    # FastAPI app factory
│   ├── schemas.py                 # Pydantic request/response models
│   └── routes/
│       ├── query.py               # POST /query/, GET /{id}/status, GET /{id}/stream
│       └── report.py              # GET /report/{id}
│
├── ui/
│   ├── app.py                     # Streamlit app (sidebar + three-panel tabs)
│   └── components/
│       ├── report_view.py         # Structured report renderer
│       ├── graph_view.py          # Knowledge graph visualisation (PyVis)
│       └── agent_trace.py         # Step-by-step trace viewer
│
├── configs/
│   ├── agents.yaml                # Model names, timeouts, token limits
│   └── collectors.yaml            # Per-collector enable/disable + rate limits
│
├── tests/
├── run.py                         # CLI entry point
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## Configuration

### Enable / disable collectors — `configs/collectors.yaml`

```yaml
web:     { enabled: true  }
dns:     { enabled: true  }
github:  { enabled: true,  secret_scan_enabled: true }
news:    { enabled: true,  days_back: 90 }
reddit:  { enabled: false }   # requires REDDIT_CLIENT_ID
email:   { enabled: false }   # requires HUNTER_API_KEY
geo:     { enabled: false }   # requires GOOGLE_MAPS_KEY
shodan:  { enabled: false }   # requires SHODAN_API_KEY
legal:   { enabled: true  }   # Companies House, OFAC, SEC EDGAR
wayback: { enabled: true  }
```

Disabled collectors are skipped gracefully; they do not affect the graph topology.

### Change models — `configs/agents.yaml`

```yaml
planner:
  model: qwen2.5:3b            # any model available in your Ollama instance

synthesis:
  model: claude-sonnet-4-20250514

critic:
  model: claude-sonnet-4-20250514
  max_refinement_passes: 3     # critic → re-plan loop limit before forced finalise
```

---

## API reference

### Submit a query

```http
POST /query/
Content-Type: application/json

{ "query": "Acme Corp", "target_type": "org" }
```

`target_type`: `org` | `person` | `domain` | `topic`

### Submit with image

```http
POST /query/with-image
Content-Type: multipart/form-data

query=Acme Corp
target_type=org
image=<file>
```

### Poll status

```http
GET /query/{task_id}/status
```

### Stream agent trace (Server-Sent Events)

```http
GET /query/{task_id}/stream
Accept: text/event-stream
```

Events: `trace_step` (each agent step), `done`, `error`

### Fetch completed report

```http
GET /report/{task_id}
```

```json
{
  "task_id": "...",
  "status": "done",
  "report": {
    "target": "Acme Corp",
    "summary": "...",
    "entities": [...],
    "relationships": [...],
    "claims": [{ "text": "...", "source_urls": [...], "confidence": 0.87 }],
    "source_urls": [...],
    "gaps": [...],
    "confidence_overall": 0.81
  },
  "agent_trace": [...],
  "errors": []
}
```

---

## State model

All agents read and write a single `OSINTState` TypedDict threaded through the graph:

```python
class OSINTState(TypedDict):
    query: str
    target_type: str
    input_image_path: Optional[str]
    collection_tasks: list[CollectionTask]        # planner output
    findings: Annotated[list[FindingRecord], operator.add]     # parallel append
    entities: Annotated[list[EntityRecord], operator.add]      # parallel append
    relationships: Annotated[list[RelationshipRecord], operator.add]
    draft_report: Optional[OSINTReport]
    critic_feedback: Optional[str]
    refinement_count: int                         # 0–3
    final_report: Optional[OSINTReport]
    errors: Annotated[list[str], operator.add]
    agent_trace: Annotated[list[dict], operator.add]
    status: str                                   # planning|collecting|extracting|synthesising|done|failed
```

Fields annotated with `operator.add` are safe for parallel writes — LangGraph merges them rather than overwriting.

---

## Ethical use

OSINTForge collects only from **publicly available sources**. It does not:

- Attempt to access authenticated systems or private data
- Perform facial recognition or biometric identification on images
- Use paid people-search or data-broker services
- Bypass `robots.txt` or platform terms of service

Image analysis is limited to metadata (EXIF), scene context, text extraction (OCR), and logo detection. No individual identification is attempted.

Use responsibly and in compliance with applicable laws.

---

## Licence

MIT
