"""
Orchestrator Agent - Central coordinator for the multi-agent incident response pipeline.
Manages workflow state machine, routes messages between agents, handles feedback loops.
"""

import time
from datetime import datetime
from typing import Optional, Dict, Any

from .message_bus import MessageBus, AgentMessage, MessageType
from .llm_client import LLMClient
from .triage_agent import TriageAgent
from .diagnostics_agent import DiagnosticsAgent
from .rca_agent import RCAAgent
from .remediation_agent import RemediationAgent
from .comms_agent import CommunicationsAgent


class OrchestratorAgent:
    """
    Central coordinator. Manages the incident analysis workflow
    by routing messages between specialized agents in sequence.

    Workflow: Triage → Diagnostics → RCA → Remediation → Communications

    Features:
    - Sequential pipeline with result passing
    - Feedback loop: if RCA confidence < 0.3, re-requests diagnostics
    - Returns legacy-compatible dict for engine integration
    - Tracks per-stage timing and status
    """

    def __init__(self, bus: MessageBus,
                 slack_notifier=None, jira_connector=None,
                 llm_client: Optional[LLMClient] = None):
        self.bus = bus
        self.llm = llm_client or LLMClient()
        self._logs = []

        # Initialize all specialized agents
        self.triage = TriageAgent("triage", bus, llm_client=self.llm)
        self.diagnostics = DiagnosticsAgent("diagnostics", bus, llm_client=self.llm)
        self.rca = RCAAgent("rca", bus, llm_client=self.llm)
        self.remediation = RemediationAgent("remediation", bus, llm_client=self.llm)
        self.comms = CommunicationsAgent("comms", bus,
                                          slack_notifier=slack_notifier,
                                          jira_connector=jira_connector)

        self.log("Multi-agent system initialized with 5 agents")
        self.log(f"LLM Mode: {'Active (' + self.llm.model + ')' if self.llm.is_active else 'Mock (rule-based)'}")

    def log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] [orchestrator] {msg}"
        print(entry)
        self._logs.append(entry)
        if len(self._logs) > 100:
            self._logs.pop(0)

    def process_incident(self, metrics_snapshot: dict, log_features: dict,
                         incident_id: str, context: Optional[Dict] = None) -> dict:
        """
        Runs the full multi-agent pipeline synchronously.

        Args:
            metrics_snapshot: Current system metrics
            log_features: Extracted log features from ObservationWindow
            incident_id: The incident being analyzed
            context: Optional dict with {slack_sent, jira_ticket_key, incident_type}

        Returns:
            Dict compatible with the legacy analyze_incident() output shape,
            plus additional multi-agent fields.
        """
        context = context or {}
        pipeline_start = time.time()
        workflow_stages = {}

        self.log(f"=== Starting Multi-Agent Pipeline for Incident {incident_id} ===")

        # Clear any previous conversation for this incident (re-analysis)
        self.bus.clear_conversation(incident_id)

        # ================================================================
        # PHASE 1: TRIAGE
        # ================================================================
        stage_start = time.time()
        self.log("[Phase 1/5] Triage Agent - Classifying severity...")

        triage_msg = AgentMessage(
            type=MessageType.TRIAGE_REQUEST,
            sender="orchestrator",
            recipient="triage",
            incident_id=incident_id,
            payload={
                'metrics_snapshot': metrics_snapshot,
                'log_features': log_features
            }
        )
        triage_result = self.bus.send(triage_msg)
        triage_payload = triage_result.payload if triage_result else {}

        workflow_stages['triage'] = {
            'status': 'complete' if triage_result else 'error',
            'duration_ms': round((time.time() - stage_start) * 1000, 1),
            'output_summary': f"Severity: {triage_payload.get('severity', '?')}, "
                              f"Symptoms: {len(triage_payload.get('symptoms', []))}"
        }

        # ================================================================
        # PHASE 2: DIAGNOSTICS
        # ================================================================
        stage_start = time.time()
        self.log("[Phase 2/5] Diagnostics Agent - Analyzing patterns...")

        diag_msg = AgentMessage(
            type=MessageType.DIAGNOSTICS_REQUEST,
            sender="orchestrator",
            recipient="diagnostics",
            incident_id=incident_id,
            payload={'triage_report': triage_payload}
        )
        diag_result = self.bus.send(diag_msg)
        diag_payload = diag_result.payload if diag_result else {}

        workflow_stages['diagnostics'] = {
            'status': 'complete' if diag_result else 'error',
            'duration_ms': round((time.time() - stage_start) * 1000, 1),
            'output_summary': f"Patterns: {len(diag_payload.get('error_patterns', []))}, "
                              f"Services: {diag_payload.get('affected_services', [])}"
        }

        # ================================================================
        # PHASE 3: ROOT CAUSE ANALYSIS
        # ================================================================
        stage_start = time.time()
        self.log("[Phase 3/5] RCA Agent - Searching knowledge base...")

        rca_msg = AgentMessage(
            type=MessageType.RCA_REQUEST,
            sender="orchestrator",
            recipient="rca",
            incident_id=incident_id,
            payload={
                'diagnostic_report': diag_payload,
                'triage_report': triage_payload
            }
        )
        rca_result = self.bus.send(rca_msg)
        rca_payload = rca_result.payload if rca_result else {}

        # ---- Feedback Loop: Low Confidence → Re-diagnose ----
        retried = False
        top = rca_payload.get('top_root_cause') or {}
        if top.get('confidence', 0) < 0.3 and diag_payload:
            retried = True
            self.log("[Feedback] Low RCA confidence (<0.3). Requesting expanded diagnostics...")

            # Request expanded diagnostics with more context
            expanded_triage = dict(triage_payload)
            expanded_triage['log_features'] = log_features  # Pass full features again
            expanded_triage['symptoms'] = triage_payload.get('symptoms', []) + \
                                          diag_payload.get('correlated_symptoms', [])

            diag_msg2 = AgentMessage(
                type=MessageType.DIAGNOSTICS_REQUEST,
                sender="orchestrator",
                recipient="diagnostics",
                incident_id=incident_id,
                payload={'triage_report': expanded_triage}
            )
            diag_result2 = self.bus.send(diag_msg2)
            if diag_result2:
                diag_payload = diag_result2.payload
                # Re-run RCA with expanded context
                rca_msg2 = AgentMessage(
                    type=MessageType.RCA_REQUEST,
                    sender="orchestrator",
                    recipient="rca",
                    incident_id=incident_id,
                    payload={
                        'diagnostic_report': diag_payload,
                        'triage_report': expanded_triage
                    }
                )
                rca_result2 = self.bus.send(rca_msg2)
                if rca_result2:
                    rca_payload = rca_result2.payload
                    self.log("[Feedback] RCA re-run complete with expanded context")

        workflow_stages['rca'] = {
            'status': 'complete' if rca_result else 'error',
            'duration_ms': round((time.time() - stage_start) * 1000, 1),
            'retried': retried,
            'output_summary': f"Hypotheses: {len(rca_payload.get('hypotheses', []))}, "
                              f"Top confidence: {(rca_payload.get('top_root_cause') or {}).get('confidence', 0):.2f}"
        }

        # ================================================================
        # PHASE 4: REMEDIATION
        # ================================================================
        stage_start = time.time()
        self.log("[Phase 4/5] Remediation Agent - Checking safety & selecting action...")

        rem_msg = AgentMessage(
            type=MessageType.REMEDIATION_REQUEST,
            sender="orchestrator",
            recipient="remediation",
            incident_id=incident_id,
            payload={
                'rca_report': rca_payload,
                'triage_report': triage_payload,
                'incident_type': context.get('incident_type', 'unknown')
            }
        )
        rem_result = self.bus.send(rem_msg)
        rem_payload = rem_result.payload if rem_result else {}

        workflow_stages['remediation'] = {
            'status': 'complete' if rem_result else 'error',
            'duration_ms': round((time.time() - stage_start) * 1000, 1),
            'output_summary': f"Action: {rem_payload.get('recommended_action', '?')}, "
                              f"Safety: {rem_payload.get('safety_status', '?')}"
        }

        # ================================================================
        # PHASE 5: COMMUNICATIONS
        # ================================================================
        stage_start = time.time()
        self.log("[Phase 5/5] Communications Agent - Sending notifications...")

        top_rc = rca_payload.get('top_root_cause') or {}
        comms_msg = AgentMessage(
            type=MessageType.COMMS_REQUEST,
            sender="orchestrator",
            recipient="comms",
            incident_id=incident_id,
            payload={
                'summary': diag_payload.get('readable_summary', 'No details.'),
                'severity': triage_payload.get('severity', 'P2'),
                'top_recommendation': rem_payload.get('recommended_action', 'Escalate'),
                'top_hypothesis': top_rc,
                'already_slack_sent': context.get('slack_sent', False),
                'existing_jira_key': context.get('jira_ticket_key', None),
                'incident_type': context.get('incident_type', 'unknown')
            }
        )
        comms_result = self.bus.send(comms_msg)
        comms_payload = comms_result.payload if comms_result else {}

        workflow_stages['comms'] = {
            'status': 'complete' if comms_result else 'error',
            'duration_ms': round((time.time() - stage_start) * 1000, 1),
            'output_summary': f"Slack: {'✓' if comms_payload.get('slack_sent') else '✗'}, "
                              f"Jira: {comms_payload.get('jira_ticket_key', 'N/A')}"
        }

        # ================================================================
        # BUILD LEGACY-COMPATIBLE RESULT
        # ================================================================
        total_time = round((time.time() - pipeline_start) * 1000, 1)
        self.log(f"=== Pipeline Complete ({total_time}ms) ===")

        # Build agent conversation for dashboard
        conversation = self._build_conversation_log(incident_id)

        result = {
            # Legacy-compatible fields (same as old RCAAgent.analyze_incident)
            "incident_id": incident_id,
            "hypotheses": rca_payload.get('hypotheses', []),
            "top_recommendation": rem_payload.get('recommended_action', 'Escalate to L3'),
            "severity": triage_payload.get('severity', 'P2'),
            "needs_approval": rem_payload.get('needs_approval', True),
            "summary": diag_payload.get('readable_summary', 'No details.'),
            "evidence": diag_payload.get('query_context', ''),

            # New multi-agent fields
            "jira_ticket_key": comms_payload.get('jira_ticket_key'),
            "slack_sent": comms_payload.get('slack_sent', False),
            "workflow_stages": workflow_stages,
            "agent_conversation": conversation,
            "pipeline_duration_ms": total_time,

            # Per-agent reports (for detailed dashboard)
            "triage_report": triage_payload,
            "diagnostic_report": diag_payload,
            "rca_report": rca_payload,
            "remediation_plan": rem_payload,
            "comms_report": comms_payload,

            # LLM metadata
            "llm_active": self.llm.is_active if self.llm else False,
        }

        return result

    def _build_conversation_log(self, incident_id: str) -> list:
        """Build a serializable conversation log for the dashboard."""
        messages = self.bus.get_conversation(incident_id)
        conversation = []
        for msg in messages:
            conversation.append({
                'id': msg.id,
                'type': msg.type.value,
                'sender': msg.sender,
                'recipient': msg.recipient,
                'timestamp': msg.timestamp,
                'duration_ms': msg.duration_ms,
                'payload_keys': list(msg.payload.keys()) if msg.payload else [],
                'payload_summary': self._summarize_payload(msg)
            })
        return conversation

    def _summarize_payload(self, msg: AgentMessage) -> str:
        """Create a one-line summary of a message's payload."""
        p = msg.payload
        if msg.type == MessageType.TRIAGE_RESULT:
            return f"Severity={p.get('severity')}, {len(p.get('symptoms',[]))} symptoms, urgency={p.get('urgency_score',0):.2f}"
        elif msg.type == MessageType.DIAGNOSTICS_RESULT:
            return f"{len(p.get('error_patterns',[]))} patterns, services={p.get('affected_services',[])}"
        elif msg.type == MessageType.RCA_RESULT:
            top = p.get('top_root_cause') or {}
            return f"{len(p.get('hypotheses',[]))} hypotheses, top={top.get('root_cause','?')[:50]}"
        elif msg.type == MessageType.REMEDIATION_RESULT:
            return f"Action='{p.get('recommended_action')}', safety={p.get('safety_status')}"
        elif msg.type == MessageType.COMMS_RESULT:
            return f"Slack={'✓' if p.get('slack_sent') else '✗'}, Jira={p.get('jira_ticket_key','N/A')}"
        else:
            return f"{len(p)} fields"

    def get_agent_stats(self) -> dict:
        """Get performance stats for all agents."""
        return {
            "triage": self.triage.get_stats(),
            "diagnostics": self.diagnostics.get_stats(),
            "rca": self.rca.get_stats(),
            "remediation": self.remediation.get_stats(),
            "comms": self.comms.get_stats(),
            "bus": self.bus.get_stats(),
            "llm": self.llm.get_stats() if self.llm else {}
        }

    def get_all_logs(self) -> list:
        """Get logs from all agents combined."""
        all_logs = list(self._logs)
        for agent in [self.triage, self.diagnostics, self.rca,
                      self.remediation, self.comms]:
            all_logs.extend(agent._logs)
        all_logs.sort()
        return all_logs[-50:]
