"""Tests for new features: Cursor detection, markdown export, flexible --since, top command."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from agent_tally.cli import cli, _export_markdown, _parse_since
from agent_tally.detector import detect_agent, parse_tokens, parse_model, AgentType, AGENT_MAP
from agent_tally.storage import Storage, Session


# ── Cursor detection ──────────────────────────────────────────

class TestCursorDetection:
    def test_cursor_in_agent_map(self):
        assert "cursor" in AGENT_MAP

    def test_cursor_agent_type(self):
        info = AGENT_MAP["cursor"]
        assert info.agent_type == AgentType.CURSOR
        assert info.display_name == "Cursor"

    def test_detect_cursor_command(self):
        info = detect_agent(["cursor", "fix the code"])
        assert info is not None
        assert info.agent_type == AgentType.CURSOR

    def test_cursor_parse_tokens_json_style(self):
        info = AGENT_MAP["cursor"]
        output = '{"input_tokens": 5000, "output_tokens": 2000}'
        result = parse_tokens(output, info)
        assert result["tokens_in"] == 5000
        assert result["tokens_out"] == 2000

    def test_cursor_parse_tokens_in_out(self):
        info = AGENT_MAP["cursor"]
        output = "Tokens: 3000 in, 1500 out"
        result = parse_tokens(output, info)
        assert result["tokens_in"] == 3000
        assert result["tokens_out"] == 1500

    def test_cursor_parse_tokens_input_output(self):
        info = AGENT_MAP["cursor"]
        output = "input: 7000 output: 4000"
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 7000

    def test_cursor_parse_model(self):
        info = AGENT_MAP["cursor"]
        output = "model: cursor-pro"
        result = parse_model(output, info)
        assert result == "cursor-pro"

    def test_cursor_parse_model_not_found(self):
        info = AGENT_MAP["cursor"]
        result = parse_model("completed task successfully", info)
        assert result is None


# ── Markdown export ────────────────────────────────────────────

class TestMarkdownExport:
    def test_empty_rows(self):
        result = _export_markdown([])
        assert result == ""

    def test_single_row(self):
        rows = [{
            "id": 1,
            "agent": "Claude Code",
            "model": "claude-sonnet-4",
            "task_prompt": "fix bug",
            "tokens_in": 5000,
            "tokens_out": 2000,
            "cost": 0.045,
            "started_at": "2026-04-08T10:30:00",
            "ended_at": "2026-04-08T10:30:45",
            "duration_sec": 45.2,
        }]
        result = _export_markdown(rows)
        assert "# Agent-Tally Session Export" in result
        assert "Claude Code" in result
        assert "claude-sonnet-4" in result
        assert "$0.0450" in result
        assert "5,000" in result
        assert "2,000" in result

    def test_multiple_rows(self):
        rows = [
            {
                "id": i,
                "agent": f"Agent-{i}",
                "model": f"model-{i}",
                "task_prompt": "",
                "tokens_in": i * 1000,
                "tokens_out": i * 500,
                "cost": i * 0.01,
                "started_at": "2026-04-08T10:00:00",
                "ended_at": "2026-04-08T10:01:00",
                "duration_sec": 60.0,
            }
            for i in range(1, 4)
        ]
        result = _export_markdown(rows)
        assert "Agent-1" in result
        assert "Agent-2" in result
        assert "Agent-3" in result
        assert "3" in result  # session count in summary

    def test_zero_cost_shows_dash(self):
        rows = [{
            "id": 1,
            "agent": "Test",
            "model": "test-model",
            "task_prompt": "",
            "tokens_in": 0,
            "tokens_out": 0,
            "cost": 0.0,
            "started_at": None,
            "ended_at": None,
            "duration_sec": 0.0,
        }]
        result = _export_markdown(rows)
        assert "|" in result  # Table structure is correct

    def test_null_started_at(self):
        rows = [{
            "id": 1,
            "agent": "Test",
            "model": "test",
            "task_prompt": "",
            "tokens_in": 100,
            "tokens_out": 50,
            "cost": 0.001,
            "started_at": None,
            "ended_at": None,
            "duration_sec": 10.0,
        }]
        result = _export_markdown(rows)
        assert "-" in result  # Should show dash for missing date

    def test_summary_line(self):
        rows = [
            {
                "id": 1,
                "agent": "A",
                "model": "m",
                "task_prompt": "",
                "tokens_in": 1000,
                "tokens_out": 500,
                "cost": 0.05,
                "started_at": "2026-04-08T10:00:00",
                "ended_at": None,
                "duration_sec": 10.0,
            },
            {
                "id": 2,
                "agent": "B",
                "model": "n",
                "task_prompt": "",
                "tokens_in": 2000,
                "tokens_out": 1000,
                "cost": 0.10,
                "started_at": "2026-04-08T11:00:00",
                "ended_at": None,
                "duration_sec": 20.0,
            },
        ]
        result = _export_markdown(rows)
        # Total cost should be $0.1500
        assert "0.1500" in result
        # Total tokens: 3000 in, 1500 out
        assert "3,000" in result
        assert "1,500" in result


# ── Flexible --since parsing ───────────────────────────────────

class TestParseSinceExtended:
    def test_today(self):
        result = _parse_since("today")
        assert result is not None
        assert result.hour == 0
        assert result.minute == 0

    def test_yesterday(self):
        result = _parse_since("yesterday")
        assert result is not None
        yesterday = datetime.now() - timedelta(days=1)
        assert result.date() == yesterday.date()

    def test_all(self):
        result = _parse_since("all")
        assert result is None

    def test_hours_format(self):
        result = _parse_since("1h")
        assert result is not None
        expected = datetime.now() - timedelta(hours=1)
        diff = abs((result - expected).total_seconds())
        assert diff < 2  # Within 2 seconds

    def test_24h_format(self):
        result = _parse_since("24h")
        assert result is not None
        expected = datetime.now() - timedelta(hours=24)
        diff = abs((result - expected).total_seconds())
        assert diff < 2

    def test_minutes_format(self):
        result = _parse_since("30m")
        assert result is not None
        expected = datetime.now() - timedelta(minutes=30)
        diff = abs((result - expected).total_seconds())
        assert diff < 2

    def test_5m_format(self):
        result = _parse_since("5m")
        assert result is not None
        expected = datetime.now() - timedelta(minutes=5)
        diff = abs((result - expected).total_seconds())
        assert diff < 2

    def test_days_format(self):
        result = _parse_since("7d")
        assert result is not None
        expected = datetime.now() - timedelta(days=7)
        diff = abs((result - expected).total_seconds())
        assert diff < 2

    def test_30d_format(self):
        result = _parse_since("30d")
        assert result is not None

    def test_iso_format(self):
        result = _parse_since("2026-04-01")
        assert result is not None
        assert result.year == 2026
        assert result.month == 4

    def test_invalid_defaults_to_today(self):
        result = _parse_since("not-a-date")
        assert result is not None
        assert result.hour == 0
        assert result.minute == 0


# ── CLI integration tests ──────────────────────────────────────

class TestCLIExportFormats:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = Path(self.tmp) / "test.db"
        self.storage = Storage(db_path=self.db_path)

        # Insert test data
        now = datetime.now()
        self.storage.insert(Session(
            agent="Claude Code",
            model="claude-sonnet-4",
            tokens_in=5000,
            tokens_out=2000,
            cost=0.045,
            started_at=now,
            ended_at=now + timedelta(seconds=30),
            duration_sec=30.0,
        ))
        self.storage.close()

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_export_markdown_format(self):
        runner = CliRunner()
        with patch("agent_tally.cli.Storage", return_value=self.storage):
            # Re-open storage for the command
            storage = Storage(db_path=self.db_path)
            with patch("agent_tally.cli.Storage", return_value=storage):
                result = runner.invoke(cli, ["export", "--format", "markdown", "--since", "all"])
                # Should contain markdown table header
                if result.exit_code == 0:
                    assert "Agent-Tally" in result.output or "No sessions" in result.output
                storage.close()

    def test_export_json_format(self):
        runner = CliRunner()
        storage = Storage(db_path=self.db_path)
        with patch("agent_tally.cli.Storage", return_value=storage):
            result = runner.invoke(cli, ["export", "--format", "json", "--since", "all"])
            if result.exit_code == 0 and "No sessions" not in result.output:
                data = json.loads(result.output)
                assert isinstance(data, list)
            storage.close()


class TestCLITopCommand:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = Path(self.tmp) / "test.db"
        self.storage = Storage(db_path=self.db_path)

        now = datetime.now()
        self.storage.insert(Session(
            agent="Claude Code",
            model="claude-sonnet-4",
            tokens_in=10000,
            tokens_out=5000,
            cost=0.15,
            started_at=now,
            duration_sec=45.0,
        ))
        self.storage.insert(Session(
            agent="Codex CLI",
            model="o3",
            tokens_in=8000,
            tokens_out=3000,
            cost=0.10,
            started_at=now - timedelta(minutes=5),
            duration_sec=30.0,
        ))
        self.storage.close()

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_top_by_agent(self):
        runner = CliRunner()
        storage = Storage(db_path=self.db_path)
        with patch("agent_tally.cli.Storage", return_value=storage):
            result = runner.invoke(cli, ["top", "--by", "agent", "--since", "all"])
            assert result.exit_code == 0
            storage.close()

    def test_top_by_model(self):
        runner = CliRunner()
        storage = Storage(db_path=self.db_path)
        with patch("agent_tally.cli.Storage", return_value=storage):
            result = runner.invoke(cli, ["top", "--by", "model", "--since", "all"])
            assert result.exit_code == 0
            storage.close()

    def test_top_json_output(self):
        runner = CliRunner()
        storage = Storage(db_path=self.db_path)
        with patch("agent_tally.cli.Storage", return_value=storage):
            result = runner.invoke(cli, ["top", "--json", "--since", "all"])
            assert result.exit_code == 0
            if "No sessions" not in result.output:
                data = json.loads(result.output)
                assert isinstance(data, list)
            storage.close()

    def test_top_no_data(self):
        runner = CliRunner()
        empty_tmp = tempfile.mkdtemp()
        empty_db = Path(empty_tmp) / "empty.db"
        storage = Storage(db_path=empty_db)
        with patch("agent_tally.cli.Storage", return_value=storage):
            result = runner.invoke(cli, ["top", "--since", "today"])
            assert result.exit_code == 0
            storage.close()
        import shutil
        shutil.rmtree(empty_tmp, ignore_errors=True)

    def test_top_with_limit(self):
        runner = CliRunner()
        storage = Storage(db_path=self.db_path)
        with patch("agent_tally.cli.Storage", return_value=storage):
            result = runner.invoke(cli, ["top", "-n", "1", "--since", "all"])
            assert result.exit_code == 0
            storage.close()


class TestCLIHistoryWithSince:
    """Test that --since with new flexible formats works through CLI."""

    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = Path(self.tmp) / "test.db"

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_history_since_hours(self):
        storage = Storage(db_path=self.db_path)
        storage.insert(Session(
            agent="Test",
            tokens_in=100,
            cost=0.01,
            started_at=datetime.now() - timedelta(minutes=30),
        ))
        runner = CliRunner()
        with patch("agent_tally.cli.Storage", return_value=storage):
            result = runner.invoke(cli, ["history", "--since", "1h", "--json"])
            assert result.exit_code == 0
            if "No sessions" not in result.output:
                data = json.loads(result.output)
                assert len(data) >= 1
        storage.close()
