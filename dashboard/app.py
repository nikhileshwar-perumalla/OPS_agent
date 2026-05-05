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
from src.agent.orchestrator import OrchestratorAgent
from src.agent.message_bus import MessageBus
from src.agent.llm_client import LLMClient
from src.orchestration.policy_engine import PolicyEngine

# Page Config
st.set_page_config(page_title="AI Ops Agent — Multi-Agent", layout="wide")

# Valid States
if 'engine' not in st.session_state:
    engine = SimulationEngine()
    # Configure Dependencies
    engine.log_source = FileLogSource('data/app_logs.log')
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
@st.cache_resource
def get_shared_llm():
    print("[App] Initializing Cached LLMClient...")
    return LLMClient()

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

# Re-attach dependencies to session engine
# This fixes the issue where unpicklable objects are lost on rerun
engine = st.session_state.engine
engine.slack_notifier = get_shared_slack()
engine.jira_connector = get_shared_jira()

# Re-initialize orchestrator with cached dependencies if needed
if engine.orchestrator is None:
    llm = get_shared_llm()
    engine.llm_client = llm
    engine.orchestrator = OrchestratorAgent(
        bus=engine.message_bus,
        slack_notifier=engine.slack_notifier,
        jira_connector=engine.jira_connector,
        llm_client=llm
    )
else:
    # Update comms agent references
    engine.orchestrator.comms.slack = engine.slack_notifier
    engine.orchestrator.comms.jira = engine.jira_connector

if 'auto_run' not in st.session_state:
    st.session_state.auto_run = False

if 'tick_history' not in st.session_state:
    st.session_state.tick_history = []

# --- Sidebar ---
st.sidebar.title("🎮 Simulation Control")

# Mode Selection
engine.set_mode(SimulationMode.SIMULATION)
st.sidebar.caption(f"Mode: {engine.mode.value.upper()}")

# LLM Status
llm_mode = "🟢 LLM Active" if (engine.llm_client and engine.llm_client.is_active) else "🟡 Mock Mode"
st.sidebar.caption(f"AI: {llm_mode}")

st.sidebar.divider()

# Tick Controls
col1, col2 = st.sidebar.columns(2)
if col1.button("▶️ Start"):
    st.session_state.auto_run = True
if col2.button("⏸️ Pause"):
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

# Agent Stats (Sidebar)
st.sidebar.divider()
st.sidebar.subheader("🤖 Agent Stats")
if engine.orchestrator:
    stats = engine.orchestrator.get_agent_stats()
    for agent_name, agent_stats in stats.items():
        if agent_name in ('bus', 'llm'):
            continue
        calls = agent_stats.get('calls', 0)
        avg = agent_stats.get('avg_time_ms', 0)
        st.sidebar.caption(f"**{agent_name}**: {calls} calls, {avg:.0f}ms avg")

# --- Main UI ---
st.title("🛡️ AI Ops Agent: Multi-Agent System")

# Metrics & State Display
m_col1, m_col2, m_col3, m_col4 = st.columns(4)
m_col1.metric("Tick", engine.tick_count)
m_col2.metric("Active Incidents", len(engine.state_tracker.get_active()))
m_col3.metric("Mode", engine.mode.value.upper())
m_col4.metric("Agents", "5 Active" if engine.orchestrator else "None")

# Tick Logic (Fragment for Auto-Run)
@st.fragment(run_every=2 if st.session_state.auto_run else None)
def game_loop():
    should_tick = False
    if st.session_state.auto_run:
        should_tick = True

    if should_tick:
        state = engine.tick()
        st.session_state.tick_history.append(state)
        if len(st.session_state.tick_history) > 30:
             st.session_state.tick_history.pop(0)

    # Visualization (Always render latest)
    if st.session_state.tick_history:
        latest = st.session_state.tick_history[-1]
        metrics = latest.get('metrics', {})

        # Charts - Metric Chart (Full Width)
        df = pd.DataFrame([s['metrics'] for s in st.session_state.tick_history])
        if not df.empty and 'cpu_percent' in df.columns:
            st.subheader("📊 System Metrics")
            cols = ['cpu_percent', 'memory_percent', 'latency_seconds']
            if 'disk_percent' in df.columns: cols.append('disk_percent')
            st.line_chart(df[cols])
            
        # ================================================
        # INCIDENT LIST WITH MULTI-AGENT DETAIL
        # ================================================
        st.subheader("🚨 Active Incidents")
        
        # Use LIVE state, not history
        active_incidents = engine.state_tracker.get_active()
        
        if active_incidents:
            for incident in active_incidents:
                status_icon = "🔥" if incident.state.value == "ESCALATED" else "⚠️"
                label = f"{status_icon} **{incident.id}** | Type: {incident.type.value} | State: {incident.state.value}"
                
                with st.expander(label, expanded=True):
                    st.write(f"**Started at Tick:** {incident.start_tick}")

                    # Show Jira Ticket
                    if incident.jira_ticket_key:
                        jira_url = os.getenv("JIRA_URL", "")
                        ticket_link = f"{jira_url}/browse/{incident.jira_ticket_key}"
                        st.markdown(f"🎫 **Jira Ticket:** [{incident.jira_ticket_key}]({ticket_link})")

                    # Show Analysis with Multi-Agent Detail
                    if incident.analysis:
                        analysis = incident.analysis

                        # ============================================
                        # AGENT WORKFLOW PIPELINE VISUALIZATION
                        # ============================================
                        workflow = analysis.get('workflow_stages', {})
                        if workflow:
                            st.subheader("🤖 Agent Pipeline")
                            
                            pipeline_cols = st.columns(5)
                            stages = [
                                ('triage', '🔍', 'Triage'),
                                ('diagnostics', '🔬', 'Diagnostics'),
                                ('rca', '🧠', 'RCA'),
                                ('remediation', '🛠️', 'Remediation'),
                                ('comms', '📡', 'Comms')
                            ]
                            
                            for i, (key, icon, label) in enumerate(stages):
                                stage_data = workflow.get(key, {})
                                status = stage_data.get('status', 'pending')
                                duration = stage_data.get('duration_ms', 0)
                                summary = stage_data.get('output_summary', '')
                                
                                status_emoji = {'complete': '🟢', 'error': '🔴', 'skipped': '⚪'}.get(status, '🟡')
                                
                                with pipeline_cols[i]:
                                    st.markdown(f"**{icon} {label}**")
                                    st.caption(f"{status_emoji} {status.upper()}")
                                    st.caption(f"⏱️ {duration:.0f}ms")
                                    if summary:
                                        st.caption(summary)
                            
                            # Total pipeline time
                            total_ms = analysis.get('pipeline_duration_ms', 0)
                            llm_active = analysis.get('llm_active', False)
                            st.caption(f"📐 Total Pipeline: **{total_ms:.0f}ms** | "
                                       f"AI: {'🟢 LLM' if llm_active else '🟡 Rule-based'}")

                        # ============================================
                        # TABBED AGENT DETAIL VIEW
                        # ============================================
                        tab_overview, tab_triage, tab_diag, tab_rca, tab_remediation, tab_conversation = st.tabs([
                            "📋 Overview", "🔍 Triage", "🔬 Diagnostics", 
                            "🧠 RCA", "🛠️ Remediation", "💬 Agent Chat"
                        ])
                        
                        with tab_overview:
                            st.markdown(f"**Top Recommendation**: `{analysis.get('top_recommendation')}`")
                            st.markdown(f"**Severity**: `{analysis.get('severity')}`")
                            st.markdown(f"**Summary**: {analysis.get('summary')}")
                            
                            # Ranked Hypotheses
                            st.caption("Ranked Hypotheses (Confidence)")
                            for hyp in analysis.get('hypotheses', []):
                                conf = hyp['confidence']
                                st.progress(conf, text=f"{hyp['root_cause']} ({int(conf*100)}%) — {hyp.get('reasoning', '')[:100]}")
                            
                            if analysis.get('needs_approval'):
                                st.warning("⚠️ Action Requires Approval (Policy Check)")
                                c_act1, c_act2 = st.columns(2)
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
                        
                        with tab_triage:
                            triage = analysis.get('triage_report', {})
                            if triage:
                                st.markdown(f"**Severity**: `{triage.get('severity', '?')}`")
                                st.markdown(f"**Urgency Score**: `{triage.get('urgency_score', 0):.2f}`")
                                st.markdown("**Detected Symptoms:**")
                                for s in triage.get('symptoms', []):
                                    st.markdown(f"- {s}")
                            else:
                                st.info("No triage data available")
                        
                        with tab_diag:
                            diag = analysis.get('diagnostic_report', {})
                            if diag:
                                st.markdown(f"**Diagnostic Summary**: {diag.get('readable_summary', 'N/A')}")
                                llm_badge = "🟢 LLM-Enhanced" if diag.get('llm_enhanced') else "🟡 Rule-based"
                                st.caption(f"Analysis Mode: {llm_badge}")
                                
                                d_col1, d_col2 = st.columns(2)
                                with d_col1:
                                    st.markdown("**Error Patterns:**")
                                    for p in diag.get('error_patterns', []):
                                        st.code(p, language=None)
                                with d_col2:
                                    st.markdown("**Affected Services:**")
                                    for s in diag.get('affected_services', []):
                                        st.markdown(f"🔸 {s}")
                                
                                st.markdown("**Correlated Symptoms:**")
                                for c in diag.get('correlated_symptoms', []):
                                    st.markdown(f"↳ {c}")
                            else:
                                st.info("No diagnostic data available")
                        
                        with tab_rca:
                            rca = analysis.get('rca_report', {})
                            if rca:
                                st.markdown(f"**RAG Matches**: {rca.get('rag_match_count', 0)}")
                                
                                if rca.get('llm_reasoning'):
                                    st.markdown("**🧠 LLM Reasoning Chain:**")
                                    st.info(rca['llm_reasoning'])
                                
                                top = rca.get('top_root_cause', {})
                                if top:
                                    st.markdown(f"**Top Root Cause**: {top.get('root_cause', 'Unknown')}")
                                    st.markdown(f"**Confidence**: {top.get('confidence', 0):.2%}")
                                    st.markdown(f"**Historical Match**: {top.get('historical_id', 'N/A')}")
                                    if top.get('resolution'):
                                        st.markdown(f"**Past Resolution**: {top['resolution']}")
                            else:
                                st.info("No RCA data available")
                        
                        with tab_remediation:
                            rem = analysis.get('remediation_plan', {})
                            if rem:
                                st.markdown(f"**Recommended Action**: `{rem.get('recommended_action')}`")
                                
                                safety = rem.get('safety_status', 'UNKNOWN')
                                safety_colors = {'ALLOWED': '🟢', 'REQUIRES_APPROVAL': '🟡', 'BLOCKED': '🔴'}
                                st.markdown(f"**Safety**: {safety_colors.get(safety, '⚪')} {safety}")
                                st.markdown(f"**Needs Approval**: {'Yes' if rem.get('needs_approval') else 'No'}")
                                st.markdown(f"**Playbook**: `{rem.get('playbook_id', 'N/A')}`")
                                st.markdown(f"**Confidence**: {rem.get('confidence', 0):.2%}")
                                
                                if rem.get('safety_message'):
                                    st.caption(f"Policy: {rem['safety_message']}")
                            else:
                                st.info("No remediation data available")
                        
                        with tab_conversation:
                            conversation = analysis.get('agent_conversation', [])
                            if conversation:
                                st.caption(f"{len(conversation)} messages in pipeline")
                                
                                agent_colors = {
                                    'orchestrator': '🎯',
                                    'triage': '🔍',
                                    'diagnostics': '🔬',
                                    'rca': '🧠',
                                    'remediation': '🛠️',
                                    'comms': '📡'
                                }
                                
                                for msg in conversation:
                                    sender = msg.get('sender', 'unknown')
                                    icon = agent_colors.get(sender, '💬')
                                    msg_type = msg.get('type', '')
                                    recipient = msg.get('recipient', '')
                                    duration = msg.get('duration_ms', 0)
                                    summary = msg.get('payload_summary', '')
                                    
                                    with st.chat_message(sender, avatar=icon):
                                        st.caption(f"**{msg_type}** → {recipient} ({duration:.0f}ms)")
                                        st.write(summary)
                            else:
                                st.info("No conversation data")

                    else:
                        # Check if we have a recent error
                        logs = getattr(engine, 'system_logs', [])
                        recent_logs = logs[-5:]
                        agent_error = next((l for l in recent_logs if "[Agent Error]" in l), None)
                        
                        if agent_error:
                             st.error(f"⚠️ Analysis Failed: {agent_error}")
                             if st.button("🔄 Retry Analysis", key=f"retry_{incident.id}"):
                                 engine.trigger_reanalysis()
                                 st.rerun()
                        else:
                             st.info("⏳ Waiting for Multi-Agent Analysis... (Next Tick)")
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
            pass

game_loop()

# Manual Step Handling (Outside Fragment)
if st.session_state.step_once and not st.session_state.auto_run:
    state = engine.tick()
    st.session_state.tick_history.append(state)
    st.rerun()

st.divider()
st.subheader("💻 Chaos Terminal")

# Live Terminal Output — includes agent logs
terminal_logs = getattr(engine, 'system_logs', [])
if engine.orchestrator:
    agent_logs = engine.orchestrator.get_all_logs()
    # Merge and deduplicate
    all_logs = list(set(terminal_logs + agent_logs))
    all_logs.sort()
    terminal_text = "\n".join(all_logs[-25:])
else:
    terminal_text = "\n".join(terminal_logs[-20:])

st.code(terminal_text, language="bash")

# Unified Input (Chat Style)
prompt = st.chat_input("admin@ops-agent:~$ (Type command or paste logs)")

if prompt:
    lines = prompt.strip().split('\n')
    
    # Heuristic: Is this a log paste?
    is_log = len(lines) > 1 or any(x in prompt for x in ["INFO", "WARN", "ERROR", "202"])
    
    if is_log:
        # Log Injection Mode
        log_file = 'data/app_logs.log'
        try:
            with open(log_file, 'a') as f:
                f.write("\n" + prompt + "\n")
            
            engine.log(f"[Injector] Writing {len(lines)} lines to log stream...")
            for line in lines:
                if line.strip():
                    engine.log(f"   > {line.strip()}")
                    
            st.toast(f"Injected {len(lines)} log lines")
            
            engine.cooldown_until = 0
            
            if engine.trigger_reanalysis():
                 st.toast("Logs Injected. Re-analyzing...")
            else:
                 st.toast("Logs Injected. Triggering Detection...")
            
            state = engine.tick()
            st.session_state.tick_history.append(state)
            
            time.sleep(0.1)
            st.rerun()
                 
        except Exception as e:
            st.error(f"Failed to write logs: {e}")
            
    else:
        # Command Mode
        cmd = prompt.strip().lower()
        
        if cmd == "help":
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
            - agents              : Show agent statistics
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
        
        elif cmd == "agents":
            if engine.orchestrator:
                stats = engine.orchestrator.get_agent_stats()
                for name, data in stats.items():
                    engine.log(f"[Agent Stats] {name}: {data}")
            else:
                engine.log("[Error] Orchestrator not initialized")
                
        elif cmd == "status":
            engine.log(f"Tick: {engine.tick_count} | Mode: {engine.mode.value} | "
                       f"Incidents: {len(engine.state_tracker.get_active())} | "
                       f"Agents: {'5 Active' if engine.orchestrator else 'None'} | "
                       f"LLM: {'Active' if (engine.llm_client and engine.llm_client.is_active) else 'Mock'}")
            
        else:
            engine.log(f"[Error] Command not found: {cmd}")
            st.toast(f"Command not found: {cmd}")
