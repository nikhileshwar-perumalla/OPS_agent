"""
Remediation Agent - Action recommendation, policy safety checks, and playbook selection.
"""

from .base_agent import BaseAgent
from .message_bus import AgentMessage, MessageType
from .llm_client import LLMClient
from src.orchestration.policy_engine import PolicyEngine
from typing import Optional


class RemediationAgent(BaseAgent):
    """
    Determines the best recovery action based on RCA results,
    checks safety via PolicyEngine, and selects the appropriate playbook.
    """

    def __init__(self, name: str, bus, llm_client: Optional[LLMClient] = None):
        super().__init__(name, bus)
        self.policy_engine = PolicyEngine()
        self.llm = llm_client

    def handle_message(self, message: AgentMessage) -> AgentMessage:
        rca_report = message.payload.get('rca_report', {})
        triage_report = message.payload.get('triage_report', {})
        incident_type = message.payload.get('incident_type', 'unknown')
        top = rca_report.get('top_root_cause') or {}

        recommended_action = top.get('action', 'Escalate to L3')
        confidence = top.get('confidence', 0.0)
        severity = triage_report.get('severity', 'P2')

        # ---- Policy Safety Check ----
        safety_status, safety_msg = self.policy_engine.check_safety(recommended_action)

        # ---- Approval Logic ----
        needs_approval = True
        if safety_status == "ALLOWED" and confidence > 0.85:
            needs_approval = False
        elif safety_status == "BLOCKED":
            recommended_action = "Escalate to L3"
            needs_approval = False  # Auto-escalate

        # P1 always needs approval unless blocked
        if severity == "P1" and safety_status != "BLOCKED":
            needs_approval = True

        # ---- Playbook Selection ----
        playbook_id = self._select_playbook(incident_type, recommended_action)

        # ---- LLM Enhancement ----
        if self.llm and self.llm.is_active:
            llm_plan = self.llm.generate(
                system_prompt=(
                    "You are an SRE remediation specialist. Given the root cause analysis "
                    "and recommended action, provide a brief step-by-step remediation plan "
                    "in 3-5 numbered steps. Be specific and actionable."
                ),
                user_prompt=(
                    f"Root Cause: {top.get('root_cause', 'Unknown')}\n"
                    f"Recommended Action: {recommended_action}\n"
                    f"Severity: {severity}\n"
                    f"Incident Type: {incident_type}\n"
                    f"Safety Status: {safety_status}"
                )
            )
            if llm_plan:
                safety_msg = f"{safety_msg}\n\n[AI Remediation Plan]\n{llm_plan}"

        self.log(f"Action='{recommended_action}', Safety={safety_status}, "
                 f"NeedsApproval={needs_approval}, Playbook={playbook_id}")

        return AgentMessage(
            type=MessageType.REMEDIATION_RESULT,
            sender=self.name,
            recipient="orchestrator",
            incident_id=message.incident_id,
            payload={
                'recommended_action': recommended_action,
                'needs_approval': needs_approval,
                'safety_status': safety_status,
                'safety_message': safety_msg,
                'confidence': confidence,
                'playbook_id': playbook_id,
                'severity': severity
            },
            parent_message_id=message.id
        )

    def _select_playbook(self, incident_type, action):
        """Map incident type and action to a playbook identifier."""
        playbook_map = {
            "high_cpu": "PB-CPU-001",
            "memory_leak": "PB-MEM-001",
            "network_latency": "PB-NET-001",
            "service_down": "PB-SVC-001",
            "disk_usage_high": "PB-DSK-001",
            "process_crash": "PB-PRC-001",
            "database_lock": "PB-DBL-001",
            "ssl_expiry": "PB-SSL-001",
        }
        return playbook_map.get(incident_type, "PB-GEN-000")
