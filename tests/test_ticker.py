"""Tests for real-time cost ticker."""

import pytest
from io import StringIO
from unittest.mock import patch, MagicMock
import sys

from agent_tally.ticker import CostTicker, IncrementalCostTracker
from agent_tally.budget import BudgetManager, BudgetStatus


class TestCostTicker:
    """Tests for CostTicker."""
    
    def test_ticker_init(self):
        """Test ticker initialization."""
        ticker = CostTicker(
            session_id="test-session",
            agent_name="Claude Code",
        )
        assert ticker.session_id == "test-session"
        assert ticker.agent_name == "Claude Code"
        assert ticker._cost == 0.0
    
    def test_ticker_update(self):
        """Test ticker update."""
        ticker = CostTicker(
            session_id="test-session",
            agent_name="Claude Code",
        )
        ticker.start()
        
        status = ticker.update(
            cost=1.5,
            tokens_in=1000,
            tokens_out=500,
            model="claude-sonnet-4",
        )
        
        assert ticker._cost == 1.5
        assert ticker._tokens_in == 1000
        assert ticker._tokens_out == 500
        assert ticker._model == "claude-sonnet-4"
        assert isinstance(status, BudgetStatus)
        
        ticker.stop()
    
    def test_ticker_with_budget(self, tmp_path):
        """Test ticker with budget manager."""
        config_path = tmp_path / "budget.yaml"
        manager = BudgetManager(config_path=config_path)
        manager.set_limits(session=2.0)
        
        ticker = CostTicker(
            session_id="test-session",
            agent_name="Claude Code",
            budget_manager=manager,
            get_daily_total=lambda: 0.0,
        )
        ticker.start()
        
        status = ticker.update(cost=1.5, tokens_in=1000, tokens_out=500, model="claude-sonnet-4")
        
        # Should be at 75% (1.5 / 2.0)
        assert status.session_pct == 75.0
        assert not status.session_exceeded
        
        ticker.stop()
    
    def test_ticker_budget_exceeded(self, tmp_path):
        """Test ticker when budget exceeded."""
        config_path = tmp_path / "budget.yaml"
        manager = BudgetManager(config_path=config_path)
        manager.set_limits(session=1.0)
        
        ticker = CostTicker(
            session_id="test-session",
            agent_name="Claude Code",
            budget_manager=manager,
            get_daily_total=lambda: 0.0,
        )
        ticker.start()
        
        status = ticker.update(cost=1.5, tokens_in=1000, tokens_out=500, model="claude-sonnet-4")
        
        assert status.session_exceeded
        assert manager.should_kill(status)
        
        ticker.stop()
    
    def test_get_budget_text(self, tmp_path):
        """Test budget text formatting."""
        config_path = tmp_path / "budget.yaml"
        manager = BudgetManager(config_path=config_path)
        manager.set_limits(session=1.0)
        
        ticker = CostTicker(
            session_id="test-session",
            agent_name="Claude Code",
            budget_manager=manager,
            get_daily_total=lambda: 0.0,
        )
        
        # Under 80%
        status = BudgetStatus(session_pct=50.0, session_limit=1.0)
        text = ticker._get_budget_text(status)
        assert "50%" in text
        
        # At 80%
        status = BudgetStatus(session_pct=80.0, session_limit=1.0, session_warning="80")
        text = ticker._get_budget_text(status)
        assert "80%" in text
        
        # At 95%
        status = BudgetStatus(session_pct=95.0, session_limit=1.0, session_warning="95")
        text = ticker._get_budget_text(status)
        assert "95%" in text


class TestIncrementalCostTracker:
    """Tests for IncrementalCostTracker."""
    
    def test_tracker_init(self):
        """Test tracker initialization."""
        ticker = CostTicker(
            session_id="test-session",
            agent_name="Claude Code",
        )
        tracker = IncrementalCostTracker(ticker=ticker)
        
        assert tracker._accumulated_cost == 0.0
        assert not tracker.killed
    
    def test_tracker_update_tokens(self):
        """Test updating tokens."""
        ticker = CostTicker(
            session_id="test-session",
            agent_name="Claude Code",
        )
        ticker.start()
        
        tracker = IncrementalCostTracker(ticker=ticker)
        tracker.update_tokens(tokens_in=1000, tokens_out=500, model="claude-sonnet-4")
        
        assert tracker._tokens_in == 1000
        assert tracker._tokens_out == 500
        assert tracker._model == "claude-sonnet-4"
        
        ticker.stop()
    
    def test_tracker_set_cost(self):
        """Test setting exact cost."""
        ticker = CostTicker(
            session_id="test-session",
            agent_name="Claude Code",
        )
        ticker.start()
        
        tracker = IncrementalCostTracker(ticker=ticker)
        tracker.set_cost(1.5)
        
        assert tracker._accumulated_cost == 1.5
        
        ticker.stop()
    
    def test_tracker_kill_on_exceeded(self, tmp_path):
        """Test tracker kills when budget exceeded."""
        config_path = tmp_path / "budget.yaml"
        manager = BudgetManager(config_path=config_path)
        manager.set_limits(session=1.0)
        
        ticker = CostTicker(
            session_id="test-session",
            agent_name="Claude Code",
            budget_manager=manager,
            get_daily_total=lambda: 0.0,
        )
        ticker.start()
        
        # Use a fake PID that won't exist
        tracker = IncrementalCostTracker(
            ticker=ticker,
            budget_manager=manager,
            pid=99999,  # Non-existent PID
        )
        
        # Set cost that exceeds budget
        tracker.set_cost(1.5)
        
        assert tracker.killed
        
        ticker.stop()
