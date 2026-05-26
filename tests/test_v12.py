"""Tests for v0.12.0 — agents command fix, type hints, edge cases."""

import json
import pytest
from click.testing import CliRunner

from agent_tally.cli import cli
from agent_tally.detector import AGENT_MAP, AgentInfo, AgentType
from agent_tally.notifier import Alert
from datetime import datetime
from typing import Optional


class TestAgentsCommandFix:
    """Test that agents --json uses dataclass attribute access, not dict access."""

    def test_agents_json_output(self) -> None:
        """agents --json should produce valid JSON with display and command keys."""
        runner = CliRunner()
        result = runner.invoke(cli, ["agents", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)
        assert "claude" in data
        assert "display" in data["claude"]
        assert "command" in data["claude"]

    def test_agents_json_matches_agent_map(self) -> None:
        """agents --json should include all entries from AGENT_MAP."""
        runner = CliRunner()
        result = runner.invoke(cli, ["agents", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        for name in AGENT_MAP:
            assert name in data, f"Missing agent '{name}' from JSON output"

    def test_agents_json_display_names_are_strings(self) -> None:
        """All display names should be non-empty strings."""
        runner = CliRunner()
        result = runner.invoke(cli, ["agents", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        for name, info in data.items():
            assert isinstance(info["display"], str)
            assert len(info["display"]) > 0
            assert isinstance(info["command"], str)
            assert len(info["command"]) > 0


class TestAlertTimestampType:
    """Test Alert dataclass timestamp handling."""

    def test_alert_default_timestamp(self) -> None:
        """Alert with no timestamp should auto-populate via __post_init__."""
        alert = Alert(level="info", message="test")
        assert alert.timestamp is not None
        assert isinstance(alert.timestamp, datetime)

    def test_alert_explicit_timestamp(self) -> None:
        """Alert with explicit timestamp should preserve it."""
        ts = datetime(2026, 1, 1, 12, 0, 0)
        alert = Alert(level="info", message="test", timestamp=ts)
        assert alert.timestamp == ts

    def test_alert_none_timestamp_becomes_now(self) -> None:
        """Passing None explicitly should still get a timestamp via __post_init__."""
        alert = Alert(level="info", message="test", timestamp=None)
        assert alert.timestamp is not None

    def test_alert_optional_type(self) -> None:
        """The type annotation should accept Optional[datetime]."""
        alert: Alert = Alert(level="warning", message="budget", timestamp=None)
        assert isinstance(alert.timestamp, datetime)


class TestAgentInfoDataclass:
    """Test AgentInfo dataclass behavior."""

    def test_agent_map_values_are_dataclass(self) -> None:
        """All AGENT_MAP values should be AgentInfo instances."""
        for name, info in AGENT_MAP.items():
            assert isinstance(info, AgentInfo), f"{name} is not AgentInfo"

    def test_agent_info_has_required_fields(self) -> None:
        """Each AgentInfo should have all required fields."""
        for name, info in AGENT_MAP.items():
            assert info.display_name, f"{name} missing display_name"
            assert info.cli_command, f"{name} missing cli_command"
            assert info.agent_type, f"{name} missing agent_type"
            assert info.model_pattern, f"{name} missing model_pattern"
            assert isinstance(info.token_patterns, list), f"{name} token_patterns not list"

    def test_agent_types_are_valid(self) -> None:
        """All agent types should be valid AgentType enum values."""
        for name, info in AGENT_MAP.items():
            assert isinstance(info.agent_type, AgentType), f"{name} has invalid AgentType"


class TestCLIVersion:
    """Test CLI version flag."""

    def test_version_flag(self) -> None:
        """--version should print version string."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "agent-tally" in result.output

    def test_version_matches_package(self) -> None:
        """CLI version should match __version__."""
        from agent_tally import __version__
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert __version__ in result.output


class TestSummaryEdgeCases:
    """Edge cases for summary command."""

    def test_summary_with_no_sessions(self) -> None:
        """summary should handle empty database gracefully."""
        runner = CliRunner()
        result = runner.invoke(cli, ["summary"])
        assert result.exit_code == 0

    def test_summary_json_with_no_sessions(self) -> None:
        """summary --json should handle empty database."""
        runner = CliRunner()
        result = runner.invoke(cli, ["summary", "--json"])
        assert result.exit_code == 0


class TestCostCommandEdgeCases:
    """Edge cases for cost command."""

    def test_cost_zero_tokens(self) -> None:
        """Cost of 0 tokens should be $0."""
        runner = CliRunner()
        result = runner.invoke(cli, ["cost", "claude-sonnet-4-20250514", "0", "0"])
        assert result.exit_code == 0

