"""Alert system for budget thresholds."""

from __future__ import annotations
import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from .budget import BudgetStatus


@dataclass
class Alert:
    """An alert to send."""
    level: str  # "info", "warning", "critical"
    message: str
    session_id: Optional[str] = None
    cost: float = 0.0
    budget_type: str = ""  # "session" or "daily"
    threshold: str = ""  # "80", "95", "100"
    timestamp: datetime = None
    
    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.now()


class Notifier:
    """
    Sends alerts via multiple channels:
    - Terminal notifications (in-band)
    - Webhooks (Discord, Slack, custom)
    - File logging
    """
    
    def __init__(
        self,
        webhook_url: Optional[str] = None,
        log_file: Optional[Path] = None,
    ) -> None:
        self.webhook_url = webhook_url
        self.log_file = log_file
        self._sent_alerts: set = set()  # Dedupe alerts
    
    def send(self, alert: Alert) -> bool:
        """Send an alert through all configured channels."""
        """Send an alert through all configured channels."""
        # Dedupe
        alert_key = f"{alert.session_id}:{alert.budget_type}:{alert.threshold}"
        if alert_key in self._sent_alerts:
            return False
        self._sent_alerts.add(alert_key)
        
        # Log to file
        if self.log_file:
            self._log_to_file(alert)
        
        # Send webhook
        if self.webhook_url:
            self._send_webhook(alert)
        
        return True
    
    def _log_to_file(self, alert: Alert) -> None:
        """Log alert to file."""
        """Log alert to file."""
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, "a") as f:
                ts = alert.timestamp.isoformat()
                f.write(f"[{ts}] [{alert.level.upper()}] {alert.message}\n")
        except Exception:
            pass  # Don't fail on logging errors
    
    def _send_webhook(self, alert: Alert) -> bool:
        """Send alert to webhook URL."""
        """Send alert to webhook URL."""
        if not self.webhook_url:
            return False
        
        # Detect webhook type
        if "discord.com/api/webhooks" in self.webhook_url:
            return self._send_discord(alert)
        elif "hooks.slack.com" in self.webhook_url:
            return self._send_slack(alert)
        else:
            return self._send_generic_webhook(alert)
    
    def _send_discord(self, alert: Alert) -> bool:
        """Send to Discord webhook."""
        """Send to Discord webhook."""
        color = {
            "info": 3447003,  # Blue
            "warning": 15844367,  # Yellow
            "critical": 15158332,  # Red
        }.get(alert.level, 3447003)
        
        emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "critical": "💀",
        }.get(alert.level, "📢")
        
        payload = {
            "embeds": [{
                "title": f"{emoji} agent-tally Alert",
                "description": alert.message,
                "color": color,
                "fields": [
                    {"name": "Cost", "value": f"${alert.cost:.4f}", "inline": True},
                    {"name": "Type", "value": alert.budget_type, "inline": True},
                    {"name": "Threshold", "value": f"{alert.threshold}%", "inline": True},
                ],
                "timestamp": alert.timestamp.isoformat(),
            }]
        }
        
        return self._post_json(self.webhook_url, payload)
    
    def _send_slack(self, alert: Alert) -> bool:
        """Send to Slack webhook."""
        """Send to Slack webhook."""
        color = {
            "info": "#36a64f",
            "warning": "#ffcc00",
            "critical": "#ff0000",
        }.get(alert.level, "#36a64f")
        
        emoji = {
            "info": ":information_source:",
            "warning": ":warning:",
            "critical": ":skull:",
        }.get(alert.level, ":loudspeaker:")
        
        payload = {
            "attachments": [{
                "color": color,
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{emoji} *agent-tally Alert*\n{alert.message}",
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Cost:*\n${alert.cost:.4f}"},
                            {"type": "mrkdwn", "text": f"*Type:*\n{alert.budget_type}"},
                            {"type": "mrkdwn", "text": f"*Threshold:*\n{alert.threshold}%"},
                        ]
                    }
                ]
            }]
        }
        
        return self._post_json(self.webhook_url, payload)
    
    def _send_generic_webhook(self, alert: Alert) -> bool:
        """Send to generic webhook."""
        """Send to generic webhook."""
        payload = {
            "level": alert.level,
            "message": alert.message,
            "session_id": alert.session_id,
            "cost": alert.cost,
            "budget_type": alert.budget_type,
            "threshold": alert.threshold,
            "timestamp": alert.timestamp.isoformat(),
        }
        
        return self._post_json(self.webhook_url, payload)
    
    def _post_json(self, url: str, payload: dict) -> bool:
        """POST JSON to URL."""
        """POST JSON to URL."""
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return 200 <= resp.status < 300
        except Exception:
            return False
    
    def alert_from_status(
        self,
        status: BudgetStatus,
        session_id: str,
    ) -> List[Alert]:
        """Create alerts from budget status."""
        """Create alerts from budget status."""
        alerts = []
        
        # Session warnings
        if status.session_warning == "80":
            alerts.append(Alert(
                level="warning",
                message=f"Session cost at 80% of budget: ${status.session_cost:.4f}/${status.session_limit:.2f}",
                session_id=session_id,
                cost=status.session_cost,
                budget_type="session",
                threshold="80",
            ))
        elif status.session_warning == "95":
            alerts.append(Alert(
                level="warning",
                message=f"Session cost at 95% of budget: ${status.session_cost:.4f}/${status.session_limit:.2f}",
                session_id=session_id,
                cost=status.session_cost,
                budget_type="session",
                threshold="95",
            ))
        
        if status.session_exceeded:
            alerts.append(Alert(
                level="critical",
                message=f"Session budget EXCEEDED: ${status.session_cost:.4f}/${status.session_limit:.2f}",
                session_id=session_id,
                cost=status.session_cost,
                budget_type="session",
                threshold="100",
            ))
        
        # Daily warnings
        if status.daily_warning == "80":
            alerts.append(Alert(
                level="warning",
                message=f"Daily cost at 80% of budget: ${status.daily_cost:.4f}/${status.daily_limit:.2f}",
                session_id=session_id,
                cost=status.daily_cost,
                budget_type="daily",
                threshold="80",
            ))
        elif status.daily_warning == "95":
            alerts.append(Alert(
                level="warning",
                message=f"Daily cost at 95% of budget: ${status.daily_cost:.4f}/${status.daily_limit:.2f}",
                session_id=session_id,
                cost=status.daily_cost,
                budget_type="daily",
                threshold="95",
            ))
        
        if status.daily_exceeded:
            alerts.append(Alert(
                level="critical",
                message=f"Daily budget EXCEEDED: ${status.daily_cost:.4f}/${status.daily_limit:.2f}",
                session_id=session_id,
                cost=status.daily_cost,
                budget_type="daily",
                threshold="100",
            ))
        
        # Send all alerts
        for alert in alerts:
            self.send(alert)
        
        return alerts
