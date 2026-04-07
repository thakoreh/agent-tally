"""Tests for configuration file support."""

import pytest
from pathlib import Path

from agent_tally.config import (
    AgentTallyConfig,
    load_config,
    save_config,
    generate_default_config,
    DEFAULT_CONFIG_PATH,
)


class TestAgentTallyConfig:
    """Tests for AgentTallyConfig dataclass."""

    def test_default_config(self):
        config = AgentTallyConfig()
        assert config.daily_budget is None
        assert config.session_budget is None
        assert config.default_model == "claude-sonnet-4"
        assert config.currency == "USD"
        assert config.timezone == "UTC"
        assert config.warn_at_80 is True
        assert config.warn_at_95 is True
        assert config.kill_at_100 is True
        assert config.webhook_url is None
        assert config.model_pricing == {}
        assert config.ignored_agents == []

    def test_custom_config(self):
        config = AgentTallyConfig(
            daily_budget=10.0,
            session_budget=2.0,
            default_model="gpt-5.4",
            currency="EUR",
            timezone="US/Eastern",
            webhook_url="https://discord.com/api/webhooks/test",
            warn_at_80=False,
            kill_at_100=False,
            model_pricing={"custom-model": {"input": 1.0, "output": 5.0}},
            ignored_agents=["some-tool"],
        )
        assert config.daily_budget == 10.0
        assert config.session_budget == 2.0
        assert config.default_model == "gpt-5.4"
        assert config.currency == "EUR"
        assert config.warn_at_80 is False
        assert config.kill_at_100 is False
        assert "custom-model" in config.model_pricing


class TestLoadConfig:
    """Tests for loading configuration."""

    def test_load_missing_file(self, tmp_path):
        config = load_config(tmp_path / "nonexistent.yaml")
        assert config.daily_budget is None
        assert config.default_model == "claude-sonnet-4"

    def test_load_valid_file(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "daily_budget: 5.0\n"
            "session_budget: 1.0\n"
            "default_model: gpt-5.4\n"
            "currency: EUR\n"
            "warn_at_80: false\n"
        )
        config = load_config(config_path)
        assert config.daily_budget == 5.0
        assert config.session_budget == 1.0
        assert config.default_model == "gpt-5.4"
        assert config.currency == "EUR"
        assert config.warn_at_80 is False

    def test_load_empty_file(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text("")
        config = load_config(config_path)
        assert config.daily_budget is None
        assert config.default_model == "claude-sonnet-4"

    def test_load_invalid_yaml(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text("{{invalid: yaml: [}")
        config = load_config(config_path)
        # Should fall back to defaults
        assert config.daily_budget is None

    def test_load_with_model_pricing(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "model_pricing:\n"
            "  my-model:\n"
            "    input: 2.0\n"
            "    output: 8.0\n"
        )
        config = load_config(config_path)
        assert "my-model" in config.model_pricing
        assert config.model_pricing["my-model"]["input"] == 2.0

    def test_load_with_ignored_agents(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "ignored_agents:\n"
            "  - tool-a\n"
            "  - tool-b\n"
        )
        config = load_config(config_path)
        assert "tool-a" in config.ignored_agents
        assert "tool-b" in config.ignored_agents


class TestSaveConfig:
    """Tests for saving configuration."""

    def test_save_and_reload(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config = AgentTallyConfig(
            daily_budget=10.0,
            session_budget=2.0,
            default_model="gpt-5.4",
        )
        save_config(config, config_path)

        loaded = load_config(config_path)
        assert loaded.daily_budget == 10.0
        assert loaded.session_budget == 2.0
        assert loaded.default_model == "gpt-5.4"

    def test_save_creates_directory(self, tmp_path):
        config_path = tmp_path / "nested" / "dir" / "config.yaml"
        config = AgentTallyConfig()
        save_config(config, config_path)
        assert config_path.exists()

    def test_save_with_webhook(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config = AgentTallyConfig(
            webhook_url="https://discord.com/api/webhooks/test",
        )
        save_config(config, config_path)

        content = config_path.read_text()
        assert "webhook_url" in content

    def test_save_without_optional_fields(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        config = AgentTallyConfig()  # No optional fields
        save_config(config, config_path)

        content = config_path.read_text()
        assert "webhook_url" not in content
        assert "model_pricing" not in content
        assert "ignored_agents" not in content


class TestGenerateDefaultConfig:
    """Tests for config generation."""

    def test_generates_string(self):
        content = generate_default_config()
        assert isinstance(content, str)
        assert "agent-tally" in content
        assert "daily_budget" in content
        assert "session_budget" in content

    def test_generated_is_commented(self):
        content = generate_default_config()
        # All actual settings should be commented out
        lines = [l for l in content.split("\n") if l.strip() and not l.startswith("#")]
        # Should only be empty lines
        assert all(l.strip() == "" for l in lines)
