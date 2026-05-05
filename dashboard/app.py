import streamlit as st
import time
import pandas as pd
import json
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Add root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.simulation.engine import SimulationEngine, SimulationMode
from src.simulation.observations import FileLogSource
from src.detection.anomaly_model import AnomalyDetector
from src.integration.slack_client import SlackNotifier
from src.integration.jira_client import JiraConnector
from src.agent.rca_agent import RCAAgent
from src.orchestration.policy_engine import PolicyEngine

# Page Config
st.set_page_config(page_title="AI Ops Agent (Phase 2)", layout="wide")

# Valid States
if 'engine' not in st.session_state:
    engine = SimulationEngine()
    # Configure Dependencies
    engine.log_source = FileLogSource('data/app_logs.log')
    engine.agent = RCAAgent() 
    engine.detector = AnomalyDetector()
    engine.slack_notifier = SlackNotifier(webhook_url=os.getenv("SLACK_WEBHOOK_URL"), mock=False)
    engine.jira_connector = JiraConnector(
            url=os.getenv("JIRA_URL"),
            username=os.getenv("JIRA_USERNAME"),
            token=os.getenv("JIRA_API_TOKEN"),
            project_key=os.getenv("JIRA_PROJECT_KEY", "KAN"),
            mock=False
    )
    st.session_state.engine = engine

# --- Dependency Management ---
# Use cache_resource to keep DB connections alive across reruns
@st.cache_resource
def get_shared_agent():
    print("[App] Initializing Cached RCAAgent...")
    return RCAAgent()

@st.cache_resource
def get_shared_slack():
    return SlackNotifier(webhook_url=os.getenv("SLACK_WEBHOOK_URL"), mock=False)

def get_shared_jira():
    return JiraConnector(
            url=os.getenv("JIRA_URL"),
            username=os.getenv("JIRA_USERNAME"),
            token=os.getenv("JIRA_API_TOKEN"),
            project_key=os.getenv("JIRA_PROJECT_KEY", "KAN"),
            mock=False
    )

# Always re-attach dependencies to the session text engine
# This fixes the issue where unpicklable objects (like ChromaDB) are lost on rerun
st.session_state.engine.agent = get_shared_agent()
st.session_state.engine.slack_notifier = get_shared_slack()
st.session_state.engine.jira_connector = get_shared_jira()
    
engine = st.session_state.engine

if 'auto_run' not in st.session_state:
    st.session_state.auto_run = False

if 'tick_history' not in st.session_state:
    st.session_state.tick_history = []

engine = st.session_state.engine

# --- Sidebar ---
st.sidebar.title("🎮 Simulation Control")

# Mode Selection
# Defaulting to SIMULATION (User requested removal of Observe Only)
engine.set_mode(SimulationMode.SIMULATION)
st.sidebar.caption(f"Mode: {engine.mode.value.upper()}")

st.sidebar.divider()

# Tick Controls
col1, col2 = st.sidebar.columns(2)
if col1.button("▶️ Start"):
    st.session_state.auto_run = True
if col2.button("MwPause"):
    st.session_state.auto_run = False

if st.sidebar.button("⏩ Step Tick"):
    st.session_state.step_once = True
else:
    st.session_state.step_once = False

st.sidebar.divider()

# Incident Injection
st.sidebar.subheader("Inject Incident")
inc_type = st.sidebar.selectbox("Type", [
    "high_cpu", "memory_leak", "network_latency", "service_down",
    "disk_usage_high", "process_crash", "database_lock", "ssl_expiry"
])
if st.sidebar.button("Inject"):
    engine.inject_incident(inc_type)
    st.toast(f"Injected {inc_type}")

# --- Main UI ---
st.title("🛡️ AI Ops Agent: Phase 2")

# Metrics & State Display
m_col1, m_col2, m_col3 = st.columns(3)
m_col1.metric("Tick", engine.tick_count)
m_col2.metric("Active Incidents", len(engine.state_tracker.get_active()))
m_col3.metric("Mode", engine.mode.value.upper())

# Tick Logic (Fragment for Auto-Run)
@st.fragment(run_every=2 if st.session_state.auto_run else None)
def game_loop():
    should_tick = False
    if st.session_state.auto_run:
        should_tick = True
    elif st.session_state.get('step_once'):
        # Only tick once, then consume the flag (state trickery needed here?)
        # Actually fragments might re-run, simpler to just check session state trigger outside?
        # For simplicity, if auto_run is off, we rely on the main script rerun triggered by button.
        pass

    if should_tick:
        state = engine.tick()
        # Append to history for viz
        st.session_state.tick_history.append(state)
        if len(st.session_state.tick_history) > 30:
             st.session_state.tick_history.pop(0)

    # Visualization (Always render latest)
    if st.session_state.tick_history:
        latest = st.session_state.tick_history[-1]
        metrics = latest.get('metrics', {})
        features = latest.get('log_features', {})
        analysis = metrics.get('latest_analysis') # Retrieved from engine
        
        # Charts
        # Metric Chart (Full Width)
        df = pd.DataFrame([s['metrics'] for s in st.session_state.tick_history])
        if not df.empty and 'cpu_percent' in df.columns:
            st.subheader("System Metrics")
            # Added disk_percent if available
            cols = ['cpu_percent', 'memory_percent', 'latency_seconds']
            if 'disk_percent' in df.columns: cols.append('disk_percent')
            st.line_chart(df[cols])
            
        # Incident List
        st.subheader("Active Incidents")
        
        # Use LIVE state, not history (avoids UI lag on resolution)
        active_incidents = engine.state_tracker.get_active()
        
        if active_incidents:
            for incident in active_incidents:
                # Color code based on severity/state
                status_icon = "🔥" if incident.state.value == "ESCALATED" else "⚠️"
                label = f"{status_icon} **{incident.id}** | Type: {incident.type.value} | State: {incident.state.value}"
                
                with st.expander(label, expanded=True):
                    st.write(f"**Started at Tick:** {incident.start_tick}")

                    # Show Jira Ticket
                    if incident.jira_ticket_key:
                        jira_url = os.getenv("JIRA_URL", "")
                        ticket_link = f"{jira_url}/browse/{incident.jira_ticket_key}"
                        st.markdown(f"🎫 **Jira Ticket:** [{incident.jira_ticket_key}]({ticket_link})")

                    # Show Analysis Persistence
                    if incident.analysis:
                        analysis = incident.analysis
                        st.subheader(f"🧠 Agent Hypothesis")
                        
                        # Top Recommendation
                        st.markdown(f"**Top Recommendation**: `{analysis.get('top_recommendation')}`")
                        st.markdown(f"**Summary**: {analysis.get('summary')}")
                        
                        # Ranked Hypotheses
                        st.caption("Ranked Hypotheses (Confidence)")
                        for hyp in analysis.get('hypotheses', []):
                            conf = hyp['confidence']
                            st.progress(conf, text=f"{hyp['root_cause']} ({int(conf*100)}%) - {hyp['reasoning']}")
                        
                        if analysis.get('needs_approval'):
                            st.warning("⚠️ Action Requires Approval (Policy Check)")
                            c_act1, c_act2 = st.columns(2)
                            # We use unique keys for buttons
                            if c_act1.button("✅ Approve", key=f"app_{incident.id}"):
                                engine.approve_action(incident.id)
                                st.toast("Action Approved! System Recovering...")
                                time.sleep(1)
                                st.rerun()
                                
                            if c_act2.button("❌ Deny", key=f"den_{incident.id}"):
                                engine.deny_action(incident.id)
                                st.toast("Action Denied. Escalating...")
                                time.sleep(1)
                                st.rerun()
                    else:

                        # Check if we have a recent error
                        logs = getattr(engine, 'system_logs', [])
                        recent_logs = logs[-5:] # check last 5
                        agent_error = next((l for l in recent_logs if "[Agent Error]" in l), None)
                        
                        if agent_error:
                             st.error(f"⚠️ Analysis Failed: {agent_error}")
                             if st.button("🔄 Retry Analysis", key=f"retry_{incident.id}"):
                                 # Force re-trigger
                                 engine.trigger_reanalysis()
                                 st.rerun()
                        else:
                             st.info("⏳ Waiting for Agent Analysis... (Next Tick)")
        else:
            st.success("No Active Incidents")

    # Polling for External Actions (Slack)
    PENDING_FILE = 'data/pending_actions.json'
    if os.path.exists(PENDING_FILE):
        try:
            with open(PENDING_FILE, 'r') as f:
                pending_events = json.load(f)
            
            if pending_events:
                for event in pending_events:
                    action_id = event.get('action_id')
                    ticket_id = event.get('ticket_id')
                    user = event.get('user')
                    
                    if action_id == "approve_action":
                        engine.approve_action(ticket_id)
                        st.toast(f"Slack: @{user} Approved {ticket_id}")
                    elif action_id == "escalate_action":
                        engine.deny_action(ticket_id)
                        st.toast(f"Slack: @{user} Escalated {ticket_id}")
                
                # Clear file
                with open(PENDING_FILE, 'w') as f:
                    json.dump([], f)
                    
        except Exception as e:
            # print(f"Polling Error: {e}")
            pass

game_loop()

# Manual Step Handling (Outside Fragment)
if st.session_state.step_once and not st.session_state.auto_run:
    state = engine.tick()
    st.session_state.tick_history.append(state)
    st.rerun()

st.divider()
st.subheader("💻 Chaos Terminal")

# Live Terminal Output
terminal_logs = getattr(engine, 'system_logs', [])
terminal_text = "\n".join(terminal_logs[-20:]) # Show last 20 lines
st.code(terminal_text, language="bash")

# Unified Input
# Unified Input (Chat Style - Fixed at Bottom)
# prompt = st.chat_input("admin@ops-agent:~$ Type command or paste logs...")
# Use chat_input to allow "Enter to Run" behavior
prompt = st.chat_input("admin@ops-agent:~$ (Type command or paste logs)")

if prompt:
    lines = prompt.strip().split('\n')
    
    # Echo to Chaos Terminal
    # engine.log(f"[User Input] {prompt}") # Optional echo
    
    # Heuristic: Is this a log paste? (Multiple lines or timestamp/level)
    is_log = len(lines) > 1 or any(x in prompt for x in ["INFO", "WARN", "ERROR", "202"])
    
    if is_log:
        # Log Injection Mode
        log_file = 'data/app_logs.log'
        try:
            with open(log_file, 'a') as f:
                f.write("\n" + prompt + "\n")
            
            # Echo to Chaos Terminal for visual feedback
            engine.log(f"[Injector] Writing {len(lines)} lines to log stream...")
            for line in lines:
                if line.strip():
                    engine.log(f"   > {line.strip()}")
                    
            st.toast(f"Injected {len(lines)} log lines")
            
            # Force Immediate Action
            engine.cooldown_until = 0 # Bypass any cooldowns
            
            if engine.trigger_reanalysis():
                 # Incident exists, re-analyze
                 st.toast("Logs Injected. Re-analyzing...")
            else:
                 # No incident, this should trigger one next tick
                 st.toast("Logs Injected. Triggering Detection...")
            
            # Force a tick immediately to process the new logs/state
            state = engine.tick()
            st.session_state.tick_history.append(state)
            
            # Rerun to show results instantly
            time.sleep(0.1) # Brief pause to ensure files flush if needed
            st.rerun()
                 
        except Exception as e:
            st.error(f"Failed to write logs: {e}")
            
    else:
        # Command Mode
        cmd = prompt.strip().lower()
        
        if cmd == "help":
            # We can't really print to the chat input, so print to terminal log
            help_text = """
            Available Commands:
            - inject cpu          : Trigger High CPU Incident
            - inject memory       : Trigger Memory Leak
            - inject latency      : Trigger Network Latency
            - inject service      : Trigger Service Down
            - inject disk         : Trigger High Disk Usage
            - inject process      : Trigger Process Crash
            - inject db           : Trigger Database Lock
            - inject ssl          : Trigger SSL Expiry
            - resolve <id>        : Force resolve incident
            - status              : Show engine status
            """
            for line in help_text.split('\n'):
                 if line.strip(): engine.log(line.strip())
            
        elif cmd.startswith("inject"):
            parts = cmd.split()
            if len(parts) > 1:
                target = parts[1]
                type_map = {
                    "cpu": "high_cpu",
                    "memory": "memory_leak",
                    "latency": "network_latency",
                    "network": "network_latency",
                    "service": "service_down",
                    "disk": "disk_usage_high",
                    "process": "process_crash",
                    "db": "database_lock",
                    "lock": "database_lock",
                    "ssl": "ssl_expiry",
                    "cert": "ssl_expiry"
                }
                if target in type_map:
                    engine.inject_incident(type_map[target])
                    st.toast(f"Executed: {cmd}")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.toast(f"Unknown injection target: {target}")
                    engine.log(f"[Error] Unknown target: {target}")
        
        elif cmd.startswith("resolve"):
            parts = cmd.split()
            if len(parts) > 1:
                iid = parts[1]
                engine.approve_action(iid)
                st.toast(f"Force Resolved {iid}")
                st.rerun()
                
        elif cmd == "status":
            engine.log(f"Tick: {engine.tick_count} | Mode: {engine.mode.value} | Incidents: {len(engine.state_tracker.get_active())}")
            
        else:
            engine.log(f"[Error] Command not found: {cmd}")
            st.toast(f"Command not found: {cmd}")
