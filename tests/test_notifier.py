"""Tests for alert system."""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from agent_tally.notifier import Notifier, Alert
from agent_tally.budget import BudgetStatus


class TestAlert:
    """Tests for Alert dataclass."""
    
    def test_alert_defaults(self):
        """Test alert default values."""
        alert = Alert(
            level="warning",
            message="Test alert",
        )
        
        assert alert.level == "warning"
        assert alert.message == "Test alert"
        assert alert.session_id is None
        assert alert.cost == 0.0
        assert alert.timestamp is not None
    
    def test_alert_with_all_fields(self):
        """Test alert with all fields."""
        alert = Alert(
            level="critical",
            message="Budget exceeded",
            session_id="session-123",
            cost=5.0,
            budget_type="daily",
            threshold="100",
        )
        
        assert alert.level == "critical"
        assert alert.session_id == "session-123"
        assert alert.cost == 5.0
        assert alert.budget_type == "daily"
        assert alert.threshold == "100"


class TestNotifier:
    """Tests for Notifier."""
    
    def test_notifier_init(self):
        """Test notifier initialization."""
        notifier = Notifier()
        assert notifier.webhook_url is None
        assert notifier.log_file is None
    
    def test_notifier_with_log_file(self, tmp_path):
        """Test notifier with log file."""
        log_file = tmp_path / "alerts.log"
        notifier = Notifier(log_file=log_file)
        
        alert = Alert(level="warning", message="Test alert")
        notifier.send(alert)
        
        assert log_file.exists()
        content = log_file.read_text()
        assert "WARNING" in content
        assert "Test alert" in content
    
    def test_notifier_deduplication(self, tmp_path):
        """Test that duplicate alerts are deduplicated."""
        log_file = tmp_path / "alerts.log"
        notifier = Notifier(log_file=log_file)
        
        alert = Alert(
            level="warning",
            message="Test alert",
            session_id="session-1",
            budget_type="session",
            threshold="80",
        )
        
        # Send same alert twice
        result1 = notifier.send(alert)
        result2 = notifier.send(alert)
        
        assert result1 is True
        assert result2 is False  # Duplicated
        
        # Log should only have one entry
        content = log_file.read_text()
        assert content.count("Test alert") == 1
    
    def test_alert_from_status_no_alerts(self):
        """Test creating alerts from status when no alerts needed."""
        notifier = Notifier()
        
        status = BudgetStatus(
            session_cost=0.5,
            daily_cost=2.0,
            session_limit=1.0,
            daily_limit=10.0,
            session_pct=50.0,
            daily_pct=20.0,
        )
        
        alerts = notifier.alert_from_status(status, "session-1")
        assert len(alerts) == 0
    
    def test_alert_from_status_warning_80(self):
        """Test creating alerts at 80% threshold."""
        notifier = Notifier()
        
        status = BudgetStatus(
            session_cost=0.8,
            session_limit=1.0,
            session_pct=80.0,
            session_warning="80",
        )
        
        alerts = notifier.alert_from_status(status, "session-1")
        assert len(alerts) == 1
        assert alerts[0].level == "warning"
        assert alerts[0].threshold == "80"
    
    def test_alert_from_status_critical(self):
        """Test creating alerts when budget exceeded."""
        notifier = Notifier()
        
        status = BudgetStatus(
            session_cost=1.5,
            session_limit=1.0,
            session_pct=150.0,
            session_exceeded=True,
        )
        
        alerts = notifier.alert_from_status(status, "session-1")
        assert len(alerts) == 1
        assert alerts[0].level == "critical"
        assert alerts[0].threshold == "100"
    
    def test_alert_from_status_both_types(self):
        """Test creating alerts for both session and daily."""
        notifier = Notifier()
        
        status = BudgetStatus(
            session_cost=0.8,
            session_limit=1.0,
            session_pct=80.0,
            session_warning="80",
            daily_cost=8.0,
            daily_limit=10.0,
            daily_pct=80.0,
            daily_warning="80",
        )
        
        alerts = notifier.alert_from_status(status, "session-1")
        assert len(alerts) == 2
        budget_types = {a.budget_type for a in alerts}
        assert "session" in budget_types
        assert "daily" in budget_types
    
    @patch("agent_tally.notifier.Notifier._post_json")
    def test_send_webhook(self, mock_post, tmp_path):
        """Test sending webhook."""
        mock_post.return_value = True
        
        notifier = Notifier(webhook_url="https://example.com/webhook")
        
        alert = Alert(
            level="warning",
            message="Test",
            cost=1.0,
            budget_type="session",
            threshold="80",
        )
        
        result = notifier.send(alert)
        assert result is True
        mock_post.assert_called_once()
    
    def test_post_json_generic(self, tmp_path):
        """Test generic webhook POST."""
        notifier = Notifier()
        
        # This will fail because the URL doesn't exist, but we can test the structure
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response
            
            result = notifier._post_json("https://example.com/webhook", {"test": "data"})
            assert result is True


class TestNotifierDiscord:
    """Tests for Discord webhook formatting."""
    
    def test_discord_payload_format(self):
        """Test Discord payload format."""
        notifier = Notifier(webhook_url="https://discord.com/api/webhooks/123/abc")
        
        alert = Alert(
            level="warning",
            message="Test message",
            cost=1.5,
            budget_type="session",
            threshold="80",
        )
        
        with patch("agent_tally.notifier.Notifier._post_json") as mock_post:
            mock_post.return_value = True
            notifier.send(alert)
            
            # Check the payload structure
            call_args = mock_post.call_args
            payload = call_args[0][1]
            
            assert "embeds" in payload
            assert len(payload["embeds"]) == 1
            embed = payload["embeds"][0]
            assert embed["title"] == "⚠️ agent-tally Alert"
            assert embed["description"] == "Test message"


class TestNotifierSlack:
    """Tests for Slack webhook formatting."""
    
    def test_slack_payload_format(self):
        """Test Slack payload format."""
        notifier = Notifier(webhook_url="https://hooks.slack.com/services/XXX/YYY/ZZZ")
        
        alert = Alert(
            level="critical",
            message="Budget exceeded",
            cost=5.0,
            budget_type="daily",
            threshold="100",
        )
        
        with patch("agent_tally.notifier.Notifier._post_json") as mock_post:
            mock_post.return_value = True
            notifier.send(alert)
            
            # Check the payload structure
            call_args = mock_post.call_args
            payload = call_args[0][1]
            
            assert "attachments" in payload
            assert len(payload["attachments"]) == 1
