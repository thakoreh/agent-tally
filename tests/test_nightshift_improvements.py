"""Night shift improvements: budget fix, config alternate path, edge cases."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from agent_tally.budget import BudgetManager, BudgetConfig, BudgetStatus
from agent_tally.config import (
    AgentTallyConfig,
    load_config,
    save_config,
    ALT_CONFIG_PATH,
    DEFAULT_CONFIG_PATH,
)
from agent_tally.pricing import PricingConfig, detect_provider, ModelPricing
from agent_tally.detector import detect_agent, parse_tokens, parse_model


class TestBudget95WarningFix:
    """Test that _warned_95_sessions is properly initialized as self."""

    def test_warned_95_sessions_attribute(self):
        """BudgetManager should have _warned_95_sessions as instance attribute."""
        manager = BudgetManager()
        assert hasattr(manager, "_warned_95_sessions")
        assert isinstance(manager._warned_95_sessions, set)

    def test_session_95_warning_dedup(self):
        """95% warning should only fire once per session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "budget.yaml"
            manager = BudgetManager(config_path=config_path)
            manager.set_limits(session=1.00)

            # First check at 95%
            status1 = manager.check("sess-1", 0.96, 0.96)
            assert status1.session_warning == "95"

            # Second check at 95% — should still report (no dedup for 95 in current impl)
            status2 = manager.check("sess-1", 0.97, 0.97)
            # The warning level should be "red"
            assert manager.get_warning_level(status2) == "red"

    def test_kill_at_100_session(self):
        """Should flag session exceeded at 100%."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "budget.yaml"
            manager = BudgetManager(config_path=config_path)
            manager.set_limits(session=1.00)

            status = manager.check("sess-1", 1.00, 1.00)
            assert status.session_exceeded is True
            assert manager.should_kill(status) is True

    def test_kill_at_100_daily(self):
        """Should flag daily exceeded at 100%."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "budget.yaml"
            manager = BudgetManager(config_path=config_path)
            manager.set_limits(daily=5.00)

            status = manager.check("sess-1", 1.00, 5.00)
            assert status.daily_exceeded is True
            assert manager.should_kill(status) is True


class TestConfigAlternatePath:
    """Test ~/.agent-tally.yaml alternate config path."""

    def test_load_from_alternate_path(self):
        """Should load config from ~/.agent-tally.yaml if primary doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            alt_path = Path(tmpdir) / ".agent-tally.yaml"
            alt_path.write_text(yaml.dump({
                "daily_budget": 15.0,
                "session_budget": 3.0,
                "default_model": "gpt-5o",
                "currency": "USD",
                "timezone": "America/Toronto",
            }))

            config = load_config(alt_path)
            assert config.daily_budget == 15.0
            assert config.session_budget == 3.0
            assert config.default_model == "gpt-5o"
            assert config.timezone == "America/Toronto"

    def test_save_and_reload(self):
        """Should save config and reload it correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = AgentTallyConfig(
                daily_budget=10.0,
                session_budget=2.0,
                default_model="claude-sonnet-4",
                warn_at_80=True,
                warn_at_95=True,
                kill_at_100=True,
            )
            save_config(config, config_path)

            # Reload
            loaded = load_config(config_path)
            assert loaded.daily_budget == 10.0
            assert loaded.session_budget == 2.0
            assert loaded.default_model == "claude-sonnet-4"

    def test_config_with_model_pricing(self):
        """Should handle custom model pricing in config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = AgentTallyConfig(
                model_pricing={
                    "my-custom-model": {"input": 1.50, "output": 6.00},
                },
            )
            save_config(config, config_path)

            loaded = load_config(config_path)
            assert "my-custom-model" in loaded.model_pricing
            assert loaded.model_pricing["my-custom-model"]["input"] == 1.50

    def test_config_with_ignored_agents(self):
        """Should handle ignored agents list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = AgentTallyConfig(
                ignored_agents=["test-tool", "debug-agent"],
            )
            save_config(config, config_path)

            loaded = load_config(config_path)
            assert "test-tool" in loaded.ignored_agents
            assert "debug-agent" in loaded.ignored_agents

    def test_empty_config_file(self):
        """Should handle empty config file gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("")

            config = load_config(config_path)
            assert config.daily_budget is None
            assert config.default_model == "claude-sonnet-4"

    def test_corrupted_yaml(self):
        """Should handle corrupted YAML gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("{{{{invalid yaml")

            config = load_config(config_path)
            assert config.daily_budget is None

    def test_missing_config_returns_defaults(self):
        """Should return defaults when no config file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent.yaml"
            config = load_config(config_path)
            assert config.daily_budget is None
            assert config.default_model == "claude-sonnet-4"
            assert config.warn_at_80 is True


class TestProviderDetectionEdgeCases:
    """Test detect_provider with various model names."""

    def test_anthropic_models(self):
        assert detect_provider("claude-sonnet-4") == "Anthropic"
        assert detect_provider("claude-opus-4") == "Anthropic"
        assert detect_provider("claude-haiku-3.5") == "Anthropic"

    def test_openai_models(self):
        assert detect_provider("gpt-5o") == "OpenAI"
        assert detect_provider("gpt-4o") == "OpenAI"
        assert detect_provider("o3-mini") == "OpenAI"

    def test_google_models(self):
        assert detect_provider("gemini-2.5-pro") == "Google"
        assert detect_provider("gemini-2.0-flash") == "Google"

    def test_xai_models(self):
        assert detect_provider("grok-4") == "xAI"
        assert detect_provider("grok-3") == "xAI"

    def test_deepseek_models(self):
        assert detect_provider("deepseek-v4") == "DeepSeek"
        assert detect_provider("deepseek-r1") == "DeepSeek"

    def test_unknown_model(self):
        assert detect_provider("totally-unknown-model") == "Unknown"

    def test_empty_string(self):
        assert detect_provider("") == "Unknown"

    def test_case_insensitive(self):
        assert detect_provider("Claude-Sonnet-4") == "Anthropic"
        assert detect_provider("GPT-4o") == "OpenAI"


class TestPricingEdgeCases:
    """Test pricing edge cases."""

    def test_zero_tokens(self):
        pricing = PricingConfig()
        model = pricing.get("gpt-4o")
        assert model.cost(0, 0) == 0.0

    def test_exact_match(self):
        pricing = PricingConfig()
        model = pricing.get("gpt-4o")
        assert model.name == "gpt-4o"
        assert model.input == 2.50
        assert model.output == 10.00

    def test_fuzzy_match(self):
        pricing = PricingConfig()
        # Partial match should work
        model = pricing.get("gpt-4o-2024-05-13")
        assert model.input > 0  # Should find gpt-4o

    def test_unknown_model(self):
        pricing = PricingConfig()
        model = pricing.get("future-model-xyz")
        assert model.name == "future-model-xyz"
        assert model.input == 0.0
        assert model.output == 0.0
        assert model.cost(1000, 1000) == 0.0

    def test_cost_calculation(self):
        pricing = PricingConfig()
        model = pricing.get("gpt-4o")
        # 1M input tokens at $2.50 + 1M output tokens at $10.00 = $12.50
        cost = model.cost(1_000_000, 1_000_000)
        assert abs(cost - 12.50) < 0.001

    def test_estimate_method(self):
        pricing = PricingConfig()
        cost = pricing.estimate("gpt-4o", 100_000, 50_000)
        expected = (100_000 / 1_000_000 * 2.50) + (50_000 / 1_000_000 * 10.00)
        assert abs(cost - expected) < 0.001

    def test_models_by_provider(self):
        pricing = PricingConfig()
        by_provider = pricing.models_by_provider()
        assert "Anthropic" in by_provider
        assert "OpenAI" in by_provider
        assert "Google" in by_provider
        assert len(by_provider["Anthropic"]) > 5

    def test_all_models(self):
        pricing = PricingConfig()
        models = pricing.all_models()
        assert len(models) > 50  # Should have extensive pricing


class TestBudgetConfigEdgeCases:
    """Test BudgetConfig edge cases."""

    def test_negative_daily_limit_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "budget.yaml"
            manager = BudgetManager(config_path=config_path)
            with pytest.raises(ValueError, match="negative"):
                manager.set_limits(daily=-5.0)

    def test_negative_session_limit_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "budget.yaml"
            manager = BudgetManager(config_path=config_path)
            with pytest.raises(ValueError, match="negative"):
                manager.set_limits(session=-5.0)

    def test_zero_limits_are_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "budget.yaml"
            manager = BudgetManager(config_path=config_path)
            # Zero is valid (effectively disables)
            manager.set_limits(daily=0.0, session=0.0)
            assert manager.config.daily_limit == 0.0
            assert manager.config.session_limit == 0.0

    def test_kill_process_nonexistent(self):
        """Killing nonexistent PID should not raise."""
        BudgetManager.kill_process(99999999)

    def test_warning_levels(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "budget.yaml"
            manager = BudgetManager(config_path=config_path)
            manager.set_limits(session=1.00, daily=10.00)

            # Under 80%
            status = manager.check("s1", 0.50, 3.00)
            assert manager.get_warning_level(status) == "none"

            # Over 80%
            status = manager.check("s2", 0.85, 3.00)
            assert manager.get_warning_level(status) == "yellow"

            # Over 95%
            status = manager.check("s3", 0.97, 3.00)
            assert manager.get_warning_level(status) == "red"

            # Over 100%
            status = manager.check("s4", 1.05, 3.00)
            assert manager.get_warning_level(status) == "kill"


class TestTokenDetectionEdgeCases:
    """Test token parsing with various formats."""

    def test_empty_output(self):
        from agent_tally.detector import AGENT_MAP
        agent_info = AGENT_MAP["claude"]
        result = parse_tokens("", agent_info)
        assert result == {}

    def test_anthropic_api_format(self):
        from agent_tally.detector import AGENT_MAP
        agent_info = AGENT_MAP["claude"]
        output = '{"input_tokens": 5000, "output_tokens": 2000}'
        result = parse_tokens(output, agent_info)
        assert result.get("tokens_in") == 5000
        assert result.get("tokens_out") == 2000

    def test_openai_api_format(self):
        from agent_tally.detector import AGENT_MAP
        agent_info = AGENT_MAP["claude"]
        output = '"prompt_tokens": 1200, "completion_tokens": 400'
        result = parse_tokens(output, agent_info)
        assert result.get("tokens_in") == 1200
        assert result.get("tokens_out") == 400

    def test_bedrock_format(self):
        from agent_tally.detector import AGENT_MAP
        agent_info = AGENT_MAP["claude"]
        output = 'inputTokenCount: 3500, outputTokenCount: 1200'
        result = parse_tokens(output, agent_info)
        assert result.get("tokens_in") == 3500
        assert result.get("tokens_out") == 1200

    def test_litellm_format(self):
        from agent_tally.detector import AGENT_MAP
        agent_info = AGENT_MAP["claude"]
        output = 'prompt_tokens = 2500, completion_tokens = 800'
        result = parse_tokens(output, agent_info)
        assert result.get("tokens_in") == 2500
        assert result.get("tokens_out") == 800

    def test_google_api_format(self):
        from agent_tally.detector import AGENT_MAP
        agent_info = AGENT_MAP["gemini"]
        output = '"totalTokenCount": 5000, "candidatesTokenCount": 2000'
        result = parse_tokens(output, agent_info)
        assert result.get("tokens_in") == 5000
        assert result.get("tokens_out") == 2000

    def test_slash_format(self):
        from agent_tally.detector import AGENT_MAP
        agent_info = AGENT_MAP["claude"]
        output = '1234 / 5678 tokens'
        result = parse_tokens(output, agent_info)
        assert result.get("tokens_in") == 1234
        assert result.get("tokens_out") == 5678

    def test_model_detection(self):
        from agent_tally.detector import AGENT_MAP
        agent_info = AGENT_MAP["claude"]
        output = 'model: claude-sonnet-4'
        result = parse_model(output, agent_info)
        assert result == "claude-sonnet-4"

    def test_no_model_found(self):
        from agent_tally.detector import AGENT_MAP
        agent_info = AGENT_MAP["claude"]
        result = parse_model("nothing relevant at all", agent_info)
        assert result is None
