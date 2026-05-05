"""
In-process message bus for agent-to-agent communication.
Lightweight synchronous implementation suitable for Streamlit's tick-based model.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
from datetime import datetime
import uuid


class MessageType(Enum):
    """Types of messages that flow between agents."""
    TRIAGE_REQUEST = "triage_request"
    TRIAGE_RESULT = "triage_result"
    DIAGNOSTICS_REQUEST = "diagnostics_request"
    DIAGNOSTICS_RESULT = "diagnostics_result"
    RCA_REQUEST = "rca_request"
    RCA_RESULT = "rca_result"
    REMEDIATION_REQUEST = "remediation_request"
    REMEDIATION_RESULT = "remediation_result"
    COMMS_REQUEST = "comms_request"
    COMMS_RESULT = "comms_result"
    FEEDBACK_REQUEST = "feedback_request"
    INCIDENT_COMPLETE = "incident_complete"


@dataclass
class AgentMessage:
    """A message passed between agents via the message bus."""
    type: MessageType
    sender: str
    recipient: str
    incident_id: str
    payload: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    parent_message_id: Optional[str] = None
    duration_ms: float = 0.0


class MessageBus:
    """
    Lightweight synchronous message bus for in-process agent communication.
    Agents register handlers; messages are delivered synchronously.
    """

    def __init__(self):
        self.history: List[AgentMessage] = []
        self.subscribers: Dict[str, Callable] = {}

    def register(self, agent_name: str, handler: Callable):
        """Register an agent's message handler."""
        self.subscribers[agent_name] = handler

    def send(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Send a message to the target agent and return its response."""
        self.history.append(message)
        handler = self.subscribers.get(message.recipient)
        if handler:
            response = handler(message)
            if response:
                self.history.append(response)
            return response
        return None

    def get_conversation(self, incident_id: str) -> List[AgentMessage]:
        """Get all messages for a specific incident."""
        return [m for m in self.history if m.incident_id == incident_id]

    def clear_conversation(self, incident_id: str):
        """Remove all messages for a specific incident (e.g., on re-analysis)."""
        self.history = [m for m in self.history if m.incident_id != incident_id]

    def get_stats(self) -> Dict:
        """Get bus statistics."""
        return {
            "total_messages": len(self.history),
            "registered_agents": list(self.subscribers.keys()),
            "incidents_tracked": len(set(m.incident_id for m in self.history))
        }
