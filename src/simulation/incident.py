from enum import Enum
import uuid
import random

class IncidentState(Enum):
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    INVESTIGATING = "INVESTIGATING"
    MITIGATING = "MITIGATING"
    MONITORING = "MONITORING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"

class IncidentType(Enum):
    HIGH_CPU = "high_cpu"
    MEMORY_LEAK = "memory_leak"
    LATENCY_SPIKE = "network_latency"
    SERVICE_DOWN = "service_down"
    DISK_USAGE_HIGH = "disk_usage_high"
    PROCESS_CRASH = "process_crash"
    DATABASE_LOCK = "database_lock"
    SSL_EXPIRY = "ssl_expiry"

class ActiveIncident:
    def __init__(self, incident_type: IncidentType, start_tick: int, severity="P2"):
        self.id = str(uuid.uuid4())[:8]
        self.type = incident_type
        self.severity = severity
        self.start_tick = start_tick
        self.state = IncidentState.DEGRADED
        self.history = []  # List of (tick, state)
        self.analysis = None # Store agent analysis persistence
        self.jira_ticket_key = None
        
    def transition(self, new_state: IncidentState, tick: int):
        # Strict Transition Logic can go here
        valid_transitions = {
            IncidentState.DEGRADED: [IncidentState.INVESTIGATING, IncidentState.RESOLVED, IncidentState.ESCALATED],
            IncidentState.INVESTIGATING: [IncidentState.MITIGATING, IncidentState.ESCALATED, IncidentState.RESOLVED],
            IncidentState.MITIGATING: [IncidentState.MONITORING, IncidentState.ESCALATED],
            IncidentState.MONITORING: [IncidentState.RESOLVED, IncidentState.DEGRADED],
            IncidentState.RESOLVED: [],
            IncidentState.ESCALATED: [IncidentState.RESOLVED]
        }
        
        # Allow force transition or check validity
        if new_state in valid_transitions.get(self.state, []) or new_state == IncidentState.ESCALATED:
            self.state = new_state
            self.history.append((tick, new_state))
            return True
        return False
