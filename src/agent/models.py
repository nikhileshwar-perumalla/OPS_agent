from dataclasses import dataclass
from typing import List

@dataclass
class Hypothesis:
    root_cause: str
    confidence: float
    action: str
    reasoning: str

@dataclass
class AnalysisResult:
    incident_id: str
    hypotheses: List[Hypothesis]
    top_recommendation: str
    severity: str
    needs_approval: bool
