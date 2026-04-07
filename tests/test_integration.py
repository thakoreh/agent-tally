"""Integration tests — verify end-to-end flows."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import pytest

from agent_tally.cli import cli
from agent_tally.storage import Storage, Session
from agent_tally.pricing import PricingConfig
from agent_tally.wrapper import AgentWrapper
from agent_tally.budget import BudgetManager, BudgetConfig
from agent_tally.detector import detect_agent, parse_tokens, parse_model

from click.testing import CliRunner


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary database."""
    return tmp_path / "test.sqlite"


@pytest.fixture
def storage(tmp_db):
    """Provide a Storage with temp database."""
    s = Storage(db_path=tmp_db)
    yield s
    s.close()


@pytest.fixture
def sample_sessions(storage):
    """Insert sample sessions for querying."""
    sessions = [
        Session(agent="Claude Code", model="claude-sonnet-4", tokens_in=5000, tokens_out=2000,
                cost=0.045, started_at=datetime(2026, 4, 1, 10, 0), ended_at=datetime(2026, 4, 1, 10, 5),
                duration_sec=300, task_prompt="fix the bug"),
        Session(agent="Codex CLI", model="o3", tokens_in=10000, tokens_out=5000,
                cost=0.075, started_at=datetime(2026, 4, 2, 14, 0), ended_at=datetime(2026, 4, 2, 14, 10),
                duration_sec=600, task_prompt="add tests"),
        Session(agent="Claude Code", model="claude-opus-4", tokens_in=20000, tokens_out=8000,
                cost=0.9, started_at=datetime(2026, 4, 3, 9, 0), ended_at=datetime(2026, 4, 3, 9, 20),
                duration_sec=1200, task_prompt="refactor module"),
        Session(agent="Gemini CLI", model="gemini-2.5-pro", tokens_in=3000, tokens_out=1500,
                cost=0.01875, started_at=datetime(2026, 4, 4, 16, 0), ended_at=datetime(2026, 4, 4, 16, 2),
                duration_sec=120, task_prompt="explain code"),
    ]
    for s in sessions:
        storage.insert(s)
    return sessions


# ── CLI Integration Tests ─────────────────────────────────────────────────

class TestCLIIntegration:
    """Test CLI commands end-to-end."""

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "agent-tally" in result.output
        assert "0.4.0" in result.output

    def test_no_args_shows_welcome(self):
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "agent-tally" in result.output

    def test_agents_command(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["agents"])
        assert result.exit_code == 0
        assert "Claude Code" in result.output
        assert "Codex CLI" in result.output
        assert "Gemini CLI" in result.output

    def test_summary_json_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agent_tally.storage.DEFAULT_DB_PATH", tmp_path / "test.sqlite")
        runner = CliRunner()
        result = runner.invoke(cli, ["summary", "--json", "--since", "today"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "summary" in data
        assert "sessions" in data

    def test_history_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agent_tally.storage.DEFAULT_DB_PATH", tmp_path / "test.sqlite")
        runner = CliRunner()
        result = runner.invoke(cli, ["history", "--since", "today"])
        assert result.exit_code == 0
        assert "No sessions found" in result.output

    def test_history_json(self, tmp_path, monkeypatch, sample_sessions):
        monkeypatch.setattr("agent_tally.storage.DEFAULT_DB_PATH",
                            sample_sessions[0] if False else tmp_path / "test.sqlite")
        # This uses the real db — just test that history runs
        runner = CliRunner()
        result = runner.invoke(cli, ["history", "--since", "all", "--json"])
        assert result.exit_code == 0

    def test_config_show(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agent_tally.config.DEFAULT_CONFIG_PATH", tmp_path / "config.yaml")
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0
        assert "Current configuration" in result.output

    def test_config_init(self, tmp_path, monkeypatch):
        config_path = tmp_path / "config.yaml"
        monkeypatch.setattr("agent_tally.config.DEFAULT_CONFIG_PATH", config_path)
        monkeypatch.setattr("agent_tally.cli.DEFAULT_CONFIG_PATH", config_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "init"], input="y\n")
        assert result.exit_code == 0
        assert config_path.exists()

    def test_config_pricing(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "pricing"])
        assert result.exit_code == 0
        assert "claude-sonnet-4" in result.output
        assert "gpt-5.4" in result.output


# ── Storage Integration Tests ─────────────────────────────────────────────

class TestStorageIntegration:
    """Test storage layer end-to-end."""

    def test_insert_and_query(self, storage):
        s = Session(
            agent="Claude Code", model="claude-sonnet-4",
            tokens_in=5000, tokens_out=2000, cost=0.045,
            started_at=datetime.now(), duration_sec=300,
        )
        sid = storage.insert(s)
        assert sid is not None

        retrieved = storage.get(sid)
        assert retrieved is not None
        assert retrieved.agent == "Claude Code"
        assert retrieved.model == "claude-sonnet-4"
        assert retrieved.tokens_in == 5000
        assert retrieved.cost == 0.045

    def test_update_session(self, storage):
        s = Session(agent="Test", started_at=datetime.now())
        sid = storage.insert(s)

        s.id = sid
        s.tokens_in = 10000
        s.tokens_out = 5000
        s.cost = 0.1
        s.model = "gpt-5.4"
        storage.update(s)

        retrieved = storage.get(sid)
        assert retrieved.tokens_in == 10000
        assert retrieved.cost == 0.1
        assert retrieved.model == "gpt-5.4"

    def test_query_with_filters(self, storage, sample_sessions):
        # Query all
        all_sessions = storage.query(limit=100)
        assert len(all_sessions) >= 4

        # Query by agent
        claude_sessions = storage.query(agent="Claude Code", limit=100)
        assert len(claude_sessions) == 2

    def test_summary_by_agent(self, storage, sample_sessions):
        summaries = storage.summary(group_by="agent")
        assert len(summaries) >= 3  # Claude Code, Codex, Gemini
        # Claude Code should have 2 sessions
        claude = next(s for s in summaries if s["grp_key"] == "Claude Code")
        assert claude["session_count"] == 2

    def test_summary_by_model(self, storage, sample_sessions):
        summaries = storage.summary(group_by="model")
        assert len(summaries) >= 4

    def test_query_since_date(self, storage, sample_sessions):
        since = datetime(2026, 4, 3)
        sessions = storage.query(since=since, limit=100)
        assert len(sessions) == 2  # Apr 3 and Apr 4


# ── Pricing Integration Tests ─────────────────────────────────────────────

class TestPricingIntegration:
    """Test pricing calculation end-to-end."""

    def test_exact_model_match(self):
        pricing = PricingConfig()
        cost = pricing.estimate("claude-sonnet-4", 1_000_000, 1_000_000)
        assert cost == 18.00  # 3.00 + 15.00

    def test_fuzzy_match(self):
        pricing = PricingConfig()
        result = pricing.get("claude-sonnet-4-20250514")
        assert result.name == "claude-sonnet-4" or result.input == 3.00

    def test_unknown_model(self):
        pricing = PricingConfig()
        result = pricing.get("totally-unknown-model-xyz")
        assert result.input == 0.0
        assert result.output == 0.0

    def test_all_default_pricing_positive(self):
        """All default models should have positive pricing."""
        pricing = PricingConfig()
        for name, p in pricing.all_models().items():
            assert p.input > 0, f"{name} has zero input price"
            assert p.output > 0, f"{name} has zero output price"


# ── Detection Integration Tests ───────────────────────────────────────────

class TestDetectionIntegration:
    """Test agent detection and token parsing together."""

    def test_detect_claude_and_parse(self):
        info = detect_agent(["claude", "fix the bug"])
        assert info is not None
        assert info.display_name == "Claude Code"

        output = "Tokens: 15234 in, 8321 out"
        tokens = parse_tokens(output, info)
        assert tokens["tokens_in"] == 15234
        assert tokens["tokens_out"] == 8321

    def test_detect_codex_and_parse_json(self):
        info = detect_agent(["codex", "--full-auto"])
        assert info.display_name == "Codex CLI"

        output = '"input_tokens": 5000, "output_tokens": 2000'
        tokens = parse_tokens(output, info)
        assert tokens["tokens_in"] == 5000

    def test_detect_generic_fallback(self):
        info = detect_agent(["some-unknown-agent", "do stuff"])
        assert info.display_name == "some-unknown-agent"

    def test_parse_model_from_output(self):
        info = detect_agent(["claude", "test"])
        output = "Using model: claude-sonnet-4"
        model = parse_model(output, info)
        assert model == "claude-sonnet-4"


# ── Wrapper Integration Tests ─────────────────────────────────────────────

class TestWrapperIntegration:
    """Test the wrapper with real subprocess calls (simple commands)."""

    def test_wrap_echo_command(self, tmp_path, monkeypatch):
        """Wrapping 'echo' should work and capture output."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.wrapper.Storage", lambda **kw: Storage(db_path=db_path))
        monkeypatch.setattr("agent_tally.wrapper.BudgetManager", lambda **kw: BudgetManager(
            config_path=tmp_path / "budget.yaml"
        ))

        wrapper = AgentWrapper(
            args=["echo", "hello world"],
            storage=Storage(db_path=db_path),
            budget_manager=BudgetManager(config_path=tmp_path / "budget.yaml"),
            enable_ticker=False,
        )
        rc = wrapper.run()
        assert rc == 0
        assert wrapper.session.duration_sec > 0
        assert wrapper.session.ended_at is not None

    def test_wrap_nonexistent_command(self, tmp_path):
        """Wrapping a nonexistent command should return 127 with good error."""
        wrapper = AgentWrapper(
            args=["totally-nonexistent-command-xyz-123"],
            storage=Storage(db_path=tmp_path / "test.sqlite"),
            budget_manager=BudgetManager(config_path=tmp_path / "budget.yaml"),
            enable_ticker=False,
        )
        rc = wrapper.run()
        assert rc == 127

    def test_wrap_failing_command(self, tmp_path):
        """Wrapping a command that exits non-zero should return its exit code."""
        wrapper = AgentWrapper(
            args=["false"],
            storage=Storage(db_path=tmp_path / "test.sqlite"),
            budget_manager=BudgetManager(config_path=tmp_path / "budget.yaml"),
            enable_ticker=False,
        )
        rc = wrapper.run()
        assert rc == 1


# ── Budget Integration Tests ──────────────────────────────────────────────

class TestBudgetIntegration:
    """Test budget tracking end-to-end."""

    def test_budget_set_and_show(self, tmp_path, monkeypatch):
        budget_path = tmp_path / "budget.yaml"
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.storage.DEFAULT_DB_PATH", db_path)

        manager = BudgetManager(config_path=budget_path)
        manager.set_limits(daily=10.0, session=2.0)

        # Reload
        manager2 = BudgetManager(config_path=budget_path)
        assert manager2.config.daily_limit == 10.0
        assert manager2.config.session_limit == 2.0

    def test_budget_warning_80(self, tmp_path):
        manager = BudgetManager(config_path=tmp_path / "budget.yaml")
        manager.config.session_limit = 1.0

        status = manager.check("sess-1", 0.85, 0.0)
        assert status.session_warning == "80"
        assert not status.session_exceeded

    def test_budget_exceeded(self, tmp_path):
        manager = BudgetManager(config_path=tmp_path / "budget.yaml")
        manager.config.session_limit = 1.0

        status = manager.check("sess-2", 1.05, 0.0)
        assert status.session_exceeded
        assert manager.should_kill(status)
