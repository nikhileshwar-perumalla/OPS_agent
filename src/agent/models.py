"""
Data models for the multi-agent system.
Extends original models with per-agent report types and workflow tracking.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class Hypothesis:
    root_cause: str
    confidence: float
    action: str
    reasoning: str


@dataclass
class TriageReport:
    symptoms: List[str]
    severity: str          # P1, P2, P3
    urgency_score: float   # 0.0 - 1.0
    metrics_snapshot: Dict[str, Any] = field(default_factory=dict)
    log_features: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagnosticReport:
    error_patterns: List[str]
    affected_services: List[str]
    correlated_symptoms: List[str]
    query_context: str
    readable_summary: str
    llm_enhanced: bool = False


@dataclass
class RCAReport:
    hypotheses: List[Dict[str, Any]]
    top_root_cause: Optional[Dict[str, Any]] = None
    llm_reasoning: Optional[str] = None
    rag_match_count: int = 0


@dataclass
class RemediationPlan:
    recommended_action: str
    needs_approval: bool
    safety_status: str     # ALLOWED, REQUIRES_APPROVAL, BLOCKED
    safety_message: str
    confidence: float
    playbook_id: Optional[str] = None


@dataclass
class CommsReport:
    slack_sent: bool = False
    jira_ticket_key: Optional[str] = None
    notification_status: str = "pending"
    errors: List[str] = field(default_factory=list)


@dataclass
class WorkflowStage:
    agent_name: str
    status: str         # "pending", "running", "complete", "error", "skipped"
    duration_ms: float = 0.0
    output_summary: str = ""


@dataclass
class AnalysisResult:
    """Legacy-compatible analysis result returned by the orchestrator."""
    incident_id: str
    hypotheses: List[Dict[str, Any]]
    top_recommendation: str
    severity: str
    needs_approval: bool
    summary: str = ""
    evidence: str = ""
    jira_ticket_key: Optional[str] = None
    slack_sent: bool = False
    workflow_stages: Dict[str, Dict] = field(default_factory=dict)
    agent_conversation: List[Dict] = field(default_factory=list)
    triage_report: Optional[Dict] = None
    diagnostic_report: Optional[Dict] = None
    rca_report: Optional[Dict] = None
    remediation_plan: Optional[Dict] = None
    comms_report: Optional[Dict] = None
