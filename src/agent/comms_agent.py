"""
Communications Agent - Handles all external notifications (Slack, Jira).
Extracted from SimulationEngine.tick() to decouple notification from analysis.
"""

from .base_agent import BaseAgent
from .message_bus import AgentMessage, MessageType
from typing import Optional
import os


class CommunicationsAgent(BaseAgent):
    """
    Handles all external communications: Slack alerts and Jira ticket creation.
    Only sends notifications when needed (checks slack_sent / jira_ticket_key flags).
    """

    def __init__(self, name: str, bus,
                 slack_notifier=None, jira_connector=None):
        super().__init__(name, bus)
        self.slack = slack_notifier
        self.jira = jira_connector

    def handle_message(self, message: AgentMessage) -> AgentMessage:
        payload = message.payload
        incident_id = message.incident_id

        # Context flags from orchestrator
        already_slack_sent = payload.get('already_slack_sent', False)
        existing_jira_key = payload.get('existing_jira_key', None)
        incident_type = payload.get('incident_type', 'unknown')

        # Analysis data
        summary = payload.get('summary', 'No details.')
        severity = payload.get('severity', 'P2')
        top_recommendation = payload.get('top_recommendation', 'Escalate')
        top_hypothesis = payload.get('top_hypothesis') or {}
        root_cause = top_hypothesis.get('root_cause', 'Unknown')
        confidence = top_hypothesis.get('confidence', 0.0)

        slack_sent = already_slack_sent
        jira_ticket_key = existing_jira_key
        errors = []

        # ---- Slack Notification ----
        if self.slack and not already_slack_sent:
            self.log(f"Sending Slack alert for {incident_id}")
            try:
                slack_data = {
                    'summary': summary,
                    'root_cause': root_cause,
                    'action': top_recommendation,
                    'confidence': confidence,
                    'severity': severity,
                }
                resp = self.slack.post_incident(slack_data, ticket_id=incident_id)
                slack_sent = resp.get('ok', False)
                if slack_sent:
                    self.log(f"Slack alert sent successfully")
                else:
                    errors.append(f"Slack send failed: {resp.get('error', 'unknown')}")
            except Exception as e:
                errors.append(f"Slack error: {str(e)}")
                self.log(f"Slack error: {e}")

        # ---- Jira Ticket Creation ----
        if self.jira and not existing_jira_key:
            self.log(f"Creating Jira ticket for {incident_id}")
            try:
                root_cause_short = root_cause[:100] if root_cause else 'Unknown Issue'
                jira_summary = f"[AI Ops] {incident_type} - {root_cause_short}"
                jira_description = (
                    f"**Root Cause Analysis**\n{root_cause}\n\n"
                    f"**Symptoms**\n{summary}\n\n"
                    f"**Recommended Action**\n{top_recommendation}"
                )
                ticket_key = self.jira.create_ticket({
                    'summary': jira_summary,
                    'root_cause': jira_description,
                    'severity': severity
                })
                if not ticket_key.startswith("ERROR"):
                    jira_ticket_key = ticket_key
                    self.log(f"Jira ticket created: {ticket_key}")
                else:
                    errors.append(f"Jira creation failed: {ticket_key}")
                    self.log(f"Jira creation failed: {ticket_key}")
            except Exception as e:
                errors.append(f"Jira error: {str(e)}")
                self.log(f"Jira error: {e}")

        notification_status = "complete" if (slack_sent or jira_ticket_key) else "failed"
        if errors:
            notification_status = "partial" if (slack_sent or jira_ticket_key) else "failed"

        return AgentMessage(
            type=MessageType.COMMS_RESULT,
            sender=self.name,
            recipient="orchestrator",
            incident_id=message.incident_id,
            payload={
                'slack_sent': slack_sent,
                'jira_ticket_key': jira_ticket_key,
                'notification_status': notification_status,
                'errors': errors
            },
            parent_message_id=message.id
        )
