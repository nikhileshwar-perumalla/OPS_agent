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
        return {
            "tick": eng.tick_count,
            "mode": eng.mode.value,
            "auto_run": self.auto_run,
            "llm_active": bool(eng.llm_client and eng.llm_client.is_active),
            "metrics": eng.metrics,
            "metrics_history": [s.get("metrics", {}) for s in self.tick_history[-60:]],
            "incidents": [_serialize_incident(i) for i in active],
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


@app.get("/api/health")
def health():
    return {"ok": True}
