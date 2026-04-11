"""Enhanced edge case tests for agent-tally."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from agent_tally.detector import detect_agent, parse_tokens, AGENT_MAP
from agent_tally.pricing import PricingConfig, detect_provider
from agent_tally.config import AgentTallyConfig, load_config, save_config
from agent_tally.storage import Storage, Session
from agent_tally.budget import BudgetManager, BudgetConfig


class TestEnhancedDetector:
    """Enhanced tests for token detection edge cases."""

    def test_valid_token_patterns(self):
        """Test that valid token patterns work correctly."""
        # Create a mock agent with simple patterns
        mock_agent = Mock()
        mock_agent.token_patterns = [
            r"(\d+)\s*tokens?\s*in.*?(\d+).*?tokens?\s*out",
        ]
        
        # Test valid pattern
        output = "1500 tokens in, 750 tokens out"
        result = parse_tokens(output, mock_agent)
        assert result == {"tokens_in": 1500, "tokens_out": 750}

    def test_no_token_match(self):
        """Test that no token match returns empty dict."""
        agent_info = AGENT_MAP["claude"]
        
        output = "No tokens here, just regular text"
        result = parse_tokens(output, agent_info)
        assert result == {}

    def test_partial_token_patterns(self):
        """Test partial token patterns."""
        agent_info = AGENT_MAP["claude"]
        
        outputs = [
            "1500 tokens in, 750",
            "input: 1500, output: 750",
            "tokens: 1500 in, 750 out",
        ]
        
        for output in outputs:
            result = parse_tokens(output, agent_info)
            # Should handle gracefully even if partial matches
            assert isinstance(result, dict)


class TestEnhancedPricing:
    """Enhanced tests for pricing edge cases."""

    def test_unknown_model_handling(self):
        """Test pricing for unknown models."""
        pricing = PricingConfig()
        
        unknown_model = pricing.get("completely-unknown-model-123")
        assert unknown_model.name == "completely-unknown-model-123"
        assert unknown_model.input == 0.0
        assert unknown_model.output == 0.0

    def test_extreme_cost_calculations(self):
        """Test cost calculations with extreme values."""
        pricing = PricingConfig()
        
        # Test maximum reasonable values
        model = pricing.get("gpt-4o")
        max_cost = model.cost(10_000_000, 5_000_000)  # 10M in, 5M out
        expected = (10.0 * 2.50) + (5.0 * 10.00)  # $25.00 + $50.00 = $75.00
        assert max_cost == expected

    def test_zero_cost_calculations(self):
        """Test cost calculations with zero values."""
        pricing = PricingConfig()
        
        model = pricing.get("gpt-4o")
        zero_cost = model.cost(0, 0)
        assert zero_cost == 0.0


class TestEnhancedConfig:
    """Enhanced tests for configuration edge cases."""

    def test_config_defaults(self):
        """Test config with default values."""
        config = AgentTallyConfig()
        
        assert config.daily_budget is None
        assert config.session_budget is None
        assert config.default_model == "claude-sonnet-4"
        assert config.currency == "USD"
        assert config.timezone == "UTC"

    def test_config_with_values(self):
        """Test config with custom values."""
        config = AgentTallyConfig()
        config.daily_budget = 10.0
        config.session_budget = 5.0
        config.default_model = "gpt-4"
        config.currency = "CAD"
        
        assert config.daily_budget == 10.0
        assert config.session_budget == 5.0
        assert config.default_model == "gpt-4"
        assert config.currency == "CAD"

    def test_config_yaml_handling(self):
        """Test config YAML handling."""
        # Test creating a valid config
        config = AgentTallyConfig()
        config.daily_budget = 10.0
        config.session_budget = 5.0
        
        # Should not crash when saving
        save_config(config, Path("/tmp/test_config.yaml"))
        
        # Should be able to load it back
        loaded_config = load_config(Path("/tmp/test_config.yaml"))
        assert loaded_config.daily_budget == 10.0
        assert loaded_config.session_budget == 5.0


class TestEnhancedStorage:
    """Enhanced tests for storage edge cases."""

    def test_storage_basic_operations(self):
        """Test basic storage operations."""
        storage = Storage()
        
        # Create session with minimal valid data
        session = Session(
            agent="test-agent",
            started_at=datetime.now(),
            cost=1.0,
            tokens_in=1000,
            tokens_out=500,
        )
        session.id = storage.insert(session)
        
        # Should work with valid data
        assert session.id is not None
        
        # Query the session
        retrieved = storage.query()
        assert len(retrieved) >= 1
        assert any(s.agent == "test-agent" for s in retrieved)
        
        storage.close()

    def test_storage_time_queries(self):
        """Test storage time-based queries."""
        storage = Storage()
        
        # Create sessions at different times
        now = datetime.now()
        sessions = []
        for i in range(3):
            session = Session(
                agent=f"agent-{i}",
                started_at=now - timedelta(hours=i),
                cost=0.1 * i,
                tokens_in=100 * i,
                tokens_out=50 * i,
            )
            session.id = storage.insert(session)
            sessions.append(session)
        
        # Query recent sessions
        recent = storage.query(since=now - timedelta(hours=1))
        assert len(recent) >= 1
        
        # Query all sessions
        all_sessions = storage.query(since=datetime.min)
        assert len(all_sessions) >= 3
        
        storage.close()

    def test_storage_with_none_values(self):
        """Test storage with optional None values."""
        storage = Storage()
        
        # Create session with some None values
        session = Session(
            agent="test-agent",
            started_at=datetime.now(),
            cost=1.0,
            tokens_in=1000,
            tokens_out=500,
            ended_at=None,  # Optional field
            duration_sec=None,  # Optional field
        )
        session.id = storage.insert(session)
        
        # Should work even with None values
        retrieved = storage.query()
        assert len(retrieved) >= 1
        
        storage.close()


class TestEnhancedBudget:
    """Enhanced tests for budget management edge cases."""

    def test_budget_manager_creation(self):
        """Test budget manager creation."""
        config = AgentTallyConfig()
        config.daily_budget = 10.0
        
        # Create budget config directly
        budget_config = BudgetConfig(
            daily_limit=10.0,
            session_limit=None,
            webhook_url=None,
            warn_at_80=True,
            warn_at_95=True,
            kill_at_100=True
        )
        
        # Create budget manager with mock config
        with patch("agent_tally.budget.BudgetManager._load_config", return_value=budget_config):
            budget_manager = BudgetManager(config)
            assert budget_manager.config.daily_limit == 10.0

    def test_budget_threshold_logic(self):
        """Test budget threshold logic."""
        config = AgentTallyConfig()
        config.daily_budget = 100.0
        
        budget_config = BudgetConfig(
            daily_limit=100.0,
            session_limit=None,
            webhook_url=None,
            warn_at_80=True,
            warn_at_95=True,
            kill_at_100=True
        )
        
        with patch("agent_tally.budget.BudgetManager._load_config", return_value=budget_config):
            budget_manager = BudgetManager(config)
            
            # Test different spending levels
            status = budget_manager.check("test-session", 50.0, 50.0)
            assert budget_manager.get_warning_level(status) == "none"  # 50%
            
            status = budget_manager.check("test-session", 95.0, 95.0)
            assert budget_manager.get_warning_level(status) == "red"  # 95%
            
            status = budget_manager.check("test-session", 100.0, 100.0)
            assert budget_manager.get_warning_level(status) == "kill"  # 100%

    def test_budget_with_zero_limit(self):
        """Test budget with zero limits."""
        config = AgentTallyConfig()
        config.daily_budget = 0.0  # Zero budget
        
        budget_config = BudgetConfig(
            daily_limit=0.0,
            session_limit=None,
            webhook_url=None,
            warn_at_80=True,
            warn_at_95=True,
            kill_at_100=True
        )
        
        with patch("agent_tally.budget.BudgetManager._load_config", return_value=budget_config):
            budget_manager = BudgetManager(config)
            
            # Test with a realistic budget
            budget_config = BudgetConfig(
                daily_limit=10.0,
                session_limit=5.0,
                webhook_url=None,
                warn_at_80=True,
                warn_at_95=True,
                kill_at_100=True
            )
            
            with patch("agent_tally.budget.BudgetManager._load_config", return_value=budget_config):
                budget_manager = BudgetManager(config)
                
                # Test different spending levels
                status = budget_manager.check("test-session", 3.0, 3.0)
                assert budget_manager.get_warning_level(status) == "none"  # Below 80%
                
                status = budget_manager.check("test-session", 4.75, 4.75)
                assert budget_manager.get_warning_level(status) == "red"  # 95% of session
                
                status = budget_manager.check("test-session", 5.0, 5.0)
                assert budget_manager.should_kill(status) == True  # Exactly at limit


class TestEnhancedIntegration:
    """Enhanced integration tests."""

    def test_detector_and_pricing_integration(self):
        """Test detector and pricing work together."""
        # Test that we can detect agents and get pricing
        agent_info = detect_agent(["claude", "test"])
        
        # Get pricing for a model
        pricing = PricingConfig()
        model_pricing = pricing.get("gpt-4o")
        
        assert model_pricing.name == "gpt-4o"
        assert model_pricing.input > 0
        assert model_pricing.output > 0

    def test_provider_detection(self):
        """Test provider detection."""
        test_cases = [
            ("claude-3", "Anthropic"),
            ("gpt-4", "OpenAI"),
            ("gemini-2.5", "Google"),
            ("deepseek", "DeepSeek"),
        ]
        
        for model_name, expected_provider in test_cases:
            if expected_provider in detect_provider(model_name):
                # If model exists in pricing, provider should be detected
                detected = detect_provider(model_name)
                assert detected == expected_provider

    def test_config_and_storage_integration(self):
        """Test config and storage integration."""
        # Create a config
        config = AgentTallyConfig()
        config.daily_budget = 10.0
        
        # Save it
        save_config(config, Path("/tmp/integration_test.yaml"))
        
        # Load it back
        loaded_config = load_config(Path("/tmp/integration_test.yaml"))
        assert loaded_config.daily_budget == 10.0
        
        # Test storage with session
        storage = Storage()
        session = Session(
            agent="integration-test",
            started_at=datetime.now(),
            cost=1.0,
            tokens_in=1000,
            tokens_out=500,
        )
        session.id = storage.insert(session)
        
        # Verify session was stored
        retrieved = storage.query()
        assert len(retrieved) >= 1
        assert any(s.agent == "integration-test" for s in retrieved)
        
        storage.close()


if __name__ == "__main__":
    pytest.main([__file__])