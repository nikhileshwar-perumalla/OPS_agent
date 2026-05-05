import json
from src.rag.vector_db import KnowledgeBase

class RCAAgent:
    def __init__(self):
        self.kb = KnowledgeBase()
        self.kb.populate('./data/historical_incidents.json')
        # Placeholder for real LLM client (OpenAI/Ollama)
        # For this demo, we can simulate the LLM response if no key is provided, 
        # but the structure will be ready for real integration.
        self.mock_mode = True 

    def analyze_incident(self, metrics_snapshot, recent_logs, incident_id=None) -> dict:
        """
        Ranked Analysis of Incident.
        """
        # 1. Summarize
        symptoms = []
        if metrics_snapshot.get('cpu_percent', 0) > 80: symptoms.append("High CPU")
        if metrics_snapshot.get('memory_percent', 0) > 90: symptoms.append("High Memory")
        if metrics_snapshot.get('latency_seconds', 0) > 2.0: symptoms.append("High Latency")
        
        # Log analysis
        error_count = recent_logs.get('recent_errors', 0)
        if error_count > 0:
            symptoms.append(f"{error_count} Errors/sec")
            
        # Add actual log text to context (for RAG search)
        log_samples = recent_logs.get('log_samples', [])
        evidence_text = ""
        if log_samples:
            evidence_text = f"Logs: {'; '.join(log_samples)}"
            
        query_context = ", ".join(symptoms) + ". " + evidence_text
        
        # Smart Summary Generation
        # Extract unique component/error types for readability
        readable_symptoms = list(symptoms) # Copy basic metrics
        
        unique_errors = set()
        for log in log_samples:
            # Simple heuristic: Extract [Component] or Exception name
            if "[" in log and "]" in log:
                try:
                    comp = log.split("[")[1].split("]")[0]
                    msg = log.split("]")[1].strip().split(":")[0] # specific error part
                    if len(msg) > 30: msg = msg[:30] + "..."
                    unique_errors.add(f"[{comp}] {msg}")
                except:
                    pass
            elif "Exception" in log:
                unique_errors.add(log.split()[-1].split(":")[-1])
        
        if unique_errors:
            # Natural Language Construction
            error_list = list(unique_errors)
            if len(error_list) == 1:
                readable_symptoms.append(f"Issue appears to be {error_list[0]}")
            else:
                readable_symptoms.append(f"Multiple failures detected: {', '.join(error_list[:2])}")
        elif log_samples:
             readable_symptoms.append("Application is throwing generic errors")

        # 2. RAG Retrieval
        rag_results = self.kb.search(query_context, n_results=3) # Get top 3
        
        hypotheses = []
        
        # 3. Formulate Hypotheses
        if rag_results and rag_results['documents']:
            for i, doc in enumerate(rag_results['documents'][0]):
                meta = rag_results['metadatas'][0][i]
                dist = rag_results['distances'][0][i]
                
                # Confidence Score
                confidence = 1.0 / (1.0 + dist)
                
                hypotheses.append({
                    "root_cause": meta.get('root_cause', 'Unknown'),
                    "action": meta.get('recommended_action', 'Escalate'),
                    "confidence": confidence,
                    "reasoning": f"Matches similar incident: {meta.get('summary')} (Conf: {confidence:.2f}). Evidence: {query_context[:100]}..."
                })
        
        # Fallback if empty (e.g. cold start)
        if not hypotheses:
            hypotheses.append({
                "root_cause": "Unknown Anomaly",
                "action": "Escalate to L3",
                "confidence": 0.1,
                "reasoning": "No RAG matches found."
            })
            
        # Sort by confidence
        hypotheses.sort(key=lambda x: x['confidence'], reverse=True)
        top = hypotheses[0]
        
        # Decision
        needs_approval = True
        if top['confidence'] > 0.85 and "Restart" in top['action']:
             needs_approval = False # Auto-action for very high confidence (example)
        
        final_summary = ". ".join(readable_symptoms) + "."
             
        return {
            "incident_id": incident_id,
            "hypotheses": hypotheses,
            "top_recommendation": top['action'],
            "severity": "P2", # placeholder
            "needs_approval": needs_approval,
            "summary": final_summary,
            "evidence": evidence_text 
        }
