# OPS Agent — AI-Driven Multi-Agent Incident Response

An autonomous **multi-agent SRE system** that simulates, detects, analyzes, and resolves
production incidents end-to-end. Five specialized AI agents coordinate through an
orchestrator to run the full incident lifecycle — triage → diagnostics → root-cause
analysis → remediation → external communications — with a human-in-the-loop for risky
actions.

The system ships with a **FastAPI backend** driving a tick-based simulation engine and a
**React + Vite frontend** that visualizes the live agent pipeline.

> For deeper architecture notes and Mermaid diagrams, see [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md).

---
## Frontend

The live dashboard shows the incident queue, the agent pipeline (Triage → Diagnostics →
RCA → Remediation → Comms), root-cause hypothesis, recommended action with approve/deny
gate, agent chatter, live signals, and the system log.
<img width="1920" height="924" alt="image" src="https://github.com/user-attachments/assets/88b76b07-039f-46ec-85f3-2181c09abbcf" />

## Architecture

```
React + Vite frontend (:5173)
        │  /api → proxy
        ▼
FastAPI backend (:8000)  ── api/server.py
        │
        ▼
SimulationEngine  ──►  Orchestrator  ──►  Agent pipeline
   (metrics/logs)        (workflow FSM)
                                │
        ┌───────────────┬───────┴────────┬──────────────┐
     Triage        Diagnostics          RCA          Remediation ─► Comms
                                          │                            │
                                   ChromaDB (RAG)              Slack / Jira
```

### Agent team

| Agent | Role | Key capability |
|:------|:-----|:----------------|
| 🔍 **Triage** | First responder | Symptom extraction, severity (P1/P2/P3), urgency scoring |
| 🔬 **Diagnostics** | Deep analysis | Log pattern correlation, affected-service ID, LLM summaries |
| 🧠 **RCA** | Root cause | RAG search over historical incidents, hypothesis ranking |
| 🛠️ **Remediation** | Action planning | Policy safety checks, playbook selection, approval logic |
| 📡 **Communications** | External notify | Slack alerts (interactive), Jira ticket creation |
| 🎯 **Orchestrator** | Coordinator | Sequential pipeline, feedback loops (low-confidence RCA → re-diagnose) |

---

## Quick start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. (Optional) configure API keys / LLM provider
cp .env .env.local   # or edit .env directly — see Configuration below

# 3. Launch backend + frontend
./start.sh
```

Then open **http://localhost:5173**.

| Option | Command |
|:-------|:--------|
| Backend + frontend | `./start.sh` |
| Backend only (FastAPI on :8000) | `./start.sh --backend` |
| Frontend only (Vite on :5173) | `./start.sh --frontend` |
| Stop everything | `./start.sh --stop` |

The script auto-installs missing FastAPI/uvicorn and frontend `node_modules` on first run.
`run_app.sh` is a simpler equivalent launcher.

---

## Configuration

Settings are read from `.env` (git-ignored). All keys are optional — the system runs fully
with rule-based logic and a mock LLM if nothing is set.

| Variable | Purpose |
|:---------|:--------|
| `LLM_PROVIDER` | `ollama` \| `groq` \| `openai` \| `mock` |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Local Ollama LLM config |
| `GROQ_API_KEY`, `GROQ_MODEL` | Groq-hosted LLM config |
| `OPENAI_API_KEY` | OpenAI LLM config |
| `SLACK_WEBHOOK_URL` | Live Slack incident alerts |
| `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY` | Jira ticket creation |
| `NGROK_AUTH_TOKEN` | Tunnel for Slack interactive callbacks |

When `LLM_PROVIDER` is unset or `mock`, agents fall back to deterministic rule-based
reasoning — no external calls required.

---

## Key API endpoints

The frontend talks to these (`api/server.py`):

| Method | Path | Description |
|:-------|:-----|:------------|
| `GET`  | `/api/state` | Current simulation + agent state |
| `POST` | `/api/tick` | Advance the simulation one tick |
| `POST` | `/api/auto` | Toggle auto-stepping |
| `POST` | `/api/inject` | Inject an incident |
| `POST` | `/api/logs/inject` | Inject raw log lines |
| `POST` | `/api/reanalyze` | Re-run the agent pipeline |
| `POST` | `/api/incidents/{id}/approve` · `/deny` | Human-in-the-loop action gate |
| `GET`  | `/api/events` | Server-sent event stream |
| `GET`  | `/api/history` | Past incidents |
| `GET`/`POST` | `/api/kb` · `/api/kb/ingest` | RAG knowledge base |
| `GET`  | `/api/health` | Health check |

---

## Project structure

```
OPS_agent/
├── api/server.py            # FastAPI bridge: engine + orchestrator → REST/SSE
├── frontend/                # React + Vite dashboard
│   └── src/                 # screens/, components/, api.js, agents.js
├── src/
│   ├── agent/               # Multi-agent system (orchestrator + 5 agents, LLM client, bus)
│   ├── simulation/          # Tick-based engine, incident FSM, metric/log generators
│   ├── detection/           # Rule-based + ML anomaly detection
│   ├── integration/         # Slack, Jira, webhook server
│   ├── orchestration/       # Policy engine (action safety classification)
│   └── rag/                 # ChromaDB vector knowledge base
├── data/
│   ├── historical_incidents.json  # RAG seed corpus
│   └── pending_actions.json       # Slack webhook action queue
├── tests/                   # pytest suites
├── start.sh / run_app.sh    # launchers
└── requirements.txt
```

---

## Tech stack

**Backend:** Python · FastAPI · ChromaDB (RAG) · scikit-learn · LangChain
**Frontend:** React 18 · Vite
**Integrations:** Slack SDK · Jira API · Flask webhook · PyNgrok
**LLM:** pluggable — Ollama / Groq / OpenAI / mock

---

## Tests

```bash
python tests/run_all_tests.py     # full suite
pytest tests/                      # or via pytest
```
