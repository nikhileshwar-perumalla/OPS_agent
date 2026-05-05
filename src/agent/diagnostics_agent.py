"""
Diagnostics Agent - Deep log analysis, pattern correlation, and service identification.
"""

from .base_agent import BaseAgent
from .message_bus import AgentMessage, MessageType
from .llm_client import LLMClient
from typing import Optional, List


class DiagnosticsAgent(BaseAgent):
    """
    Deep analysis of logs and metrics. Correlates error patterns
    with affected services and generates diagnostic context for RCA.
    """

    def __init__(self, name: str, bus, llm_client: Optional[LLMClient] = None):
        super().__init__(name, bus)
        self.llm = llm_client

    def handle_message(self, message: AgentMessage) -> AgentMessage:
        triage = message.payload.get('triage_report', {})
        log_features = triage.get('log_features', {})
        log_samples = log_features.get('log_samples', [])
        symptoms = triage.get('symptoms', [])
        metrics = triage.get('metrics_snapshot', {})

        # ---- Error Pattern Extraction ----
        error_patterns = self._extract_error_patterns(log_samples)

        # ---- Affected Service Identification ----
        affected_services = self._identify_affected_services(log_samples)

        # ---- Symptom Correlation ----
        correlated_symptoms = self._correlate(symptoms, error_patterns, metrics)

        # ---- Build RAG Query Context ----
        query_context = ", ".join(symptoms)
        if log_samples:
            query_context += ". Logs: " + "; ".join(log_samples[:5])

        # ---- Readable Summary (Rule-based) ----
        readable_summary = self._build_readable_summary(symptoms, error_patterns)

        # ---- LLM Enhancement ----
        llm_enhanced = False
        if self.llm and self.llm.is_active:
            llm_result = self.llm.generate(
                system_prompt=(
                    "You are an SRE diagnostics specialist. Analyze the following system symptoms "
                    "and error logs. Identify the most likely failure pattern, affected components, "
                    "and provide a concise diagnostic summary in 3-4 sentences."
                ),
                user_prompt=(
                    f"Symptoms: {symptoms}\n"
                    f"Error Patterns: {error_patterns}\n"
                    f"Affected Services: {affected_services}\n"
                    f"Log Samples: {log_samples[:5]}\n"
                    f"Metrics: CPU={metrics.get('cpu_percent')}%, "
                    f"Memory={metrics.get('memory_percent')}%, "
                    f"Latency={metrics.get('latency_seconds')}s"
                )
            )
            if llm_result:
                readable_summary = llm_result
                llm_enhanced = True

        self.log(f"Patterns={len(error_patterns)}, Services={affected_services}, LLM={'Yes' if llm_enhanced else 'No'}")

        return AgentMessage(
            type=MessageType.DIAGNOSTICS_RESULT,
            sender=self.name,
            recipient="orchestrator",
            incident_id=message.incident_id,
            payload={
                'error_patterns': error_patterns,
                'affected_services': affected_services,
                'correlated_symptoms': correlated_symptoms,
                'query_context': query_context,
                'readable_summary': readable_summary,
                'llm_enhanced': llm_enhanced
            },
            parent_message_id=message.id
        )

    def _extract_error_patterns(self, log_samples: List[str]) -> List[str]:
        """Extract unique error patterns from log samples."""
        patterns = set()
        for log in log_samples:
            if "[" in log and "]" in log:
                try:
                    comp = log.split("[")[1].split("]")[0]
                    msg = log.split("]")[1].strip().split(":")[0]
                    if len(msg) > 50:
                        msg = msg[:50] + "..."
                    patterns.add(f"[{comp}] {msg}")
                except (IndexError, ValueError):
                    pass
            elif "Exception" in log:
                try:
                    patterns.add(log.split()[-1].split(":")[-1])
                except (IndexError, ValueError):
                    pass
            elif "ERROR" in log or "CRITICAL" in log:
                # Extract the message portion
                parts = log.split(" - ")
                if len(parts) > 1:
                    patterns.add(parts[-1].strip()[:80])
                else:
                    patterns.add(log[:80])
        return list(patterns)

    def _identify_affected_services(self, log_samples: List[str]) -> List[str]:
        """Identify affected services from log entries."""
        services = set()
        service_keywords = {
            "UserService": ["user", "profile", "auth", "login"],
            "SearchService": ["search", "query", "index"],
            "Backend": ["api", "backend", "server"],
            "Database": ["db", "database", "sql", "postgres", "connection pool"],
            "Cache": ["redis", "cache", "memcached"],
            "Gateway": ["gateway", "nginx", "load balancer", "lb"],
        }
        for log in log_samples:
            log_lower = log.lower()
            for service, keywords in service_keywords.items():
                if any(kw in log_lower for kw in keywords):
                    services.add(service)
        if not services:
            services.add("Backend")
        return list(services)

    def _correlate(self, symptoms, error_patterns, metrics) -> List[str]:
        """Correlate symptoms with error patterns to build a richer picture."""
        correlations = []
        cpu = metrics.get('cpu_percent', 0)
        mem = metrics.get('memory_percent', 0)
        lat = metrics.get('latency_seconds', 0)

        if cpu > 90 and any("timeout" in p.lower() for p in error_patterns):
            correlations.append("High CPU causing request timeouts")
        if mem > 95 and any("oom" in p.lower() or "memory" in p.lower() for p in error_patterns):
            correlations.append("Memory exhaustion causing OOM kills")
        if lat > 3.0 and any("connection" in p.lower() for p in error_patterns):
            correlations.append("Network/DB connection issues causing latency spikes")
        if any("503" in p or "unavailable" in p.lower() for p in error_patterns):
            correlations.append("Service returning 503 - possible backend outage")
        if any("refused" in p.lower() or "pool" in p.lower() for p in error_patterns):
            correlations.append("Connection pool exhaustion detected")

        # Add raw symptoms if no correlations found
        if not correlations:
            correlations = list(symptoms)

        return correlations

    def _build_readable_summary(self, symptoms, error_patterns) -> str:
        """Build a human-readable diagnostic summary."""
        parts = list(symptoms)
        if error_patterns:
            if len(error_patterns) == 1:
                parts.append(f"Issue appears to be {error_patterns[0]}")
            else:
                parts.append(f"Multiple failures: {', '.join(error_patterns[:3])}")
        elif not parts:
            parts.append("No clear error pattern identified")
        return ". ".join(parts) + "."
