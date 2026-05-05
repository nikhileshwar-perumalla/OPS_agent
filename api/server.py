"""FastAPI bridge to the SimulationEngine + multi-agent orchestrator.

Run: uvicorn api.server:app --reload --port 8000
"""
import asyncio
import json
import os
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel


def _safe(obj, depth=0, seen=None):
    """Strip non-JSON-safe values and break cycles."""
    if seen is None:
        seen = set()
    if depth > 10:
        return None
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    oid = id(obj)
    if oid in seen:
        return None
    if isinstance(obj, dict):
        seen.add(oid)
        out = {}
        for k, v in obj.items():
            try:
                out[str(k)] = _safe(v, depth + 1, seen)
            except Exception:
                out[str(k)] = None
        return out
    if isinstance(obj, (list, tuple, set)):
        seen.add(oid)
        return [_safe(v, depth + 1, seen) for v in obj]
    # Don't dive into arbitrary objects — too risky for cycles. Stringify.
    return str(obj)


def json_response(payload: dict) -> Response:
    return Response(
        content=json.dumps(_safe(payload), default=str),
        media_type="application/json",
    )

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from src.simulation.engine import SimulationEngine, SimulationMode
from src.simulation.observations import FileLogSource
from src.detection.anomaly_model import AnomalyDetector
from src.integration.slack_client import SlackNotifier
from src.integration.jira_client import JiraConnector
from src.agent.orchestrator import OrchestratorAgent
from src.agent.llm_client import LLMClient


class EngineRuntime:
    def __init__(self):
        self.engine = SimulationEngine()
        self.engine.log_source = FileLogSource(str(ROOT / "data" / "app_logs.log"))
        self.engine.detector = AnomalyDetector()
        self.engine.slack_notifier = SlackNotifier(
            webhook_url=os.getenv("SLACK_WEBHOOK_URL"), mock=False
        )
        self.engine.jira_connector = JiraConnector(
            url=os.getenv("JIRA_URL"),
            username=os.getenv("JIRA_USERNAME"),
            token=os.getenv("JIRA_API_TOKEN"),
            project_key=os.getenv("JIRA_PROJECT_KEY", "KAN"),
            mock=False,
        )
        self.engine.set_mode(SimulationMode.SIMULATION)
        self.engine.llm_client = LLMClient()
        self.engine.orchestrator = OrchestratorAgent(
            bus=self.engine.message_bus,
            slack_notifier=self.engine.slack_notifier,
            jira_connector=self.engine.jira_connector,
            llm_client=self.engine.llm_client,
        )
        self.tick_history: list[dict] = []
        self.auto_run = False
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.tick_interval = 2.0

    def snapshot(self) -> dict:
        eng = self.engine
        active = eng.state_tracker.get_active()
        running_id = getattr(eng, "pipeline_running_id", None)

        # Compute per-incident queue state.
        incidents = []
        seen_running = False
        for inc in active:
            data = _serialize_incident(inc)
            if data["analysis"]:
                data["pipeline_state"] = "done"
            elif running_id and data["id"] == running_id:
                data["pipeline_state"] = "running"
                seen_running = True
            else:
                # If something's running already, others are queued.
                # Otherwise this one is itself next-in-line (running soon).
                data["pipeline_state"] = "queued" if seen_running or running_id else "running"
            incidents.append(data)

        # Strip references to analysis from metrics — those would alias incidents'
        # analysis dicts and confuse the cycle-detection in _safe().
        metrics_clean = {k: v for k, v in (eng.metrics or {}).items()
                         if k not in ("latest_analysis", "agent_active")}
        history_clean = [
            {k: v for k, v in (s.get("metrics", {}) or {}).items()
             if k not in ("latest_analysis", "agent_active")}
            for s in self.tick_history[-60:]
        ]

        return {
            "tick": eng.tick_count,
            "mode": eng.mode.value,
            "auto_run": self.auto_run,
            "llm_active": bool(eng.llm_client and eng.llm_client.is_active),
            "pipeline_running_id": running_id,
            "metrics": metrics_clean,
            "metrics_history": history_clean,
            "incidents": incidents,
            "logs": list(eng.system_logs[-80:]),
            "agent_stats": eng.orchestrator.get_agent_stats() if eng.orchestrator else {},
        }

    def step(self) -> dict:
        with self._lock:
            state = self.engine.tick()
            self.tick_history.append(state)
            if len(self.tick_history) > 200:
                self.tick_history.pop(0)
            return state

    def start_auto(self):
        if self._thread and self._thread.is_alive():
            self.auto_run = True
            return
        self.auto_run = True
        self._stop.clear()

        def loop():
            while not self._stop.is_set() and self.auto_run:
                try:
                    self.step()
                except Exception as e:
                    print(f"[engine] tick error: {e}")
                self._stop.wait(self.tick_interval)

        self._thread = threading.Thread(target=loop, daemon=True, name="engine-loop")
        self._thread.start()

    def stop_auto(self):
        self.auto_run = False
        self._stop.set()


def _serialize_incident(inc) -> dict:
    return {
        "id": inc.id,
        "type": inc.type.value,
        "state": inc.state.value,
        "start_tick": inc.start_tick,
        "jira_ticket_key": getattr(inc, "jira_ticket_key", None),
        "slack_sent": getattr(inc, "slack_sent", False),
        "analysis": inc.analysis,
        "history": [(t, s.value) for t, s in (getattr(inc, "history", []) or [])],
    }


runtime: EngineRuntime | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global runtime
    runtime = EngineRuntime()
    yield
    if runtime:
        runtime.stop_auto()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class InjectBody(BaseModel):
    incident_type: str
    severity: str = "P2"


class CommandBody(BaseModel):
    text: str


@app.get("/api/state")
def get_state():
    return json_response(runtime.snapshot())


@app.post("/api/tick")
def post_tick():
    runtime.step()
    return json_response(runtime.snapshot())


@app.post("/api/auto")
def post_auto(on: bool = True):
    if on:
        runtime.start_auto()
    else:
        runtime.stop_auto()
    return {"auto_run": runtime.auto_run}


@app.post("/api/inject")
def post_inject(body: InjectBody):
    runtime.engine.inject_incident(body.incident_type, body.severity)
    return json_response(runtime.snapshot())


@app.post("/api/incidents/{incident_id}/approve")
def approve(incident_id: str):
    runtime.engine.approve_action(incident_id)
    return json_response(runtime.snapshot())


@app.post("/api/incidents/{incident_id}/deny")
def deny(incident_id: str):
    runtime.engine.deny_action(incident_id)
    return json_response(runtime.snapshot())


@app.post("/api/reanalyze")
def reanalyze():
    runtime.engine.trigger_reanalysis()
    return {"ok": True}


@app.post("/api/logs/inject")
def inject_logs(body: CommandBody):
    log_path = ROOT / "data" / "app_logs.log"
    with open(log_path, "a") as f:
        f.write("\n" + body.text + "\n")
    runtime.engine.cooldown_until = 0
    runtime.engine.trigger_reanalysis()
    runtime.step()
    return json_response(runtime.snapshot())


@app.get("/api/events")
async def events():
    async def gen():
        last_tick = -1
        last_push = 0.0
        while True:
            snap = runtime.snapshot()
            now = time.time()
            # push on new tick OR at least every 1s as a heartbeat
            if snap["tick"] != last_tick or (now - last_push) > 1.0:
                last_tick = snap["tick"]
                last_push = now
                yield f"data: {json.dumps(_safe(snap), default=str)}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/history")
def get_history():
    eng = runtime.engine
    resolved = list(getattr(eng.state_tracker, "resolved_log", []))
    items = [_serialize_incident(i) for i in resolved]
    items.reverse()  # newest first

    # Compute KPIs
    total = len(resolved) + len(eng.state_tracker.get_active())
    auto_resolved = sum(
        1 for i in resolved
        if i.state.value == "RESOLVED"
        and not (i.analysis and i.analysis.get("needs_approval"))
    )
    durations = [
        (i.history[-1][0] - i.start_tick) if getattr(i, "history", None) else 0
        for i in resolved
    ]
    avg_ticks = (sum(durations) / len(durations)) if durations else 0

    return json_response({
        "kpis": {
            "incidents": total,
            "resolved": len(resolved),
            "auto_resolved": auto_resolved,
            "avg_ticks": round(avg_ticks, 1),
        },
        "items": items,
    })


class KBIngestBody(BaseModel):
    incident_id: str


@app.post("/api/kb/ingest")
def kb_ingest(body: KBIngestBody):
    """Add a resolved incident to the ChromaDB knowledge base."""
    eng = runtime.engine
    inc = next(
        (i for i in getattr(eng.state_tracker, "resolved_log", [])
         if i.id == body.incident_id),
        None,
    )
    if not inc:
        raise HTTPException(404, f"Resolved incident {body.incident_id} not found")
    a = inc.analysis or {}
    try:
        from src.rag.vector_db import KnowledgeBase
        kb = KnowledgeBase()
        root_cause = (a.get('hypotheses') or [{}])[0].get('root_cause', '')
        text = (
            f"Title: {a.get('summary','')}. "
            f"Symptoms: {', '.join(a.get('triage_report', {}).get('symptoms', [])[:5])}. "
            f"Cause: {root_cause}. "
            f"Fix: {a.get('top_recommendation','')}."
        )
        meta = {
            "id": f"live-{inc.id}",
            "summary": a.get("summary", "")[:200],
            "type": inc.type.value,
            "severity": a.get("severity", "?"),
            "root_cause": root_cause,
            "resolution": a.get("top_recommendation", ""),
        }
        kb.collection.add(ids=[f"live-{inc.id}"], documents=[text], metadatas=[meta])
        return {"ok": True, "indexed_id": f"live-{inc.id}"}
    except Exception as e:
        raise HTTPException(500, f"KB ingest failed: {e}")


@app.get("/api/kb")
def get_kb():
    """Return all historical incidents indexed in the knowledge base."""
    path = Path(__file__).resolve().parent.parent / "data" / "historical_incidents.json"
    try:
        with open(path) as f:
            incidents = json.load(f)
    except Exception as e:
        raise HTTPException(500, f"Failed to load KB: {e}")
    return json_response({"items": incidents, "count": len(incidents)})


@app.get("/api/health")
def health():
    return {"ok": True}
