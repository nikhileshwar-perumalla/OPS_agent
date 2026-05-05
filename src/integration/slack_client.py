import json
import requests
from datetime import datetime

class SlackNotifier:
    def __init__(self, webhook_url=None, mock=True):
        self.webhook_url = webhook_url
        self.mock = mock
        self.channel = "#alerts-l1"

    def post_incident(self, incident_data, ticket_id="UNKNOWN"):
        """
        incident_data: { ... }
        ticket_id: str (Used for button callback context)
        """
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 New Incident Reported: {incident_data.get('severity', 'P2')}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Summary:*\n{incident_data.get('summary')}"},
                    {"type": "mrkdwn", "text": f"*Root Cause:*\n{incident_data.get('root_cause')}"}
                ]
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Recommended Action:*\n{incident_data.get('action')}"},
                    {"type": "mrkdwn", "text": f"*Confidence:*\n{incident_data.get('confidence', 0.0):.2f}"}
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Approve Action"},
                        "style": "primary",
                        "action_id": "approve_action",
                        "value": ticket_id
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Escalate"},
                        "style": "danger",
                        "action_id": "escalate_action",
                        "value": ticket_id
                    }
                ]
            }
        ]

        # Use an environment variable or config for the callback URL in real life
        # Automatically updated by Antigravity based on active tunnel
        callback_info = "CALLBACK_URL: https://mindy-hyetographical-roseann.ngrok-free.dev/slack/actions" 

        if self.mock:
            print(f"[Slack Mock] Posting to {self.channel}:")
            print(json.dumps(blocks, indent=2))
            print(f"[{callback_info}]")
            return {
                "ok": True, 
                "mock": True, 
                "payload": blocks,
                "callback": callback_info
            }
        else:
            try:
                response = requests.post(self.webhook_url, json={'blocks': blocks}, timeout=10)
                if response.status_code == 200:
                    return {"ok": True, "mock": False, "payload": blocks}
                else:
                    return {"ok": False, "error": response.text}
            except Exception as e:
                return {"ok": False, "error": str(e)}
