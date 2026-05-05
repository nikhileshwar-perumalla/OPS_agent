"""
Triage Agent - First responder for incident classification.
Extracts symptoms, classifies severity, and scores urgency.
"""

from .base_agent import BaseAgent
from .message_bus import AgentMessage, MessageType
from .llm_client import LLMClient
from typing import Optional


class TriageAgent(BaseAgent):
    """
    First responder. Classifies severity and extracts symptoms
    from raw metrics and log features.
    """

    def __init__(self, name: str, bus, llm_client: Optional[LLMClient] = None):
        super().__init__(name, bus)
        self.llm = llm_client

    def handle_message(self, message: AgentMessage) -> AgentMessage:
        metrics = message.payload.get('metrics_snapshot', {})
        log_features = message.payload.get('log_features', {})

        # ---- Symptom Extraction ----
        symptoms = []
        cpu = metrics.get('cpu_percent', 0)
        mem = metrics.get('memory_percent', 0)
        lat = metrics.get('latency_seconds', 0)
        disk = metrics.get('disk_percent', 0)

        if cpu > 80:
            symptoms.append(f"High CPU ({cpu:.1f}%)")
        if mem > 90:
            symptoms.append(f"High Memory ({mem:.1f}%)")
        if lat > 2.0:
            symptoms.append(f"High Latency ({lat:.3f}s)")
        if disk > 90:
            symptoms.append(f"High Disk Usage ({disk:.1f}%)")

        error_count = log_features.get('recent_errors', 0)
        if error_count > 0:
            symptoms.append(f"{error_count} recent errors detected")

        # Service-down heuristic
        if cpu < 2.0 and lat < 0.05 and error_count > 0:
            symptoms.append("Possible service outage (idle CPU with errors)")

        # ---- Urgency Scoring ----
        urgency_score = self._calculate_urgency(metrics, error_count)
        severity = self._classify_severity(urgency_score)

        # ---- LLM Enhancement (if available) ----
        llm_summary = None
        if self.llm and self.llm.is_active:
            llm_summary = self.llm.generate(
                system_prompt="You are an SRE triage specialist. Classify the incident severity and summarize symptoms in 2 sentences.",
                user_prompt=f"Metrics: CPU={cpu}%, Memory={mem}%, Latency={lat}s, Disk={disk}%. Errors: {error_count}. Log samples: {log_features.get('log_samples', [])[:3]}"
            )
            if llm_summary:
                symptoms.append(f"[AI Insight] {llm_summary}")

        self.log(f"Severity={severity}, Urgency={urgency_score:.2f}, Symptoms={len(symptoms)}")

        return AgentMessage(
            type=MessageType.TRIAGE_RESULT,
            sender=self.name,
            recipient="orchestrator",
            incident_id=message.incident_id,
            payload={
                'symptoms': symptoms,
                'severity': severity,
                'urgency_score': urgency_score,
                'metrics_snapshot': metrics,
                'log_features': log_features
            },
            parent_message_id=message.id
        )

    def _calculate_urgency(self, metrics, error_count):
        score = 0.0
        cpu = metrics.get('cpu_percent', 0)
        mem = metrics.get('memory_percent', 0)
        lat = metrics.get('latency_seconds', 0)

        if cpu > 95: score += 0.3
        elif cpu > 80: score += 0.15

        if mem > 95: score += 0.3
        elif mem > 90: score += 0.15

        if lat > 5.0: score += 0.3
        elif lat > 2.0: score += 0.15

        if error_count > 5: score += 0.2
        elif error_count > 0: score += 0.1

        return min(score, 1.0)

    def _classify_severity(self, urgency_score):
        if urgency_score >= 0.7:
            return "P1"
        elif urgency_score >= 0.4:
            return "P2"
        else:
            return "P3"
