from typing import List
from .incident import ActiveIncident, IncidentState

class StateTracker:
    """
    Manages the lifecycle and strict transitions of incidents.
    """
    def __init__(self):
        self.active_incidents: List[ActiveIncident] = []
        self.resolved_log: List[ActiveIncident] = []
        
    def register_incident(self, incident: ActiveIncident):
        self.active_incidents.append(incident)
        
    def get_active(self):
        # Simply return the list, as we maintain it strict
        return self.active_incidents
        
    def update_incident_state(self, incident_id: str, new_state: IncidentState, tick: int):
        for idx, incident in enumerate(self.active_incidents):
            if incident.id == incident_id:
                success = incident.transition(new_state, tick)
                if success:
                    print(f"[StateTracker] Incident {incident_id} transitioned to {new_state.value}")
                    if new_state == IncidentState.RESOLVED:
                         # Move to archive
                         self.resolved_log.append(incident)
                         self.active_incidents.pop(idx)
                else:
                    print(f"[StateTracker] Invalid transition for {incident_id}: {incident.state} -> {new_state}")
                return success
        return False
