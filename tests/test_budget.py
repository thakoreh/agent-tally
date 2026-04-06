"""Tests for budget tracking and kill switch."""

import pytest
from pathlib import Path
import tempfile
import os

from agent_tally.budget import BudgetManager, BudgetConfig, BudgetStatus


class TestBudgetConfig:
    """Tests for BudgetConfig dataclass."""
    
    def test_default_config(self):
        """Test default config has no limits."""
        config = BudgetConfig()
        assert config.daily_limit is None
        assert config.session_limit is None
        assert config.warn_at_80 is True
        assert config.warn_at_95 is True
        assert config.kill_at_100 is True
        assert config.webhook_url is None
    
    def test_config_with_limits(self):
        """Test config with custom limits."""
        config = BudgetConfig(
            daily_limit=10.0,
            session_limit=2.0,
            warn_at_80=True,
            kill_at_100=False,
        )
        assert config.daily_limit == 10.0
        assert config.session_limit == 2.0
        assert config.kill_at_100 is False


class TestBudgetManager:
    """Tests for BudgetManager."""
    
    def test_load_empty_config(self, tmp_path):
        """Test loading when no config file exists."""
        config_path = tmp_path / "budget.yaml"
        manager = BudgetManager(config_path=config_path)
        
        assert manager.config.daily_limit is None
        assert manager.config.session_limit is None
    
    def test_set_limits(self, tmp_path):
        """Test setting budget limits."""
        config_path = tmp_path / "budget.yaml"
        manager = BudgetManager(config_path=config_path)
        
        manager.set_limits(daily=5.0, session=1.0)
        
        assert manager.config.daily_limit == 5.0
        assert manager.config.session_limit == 1.0
        
        # Verify persistence
        manager2 = BudgetManager(config_path=config_path)
        assert manager2.config.daily_limit == 5.0
        assert manager2.config.session_limit == 1.0
    
    def test_check_no_limits(self, tmp_path):
        """Test budget check when no limits set."""
        config_path = tmp_path / "budget.yaml"
        manager = BudgetManager(config_path=config_path)
        
        status = manager.check("session-1", current_cost=1.0, daily_total=5.0)
        
        assert status.session_cost == 1.0
        assert status.daily_cost == 5.0
        assert status.session_pct == 0.0
        assert status.daily_pct == 0.0
        assert not status.session_exceeded
        assert not status.daily_exceeded
    
    def test_check_within_limits(self, tmp_path):
        """Test budget check when within limits."""
        config_path = tmp_path / "budget.yaml"
        manager = BudgetManager(config_path=config_path)
        manager.set_limits(daily=10.0, session=2.0)
        
        status = manager.check("session-1", current_cost=1.0, daily_total=5.0)
        
        assert status.session_pct == 50.0  # 1/2 = 50%
        assert status.daily_pct == 50.0  # 5/10 = 50%
        assert not status.session_exceeded
        assert not status.daily_exceeded
        assert status.session_warning is None
        assert status.daily_warning is None
    
    def test_check_warning_80(self, tmp_path):
        """Test warning at 80% threshold."""
        config_path = tmp_path / "budget.yaml"
        manager = BudgetManager(config_path=config_path)
        manager.set_limits(daily=10.0, session=1.0)
        
        status = manager.check("session-1", current_cost=0.8, daily_total=8.0)
        
        assert status.session_pct == 80.0
        assert status.daily_pct == 80.0
        assert status.session_warning == "80"
        assert status.daily_warning == "80"
    
    def test_check_warning_95(self, tmp_path):
        """Test warning at 95% threshold."""
        config_path = tmp_path / "budget.yaml"
        manager = BudgetManager(config_path=config_path)
        manager.set_limits(daily=10.0, session=1.0)
        
        status = manager.check("session-1", current_cost=0.95, daily_total=9.5)
        
        assert status.session_pct == 95.0
        assert status.daily_pct == 95.0
        assert status.session_warning == "95"
        assert status.daily_warning == "95"
    
    def test_check_exceeded(self, tmp_path):
        """Test budget exceeded at 100%."""
        config_path = tmp_path / "budget.yaml"
        manager = BudgetManager(config_path=config_path)
        manager.set_limits(daily=10.0, session=1.0)
        
        status = manager.check("session-1", current_cost=1.0, daily_total=10.0)
        
        assert status.session_exceeded
        assert status.daily_exceeded
        assert manager.should_kill(status)
    
    def test_should_kill(self, tmp_path):
        """Test should_kill returns True when exceeded."""
        config_path = tmp_path / "budget.yaml"
        manager = BudgetManager(config_path=config_path)
        manager.set_limits(session=1.0)
        
        status = manager.check("session-1", current_cost=1.5, daily_total=0)
        
        assert manager.should_kill(status)
    
    def test_get_warning_level(self, tmp_path):
        """Test warning level classification."""
        config_path = tmp_path / "budget.yaml"
        manager = BudgetManager(config_path=config_path)
        manager.set_limits(daily=10.0, session=1.0)
        
        # None
        status = manager.check("s1", 0.5, 5.0)
        assert manager.get_warning_level(status) == "none"
        
        # Yellow (80%)
        status = manager.check("s2", 0.8, 8.0)
        assert manager.get_warning_level(status) == "yellow"
        
        # Red (95%)
        status = manager.check("s3", 0.95, 9.5)
        assert manager.get_warning_level(status) == "red"
        
        # Kill (100%)
        status = manager.check("s4", 1.0, 10.0)
        assert manager.get_warning_level(status) == "kill"
    
    def test_get_status_text(self, tmp_path):
        """Test status text generation."""
        config_path = tmp_path / "budget.yaml"
        manager = BudgetManager(config_path=config_path)
        manager.set_limits(daily=10.0, session=1.0)
        
        status = manager.check("s1", 0.5, 5.0)
        text = manager.get_status_text(status)
        
        assert "Session:" in text
        assert "Daily:" in text
        assert "50.0%" in text


class TestBudgetStatus:
    """Tests for BudgetStatus dataclass."""
    
    def test_default_status(self):
        """Test default status."""
        status = BudgetStatus()
        assert status.session_cost == 0.0
        assert status.daily_cost == 0.0
        assert not status.session_exceeded
        assert not status.daily_exceeded
    
    def test_status_with_values(self):
        """Test status with custom values."""
        status = BudgetStatus(
            session_cost=1.5,
            daily_cost=5.0,
            session_limit=2.0,
            daily_limit=10.0,
            session_pct=75.0,
            daily_pct=50.0,
        )
        assert status.session_cost == 1.5
        assert status.session_pct == 75.0
