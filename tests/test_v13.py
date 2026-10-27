"""Tests for v0.13.0 features: recent command, status command, --by-provider summary."""

from __future__ import annotations

import json
from datetime import datetime
from click.testing import CliRunner

from agent_tally.cli import cli
from agent_tally.storage import Storage, Session


def _insert_sample_sessions(storage: Storage) -> None:
    """Insert sample sessions for testing."""
    sessions = [
        Session(agent="Claude Code", model="claude-sonnet-4", tokens_in=5000, tokens_out=2000,
                cost=0.045, started_at=datetime.now().replace(hour=10, minute=0, second=0, microsecond=0), ended_at=datetime.now().replace(hour=10, minute=5, second=0, microsecond=0),
                duration_sec=300, task_prompt="fix the bug"),
        Session(agent="Codex CLI", model="gpt-5.2-codex", tokens_in=8000, tokens_out=3000,
                cost=0.062, started_at=datetime.now().replace(hour=11, minute=0, second=0, microsecond=0), ended_at=datetime.now().replace(hour=11, minute=3, second=0, microsecond=0),
                duration_sec=180, task_prompt="add tests"),
        Session(agent="OpenClaw", model="glm-5", tokens_in=2000, tokens_out=1000,
                cost=0.001, started_at=datetime.now().replace(hour=12, minute=0, second=0, microsecond=0), ended_at=datetime.now().replace(hour=12, minute=2, second=0, microsecond=0),
                duration_sec=120, task_prompt="explain code"),
        Session(agent="Claude Code", model="gpt-4o", tokens_in=3000, tokens_out=1500,
                cost=0.035, started_at=datetime.now().replace(hour=13, minute=0, second=0, microsecond=0), ended_at=datetime.now().replace(hour=13, minute=1, second=0, microsecond=0),
                duration_sec=60, task_prompt="refactor module"),
    ]
    for s in sessions:
        storage.insert(s)


class TestRecentCommand:
    """Test the 'recent' convenience command."""

    def test_recent_basic(self, tmp_path, monkeypatch):
        """Recent command shows last N sessions."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))
        storage = Storage(db_path=db_path)
        _insert_sample_sessions(storage)
        storage.close()

        runner = CliRunner()
        result = runner.invoke(cli, ["recent", "-n", "3"])
        assert result.exit_code == 0
        assert "3 sessions" in result.output

    def test_recent_json(self, tmp_path, monkeypatch):
        """Recent command with --json outputs valid JSON."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))
        storage = Storage(db_path=db_path)
        _insert_sample_sessions(storage)
        storage.close()

        runner = CliRunner()
        result = runner.invoke(cli, ["recent", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 4  # default is 5 but only 4 exist

    def test_recent_empty(self, tmp_path, monkeypatch):
        """Recent command with no sessions shows message."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))

        runner = CliRunner()
        result = runner.invoke(cli, ["recent"])
        assert result.exit_code == 0
        assert "No sessions found" in result.output


class TestStatusCommand:
    """Test the 'status' command."""

    def test_status_basic(self, tmp_path, monkeypatch):
        """Status command shows today's summary."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))
        storage = Storage(db_path=db_path)
        _insert_sample_sessions(storage)
        storage.close()

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        # Should show today's stats
        assert "4 sessions" in result.output
        assert "Today" in result.output

    def test_status_json(self, tmp_path, monkeypatch):
        """Status command with --json outputs structured data."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))
        storage = Storage(db_path=db_path)
        _insert_sample_sessions(storage)
        storage.close()

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "today" in data
        assert "all_time" in data
        assert data["today"]["sessions"] == 4
        assert data["today"]["cost"] > 0

    def test_status_empty(self, tmp_path, monkeypatch):
        """Status command with no sessions."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "0 sessions" in result.output


class TestProviderSummary:
    """Test --by-provider flag on summary command."""

    def test_by_provider_json(self, tmp_path, monkeypatch):
        """Summary --by-provider --json outputs provider breakdown."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))
        storage = Storage(db_path=db_path)
        _insert_sample_sessions(storage)
        storage.close()

        runner = CliRunner()
        result = runner.invoke(cli, ["summary", "--by-provider", "--json", "--since", "all"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "summary" in data
        assert data["group_by"] == "provider"
        providers = [s["provider"] for s in data["summary"]]
        assert "Anthropic" in providers  # claude-sonnet-4
        assert "OpenAI" in providers  # gpt-5.2-codex, gpt-4o

    def test_by_provider_table(self, tmp_path, monkeypatch):
        """Summary --by-provider shows provider table."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))
        storage = Storage(db_path=db_path)
        _insert_sample_sessions(storage)
        storage.close()

        runner = CliRunner()
        result = runner.invoke(cli, ["summary", "--by-provider", "--since", "all"])
        assert result.exit_code == 0
        assert "Provider" in result.output

    def test_by_provider_empty(self, tmp_path, monkeypatch):
        """Summary --by-provider with no sessions."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))

        runner = CliRunner()
        result = runner.invoke(cli, ["summary", "--by-provider", "--since", "all"])
        assert result.exit_code == 0
        assert "No sessions found" in result.output


class TestStorageSummaryByProvider:
    """Test the storage.summary_by_provider method directly."""

    def test_provider_breakdown(self, tmp_path):
        """Provider breakdown groups models correctly."""
        storage = Storage(db_path=tmp_path / "test.sqlite")
        _insert_sample_sessions(storage)

        result = storage.summary_by_provider()
        assert len(result) > 0

        provider_names = [r["provider"] for r in result]
        assert "Anthropic" in provider_names
        assert "OpenAI" in provider_names

        # Check totals
        anthropic = [r for r in result if r["provider"] == "Anthropic"][0]
        assert anthropic["sessions"] == 1
        assert anthropic["cost"] == pytest.approx(0.045, abs=0.001)

        storage.close()

    def test_provider_with_since_filter(self, tmp_path):
        """Provider breakdown respects since filter."""
        storage = Storage(db_path=tmp_path / "test.sqlite")
        _insert_sample_sessions(storage)

        # Only sessions from 11am onwards
        since = datetime.now().replace(hour=11, minute=0, second=0, microsecond=0)
        result = storage.summary_by_provider(since=since)
        total_sessions = sum(r["sessions"] for r in result)
        assert total_sessions == 3  # 3 sessions at 11, 12, 13

        storage.close()


import pytest
