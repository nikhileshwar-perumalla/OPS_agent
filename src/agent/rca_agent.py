"""
RCA Agent v2 - Focused RAG-powered root cause analysis.
Refactored from monolithic RCAAgent to work within the multi-agent pipeline.
Receives diagnostic context, queries knowledge base, and returns ranked hypotheses.
"""

from .base_agent import BaseAgent
from .message_bus import AgentMessage, MessageType
from .llm_client import LLMClient
from src.rag.vector_db import KnowledgeBase
from typing import Optional


class RCAAgent(BaseAgent):
    """
    v2: Focused solely on RAG-powered root cause analysis.
    Receives diagnostic context, queries ChromaDB knowledge base,
    and returns ranked hypotheses with confidence scores.
    """

    def __init__(self, name: str, bus, llm_client: Optional[LLMClient] = None):
        super().__init__(name, bus)
        self.kb = KnowledgeBase()
        self.kb.populate('./data/historical_incidents.json')
        self.llm = llm_client

    def handle_message(self, message: AgentMessage) -> AgentMessage:
        diagnostics = message.payload.get('diagnostic_report', {})
        query_context = diagnostics.get('query_context', '')
        triage = message.payload.get('triage_report', {})

        # ---- RAG Retrieval ----
        rag_results = self.kb.search(query_context, n_results=3)
        hypotheses = self._formulate_hypotheses(rag_results, query_context)

        # ---- LLM-Enhanced Reasoning ----
        llm_reasoning = None
        if self.llm and self.llm.is_active and hypotheses:
            top = hypotheses[0]
            llm_reasoning = self.llm.generate(
                system_prompt=(
                    "You are an expert SRE performing root cause analysis. "
                    "Given the symptoms, diagnostics, and a candidate root cause from historical data, "
                    "provide a detailed reasoning chain explaining WHY this root cause is likely correct. "
                    "Be specific and reference the evidence. Keep it to 3-4 sentences."
                ),
                user_prompt=(
                    f"Symptoms: {triage.get('symptoms', [])}\n"
                    f"Diagnostic Summary: {diagnostics.get('readable_summary', '')}\n"
                    f"Error Patterns: {diagnostics.get('error_patterns', [])}\n"
                    f"Candidate Root Cause: {top.get('root_cause', 'Unknown')}\n"
                    f"Historical Match: {top.get('reasoning', '')}\n"
                    f"Confidence: {top.get('confidence', 0):.2f}"
                )
            )
            if llm_reasoning:
                # Enhance the top hypothesis reasoning with LLM output
                hypotheses[0]['reasoning'] = llm_reasoning

        top_root_cause = hypotheses[0] if hypotheses else None
        rag_match_count = len(rag_results.get('documents', [[]])[0]) if rag_results else 0

        self.log(f"Found {rag_match_count} RAG matches, {len(hypotheses)} hypotheses, "
                 f"Top confidence: {top_root_cause['confidence']:.2f}" if top_root_cause else "No matches")

        return AgentMessage(
            type=MessageType.RCA_RESULT,
            sender=self.name,
            recipient="orchestrator",
            incident_id=message.incident_id,
            payload={
                'hypotheses': hypotheses,
                'top_root_cause': top_root_cause,
                'llm_reasoning': llm_reasoning,
                'rag_match_count': rag_match_count
            },
            parent_message_id=message.id
        )

    def _formulate_hypotheses(self, rag_results, query_context):
        """Generate ranked hypotheses from RAG results."""
        hypotheses = []

        if rag_results and rag_results.get('documents'):
            for i, doc in enumerate(rag_results['documents'][0]):
                meta = rag_results['metadatas'][0][i]
                dist = rag_results['distances'][0][i]

                confidence = 1.0 / (1.0 + dist)

                hypotheses.append({
                    "root_cause": meta.get('root_cause', 'Unknown'),
                    "action": meta.get('recommended_action', 'Escalate'),
                    "confidence": confidence,
                    "reasoning": (
                        f"Matches historical incident: {meta.get('summary')} "
                        f"(Confidence: {confidence:.2f}). "
                        f"Evidence: {query_context[:100]}..."
                    ),
                    "historical_id": meta.get('id', 'N/A'),
                    "resolution": meta.get('resolution', '')
                })

        # Fallback
        if not hypotheses:
            hypotheses.append({
                "root_cause": "Unknown Anomaly",
                "action": "Escalate to L3",
                "confidence": 0.1,
                "reasoning": "No RAG matches found. Manual investigation required.",
                "historical_id": "N/A",
                "resolution": ""
            })

        hypotheses.sort(key=lambda x: x['confidence'], reverse=True)
        return hypotheses
