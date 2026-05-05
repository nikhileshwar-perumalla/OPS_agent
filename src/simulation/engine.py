import time
import os
from enum import Enum
from typing import List, Dict, Optional
from datetime import datetime
import random # Added for random.randint

from .incident import ActiveIncident, IncidentType, IncidentState
from .state import StateTracker
from .metrics_generator import MetricsGenerator
from .logs_generator import LogGenerator
from .observations import ObservationWindow
from src.agent.orchestrator import OrchestratorAgent
from src.agent.message_bus import MessageBus
from src.agent.llm_client import LLMClient

class SimulationMode(Enum):
    SIMULATION = "simulation"
    OBSERVE_ONLY = "observe_only"

class SimulationEngine:
    def __init__(self):
        self.tick_count = 0
        self.mode = SimulationMode.SIMULATION
        self.metrics = {}
        
        # Components
        self.state_tracker = StateTracker()
        self.metrics_generator = MetricsGenerator()
        self.log_generator = LogGenerator()
        self.observation_window = ObservationWindow()
        
        # Terminal Output Buffer for Web UI
        self.system_logs = []
        self.cooldown_until = 0  
        
        # Multi-Agent System
        self.message_bus = MessageBus()
        self.orchestrator = None
        self.llm_client = None
        self.pipeline_running_id = None
        
        # External dependencies (to be set)
        self.log_source = None
        self.detector = None
        self.slack_notifier = None
        self.jira_connector = None

    def log(self, message: str):
        """
        Logs a message to both stdout and the web terminal buffer.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        print(entry)
        self.system_logs.append(entry)
        # Keep buffer manageable
        if len(self.system_logs) > 50:
            self.system_logs.pop(0)
        
    def set_mode(self, mode: SimulationMode):
        self.mode = mode
        
    def inject_incident(self, incident_type_str: str, severity="P2"):
        """
        Manually inject an incident (e.g. from Dashboard)
        """
        try:
            # Map string to Enum
            itype = IncidentType(incident_type_str)
            incident = ActiveIncident(itype, self.tick_count, severity)
            result = self.state_tracker.register_incident(incident)
            self.log(f"[Engine] Injected {itype.value} at Tick {self.tick_count}")
        except ValueError:
            self.log(f"[Engine] Unknown incident type: {incident_type_str}")

    def _ensure_orchestrator(self):
        """Initialize or re-initialize the orchestrator with current dependencies."""
        if self.orchestrator is None:
            try:
                self.llm_client = LLMClient()
                self.orchestrator = OrchestratorAgent(
                    bus=self.message_bus,
                    slack_notifier=self.slack_notifier,
                    jira_connector=self.jira_connector,
                    llm_client=self.llm_client
                )
                self.log("[Engine] Multi-Agent Orchestrator initialized (5 agents)")
            except Exception as e:
                self.log(f"[Engine] Orchestrator Init Failed: {e}")
                import traceback
                traceback.print_exc()

    def tick(self):
        """
        Executes one simulation tick.
        """
        self.tick_count += 1
        
        # Ensure Multi-Agent System is alive
        self._ensure_orchestrator()
        
        # Capture local reference for stability
        local_orchestrator = self.orchestrator

        active_incidents = self.state_tracker.get_active()

        # 1. Update Metrics
        if self.mode == SimulationMode.SIMULATION:
            self.metrics = self.metrics_generator.tick(active_incidents)
        else:
            self.metrics = self.metrics_generator.generate_baseline()

        # 1c. Generate Synthetic Logs (Background Noise + Anomaly)
        # Determine anomaly mode from metrics (which knows active incidents)
        anomaly_type = self.metrics.get('anomaly_active')
        
        # Generate 1-5 logs per tick for realism
        num_logs = random.randint(1, 5)
        if anomaly_type: num_logs += random.randint(2, 8) # More noise during incidents
        
        generated_lines = []
        for _ in range(num_logs):
            log_data = self.log_generator.generate_log(anomaly_type)
            # Format: YYYY-MM-DD HH:MM:SS LEVEL [Service] Message (Latency)
            # LogGenerator returns a dict, let's format it.
            # We add a fake [Service] tag for parsing
            service = "Backend"
            if log_data['endpoint'].startswith("/api/v1/user"): service = "UserService"
            elif log_data['endpoint'].startswith("/api/v1/search"): service = "SearchService"
            
            line = f"{log_data['timestamp']} {log_data['level']}  [{service}] {log_data['method']} {log_data['endpoint']} {log_data['status']} - {log_data['message']} ({log_data['latency']}s)"
            generated_lines.append(line)
            
        # Write to file (so FileLogSource can pick it up)
        try:
            with open('data/app_logs.log', 'a') as f:
                for l in generated_lines:
                    f.write(l + "\n")
                f.flush()
                os.fsync(f.fileno()) # Force write to disk
        except Exception as e:
            print(f"Log Write failed: {e}")

        # 2. Ingest Logs
        if self.log_source:
            new_logs = self.log_source.fetch_new_logs()
            if new_logs:
                self.observation_window.add_logs(new_logs)
            
        # 3. Detect & Update
        if self.detector:
            anomaly = self.detector.detect(self.metrics)
                
        # 3b. Log Detection (Rule-based)
        log_features = self.observation_window.get_features()
        if log_features.get('recent_errors', 0) > 0 and not active_incidents:
             # Check Cooldown
             if self.tick_count < self.cooldown_until:
                 pass
             else:
                  self.log(f"[Engine] Log Anomaly Detected ({log_features['recent_errors']} errors). Auto-injecting.")
                  # Default to service_down for generic log errors
                  self.inject_incident("service_down", severity="P1")
                
        # 4. Multi-Agent Analysis Pipeline
        # Process at most ONE eligible incident per tick so the engine loop
        # stays responsive and the UI sees progress incrementally.
        active_list = self.state_tracker.get_active()
        self.pipeline_running_id = None
        eligible = [
            i for i in active_list
            if i.state == IncidentState.DEGRADED
            or (i.state == IncidentState.INVESTIGATING and i.analysis is None)
        ]

        for incident in eligible[:1]:
             # Logic checks
             cond1 = (incident.state == IncidentState.DEGRADED)
             cond2 = (incident.state == IncidentState.INVESTIGATING)
             cond3 = (incident.analysis is None)
             self.pipeline_running_id = incident.id

             if cond1 or (cond2 and cond3):
                # Transition to INVESTIGATING if needed
                if incident.state == IncidentState.DEGRADED:
                    self.state_tracker.update_incident_state(incident.id, IncidentState.INVESTIGATING, self.tick_count)
                
                # Run Multi-Agent Pipeline
                if local_orchestrator:
                    self.log(f"[Engine] Dispatching Incident {incident.id} to Multi-Agent Pipeline...")
                    features = self.observation_window.get_features()
                    
                    try:
                        # Context flags for the orchestrator
                        context = {
                            'slack_sent': getattr(incident, 'slack_sent', False),
                            'jira_ticket_key': incident.jira_ticket_key,
                            'incident_type': incident.type.value
                        }
                        
                        analysis = local_orchestrator.process_incident(
                            self.metrics, features,
                            incident_id=incident.id,
                            context=context
                        )
                        
                        # Store analysis persistently on the incident
                        incident.analysis = analysis
                        
                        self.metrics['latest_analysis'] = analysis
                        self.metrics['agent_active'] = True
                        
                        # Update incident from comms results
                        if analysis.get('slack_sent') and not getattr(incident, 'slack_sent', False):
                            incident.slack_sent = True
                            self.log(f"[Engine] Slack alert sent for {incident.id}")
                        
                        if analysis.get('jira_ticket_key') and not incident.jira_ticket_key:
                            incident.jira_ticket_key = analysis['jira_ticket_key']
                            self.log(f"[Engine] Jira ticket created: {incident.jira_ticket_key}")
                        
                        # Log pipeline summary
                        stages = analysis.get('workflow_stages', {})
                        total_ms = analysis.get('pipeline_duration_ms', 0)
                        self.log(f"[Engine] Pipeline complete ({total_ms:.0f}ms) | "
                                 f"Severity: {analysis.get('severity')} | "
                                 f"Action: {analysis.get('top_recommendation')}")
                        
                    except Exception as e:
                        import traceback
                        tb = traceback.format_exc().strip().splitlines()
                        self.log(f"[Agent Error] Pipeline failed: {e}")
                        for line in tb[-4:]:
                            self.log(f"[Agent Error]   {line}")
                        traceback.print_exc()
                else:
                    self.log(f"[Engine] WARNING: Orchestrator is None.")

        # 5. External Polling (Jira Sync)
        # Check if any active incidents have been resolved externally in Jira
        if self.tick_count % 5 == 0: # Poll every 5 ticks to avoid rate limits
            for incident in active_incidents:
                if incident.jira_ticket_key and self.jira_connector:
                    status = self.jira_connector.get_ticket_status(incident.jira_ticket_key)
                    if status and status.lower() in ['done', 'resolved', 'closed']:
                        self.log(f"[Engine] Detected External Resolution for {incident.id} (Jira: {incident.jira_ticket_key})")
                        self.approve_action(incident.id)

        # Attach analyses to return package so UI can reference them by ID
        incident_analyses = {i.id: i.analysis for i in active_incidents if i.analysis}

        return {
            "tick": self.tick_count,
            "metrics": self.metrics,
            "log_features": self.observation_window.get_features(),
            "active_incidents": [i.type.value for i in active_incidents],
            "incident_states": {i.id: i.state.value for i in active_incidents},
            "analyses": incident_analyses
        }

    def approve_action(self, incident_id: str):
        """
        User approval received. Transition to RESOLVED (instant fix for demo).
        """
        self.log(f"[Engine] Action APPROVED for {incident_id}. Executing recovery plan...")
        
        # Scenario-Specific Recovery Playbooks
        active_incident = next((i for i in self.state_tracker.get_active() if i.id == incident_id), None)
        incident_type = active_incident.type if active_incident else IncidentType.SERVICE_DOWN
        
        playbooks = {
            IncidentType.HIGH_CPU: [
                "[Action] > Scaling Policy Triggered (CPU > 85%)",
                "[Action] > Provisioning 2 new replicas (m5.large)...",
                "[Action] > Waiting for instance initialization (Health check pending)...",
                "[Action] > Instances registered to Load Balancer.",
                "[Action] > CPU Load normalized (45%)."
            ],
            IncidentType.MEMORY_LEAK: [
                "[Action] > Initiating Heap Dump capture...",
                "[Action] > Identifying Top Talkers... (Found: default-pool-1)",
                "[Action] > Graceful Restart of Pod 'order-service-55d'",
                "[Action] > Memory usage dropped to 14%."
            ],
            IncidentType.LATENCY_SPIKE: [
                "[Action] > Detecting network partition...",
                "[Action] > Rerouting traffic via Secondary Region (us-east-2)",
                "[Action] > Flushing Redis Cache (order_cache)...",
                "[Action] > Latency P99 stabilized at 45ms."
            ],
            IncidentType.SERVICE_DOWN: [
                "[Action] > Service Check Failed (503 Service Unavailable)",
                "[Action] > Restarting Systemd Service: 'order-api'",
                "[Action] > Waiting for socket binding...",
                "[Action] > Health Check Passed (200 OK)."
            ],
            IncidentType.DISK_USAGE_HIGH: [
                "[Action] > Analyzing Disk Usage (/var/log)...",
                "[Action] > Found 45GB rotated logs. Compressing...",
                "[Action] > Moving old artifacts to S3 Bucket.",
                "[Action] > Disk Usage dropped to 65%."
            ],
            IncidentType.PROCESS_CRASH: [
                "[Action] > Detecting zombie process ID...",
                "[Action] > Sending SIGKILL to PID 4591",
                "[Action] > Restarting Worker Pool...",
                "[Action] > Workers online."
            ],
            IncidentType.DATABASE_LOCK: [
                "[Action] > Querying pg_locks...",
                "[Action] > Identified Deadlock: Transaction 99281 blocking 99282",
                "[Action] > Terminating blocking backend...",
                "[Action] > DB Concurrency returned to normal."
            ],
            IncidentType.SSL_EXPIRY: [
                "[Action] > Verifying Cert Chain...",
                "[Action] > Requesting new Let's Encrypt Certificate...",
                "[Action] > Deploying cert to Nginx Ingress...",
                "[Action] > Reloading Nginx. Cert Valid until 2026."
            ]
        }
        
        steps = playbooks.get(incident_type, playbooks[IncidentType.SERVICE_DOWN])
        
        for step in steps:
            self.log(step)
        
        # Resolve Jira
        active = [i for i in self.state_tracker.get_active() if i.id == incident_id]
        if active and active[0].jira_ticket_key and self.jira_connector:
             self.jira_connector.update_status(active[0].jira_ticket_key, "RESOLVED", "Issue resolved via AI Ops Agent action.")
             self.log(f"[Jira] Updated ticket {active[0].jira_ticket_key} to RESOLVED")

        # In a real simulation, we might go to MITIGATING -> MONITORING -> RESOLVED
        # For this instant demo:
        self.state_tracker.update_incident_state(incident_id, IncidentState.RESOLVED, self.tick_count)
        self.log(f"[Engine] Incident {incident_id} marked as RESOLVED.")
        
        # Clear analysis so UI resets
        if 'latest_analysis' in self.metrics:
            del self.metrics['latest_analysis']
        if 'agent_active' in self.metrics:
            del self.metrics['agent_active']
            
        # Set cooldown prevents immediate re-spawn from lingering logs
        self.cooldown_until = self.tick_count + 20
        self.log(f"[Engine] Cooldown active for 20 ticks.")
            
    def deny_action(self, incident_id: str):
        """
        User denied. Escalate.
        """
        self.log(f"[Engine] Action DENIED for {incident_id}. Escalating to L3 Support.")

        # Escalate Jira
        active = [i for i in self.state_tracker.get_active() if i.id == incident_id]
        if active:
             incident = active[0]
             # Ensure connector is alive
             connector = self.jira_connector
             if connector is None:
                 from src.integration.jira_client import JiraConnector
                 connector = JiraConnector(
                    url=os.getenv("JIRA_URL"),
                    username=os.getenv("JIRA_USERNAME"),
                    token=os.getenv("JIRA_API_TOKEN"),
                    project_key=os.getenv("JIRA_PROJECT_KEY", "KAN"),
                    mock=False
                 )

             # If no Jira ticket exists yet, create one before escalating
             if not incident.jira_ticket_key and connector:
                 self.log(f"[Engine] No Jira ticket for {incident_id}. Creating escalation ticket...")
                 analysis = incident.analysis or {}
                 root_cause_short = analysis.get('root_cause', 'Unknown Issue')[:100]
                 jira_summary = f"[AI Ops][ESCALATED] {incident.type.value} - {root_cause_short}"
                 jira_description = (
                     f"**Escalation Reason:** User denied AI-recommended action.\n\n"
                     f"**Root Cause Analysis**\n{analysis.get('root_cause', 'N/A')}\n\n"
                     f"**Symptoms**\n{analysis.get('summary', 'No details.')}\n\n"
                     f"**Recommended Action (Denied)**\n{analysis.get('top_recommendation', 'N/A')}"
                 )
                 ticket_key = connector.create_ticket({
                     'summary': jira_summary,
                     'root_cause': jira_description,
                     'severity': 'P1'
                 })
                 if not ticket_key.startswith("ERROR"):
                     incident.jira_ticket_key = ticket_key
                     self.log(f"[Engine] Escalation Jira Ticket Created: {ticket_key}")
                 else:
                     self.log(f"[Jira] CRITICAL: Escalation Ticket Creation Failed: {ticket_key}")

             # Update existing ticket status to ESCALATED
             if incident.jira_ticket_key and connector:
                 self.log(f"[Engine] Attempting to ESCALATE Jira Ticket {incident.jira_ticket_key}...")
                 success = connector.update_status(incident.jira_ticket_key, "ESCALATED", "User denied AI action. Escalating to L3.")
                 self.log(f"[Jira] Escalation Result: {success}")

        self.state_tracker.update_incident_state(incident_id, IncidentState.ESCALATED, self.tick_count)
        
    def trigger_reanalysis(self):
        """
        Forces the agent to re-evaluate active incidents with new context (e.g. manually injected logs).
        """
        active_list = self.state_tracker.get_active()
        if active_list:
            self.log(f"[Engine] Manual Trigger: Invalidating analysis for {len(active_list)} active incidents.")
            for incident in active_list:
                # Clearing analysis forces the agent loop to run again next tick
                incident.analysis = None
                
            # Also reset suppression if any
            self.cooldown_until = 0
            return True
        return False
