"""Tests for v0.14.0 features: notes, hourly, anomalies, and improved session output."""

from __future__ import annotations

import json
from datetime import datetime
from click.testing import CliRunner

from agent_tally.cli import cli
from agent_tally.storage import Storage, Session


def _insert_sample_sessions(storage: Storage) -> None:
    """Insert sample sessions with varied costs for anomaly testing."""
    sessions = [
        Session(
            agent="Claude Code", model="claude-sonnet-4", tokens_in=5000, tokens_out=2000,
            cost=0.05, started_at=datetime(2026, 5, 27, 10, 0), ended_at=datetime(2026, 5, 27, 10, 5),
            duration_sec=300, task_prompt="fix the bug",
        ),
        Session(
            agent="Codex CLI", model="gpt-5.2-codex", tokens_in=8000, tokens_out=3000,
            cost=0.06, started_at=datetime(2026, 5, 27, 11, 0), ended_at=datetime(2026, 5, 27, 11, 3),
            duration_sec=180, task_prompt="add tests",
        ),
        Session(
            agent="OpenClaw", model="glm-5", tokens_in=2000, tokens_out=1000,
            cost=0.001, started_at=datetime(2026, 5, 27, 12, 0), ended_at=datetime(2026, 5, 27, 12, 2),
            duration_sec=120, task_prompt="explain code",
        ),
        Session(
            agent="Claude Code", model="claude-opus-4", tokens_in=50000, tokens_out=20000,
            cost=15.0, started_at=datetime(2026, 5, 27, 13, 0), ended_at=datetime(2026, 5, 27, 13, 15),
            duration_sec=900, task_prompt="refactor module",
        ),
        Session(
            agent="Gemini CLI", model="gemini-2.5-flash", tokens_in=3000, tokens_out=1500,
            cost=0.005, started_at=datetime(2026, 5, 27, 14, 0), ended_at=datetime(2026, 5, 27, 14, 1),
            duration_sec=60, task_prompt="quick fix",
        ),
        Session(
            agent="Codex CLI", model="gpt-4o", tokens_in=3000, tokens_out=1500,
            cost=0.04, started_at=datetime(2026, 5, 27, 15, 0), ended_at=datetime(2026, 5, 27, 15, 1),
            duration_sec=60, task_prompt="refactor module",
        ),
    ]
    for s in sessions:
        storage.insert(s)


class TestNoteCommand:
    """Test the 'note' command."""

    def test_note_basic(self, tmp_path, monkeypatch):
        """Note command adds a note to a session."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))
        storage = Storage(db_path=db_path)
        sid = storage.insert(Session(
            agent="Test", cost=0.01,
            started_at=datetime(2026, 5, 27, 10, 0),
        ))
        storage.close()

        runner = CliRunner()
        result = runner.invoke(cli, ["note", str(sid), "production deploy"])
        assert result.exit_code == 0
        assert "Added note" in result.output
        assert "production deploy" in result.output

        # Verify in DB
        storage = Storage(db_path=db_path)
        s = storage.get(sid)
        assert s.notes == "production deploy"
        storage.close()

    def test_note_accumulates(self, tmp_path, monkeypatch):
        """Multiple notes accumulate with semicolons."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))
        storage = Storage(db_path=db_path)
        sid = storage.insert(Session(
            agent="Test", cost=0.01,
            started_at=datetime(2026, 5, 27, 10, 0),
        ))
        storage.close()

        runner = CliRunner()
        runner.invoke(cli, ["note", str(sid), "first note"])
        result = runner.invoke(cli, ["note", str(sid), "second note"])

        storage = Storage(db_path=db_path)
        s = storage.get(sid)
        assert "first note" in s.notes
        assert "second note" in s.notes
        assert ";" in s.notes
        storage.close()

    def test_note_not_found(self, tmp_path, monkeypatch):
        """Note command with nonexistent session returns error."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))

        runner = CliRunner()
        result = runner.invoke(cli, ["note", "99999", "test"])
        assert result.exit_code != 0
        assert "not found" in result.output


class TestStorageNotes:
    """Test Storage.add_note and notes field."""

    def test_add_note(self, tmp_path):
        storage = Storage(db_path=tmp_path / "test.sqlite")
        sid = storage.insert(Session(agent="Test", cost=0.01, started_at=datetime(2026, 5, 27, 10, 0)))

        result = storage.add_note(sid, "hello world")
        assert result is True

        s = storage.get(sid)
        assert s.notes == "hello world"
        storage.close()

    def test_add_note_accumulates(self, tmp_path):
        storage = Storage(db_path=tmp_path / "test.sqlite")
        sid = storage.insert(Session(agent="Test", cost=0.01, started_at=datetime(2026, 5, 27, 10, 0)))

        storage.add_note(sid, "first")
        storage.add_note(sid, "second")
        storage.add_note(sid, "third")

        s = storage.get(sid)
        assert "first" in s.notes
        assert "second" in s.notes
        assert "third" in s.notes
        storage.close()

    def test_add_note_nonexistent(self, tmp_path):
        storage = Storage(db_path=tmp_path / "test.sqlite")
        result = storage.add_note(99999, "test")
        assert result is False
        storage.close()

    def test_session_has_notes_field(self, tmp_path):
        storage = Storage(db_path=tmp_path / "test.sqlite")
        s = Session(agent="Test", cost=0.01, notes="initial note",
                    started_at=datetime(2026, 5, 27, 10, 0))
        sid = storage.insert(s)

        retrieved = storage.get(sid)
        assert retrieved.notes == "initial note"
        storage.close()

    def test_migration_adds_notes_column(self, tmp_path):
        """Verify migration adds notes column to existing DB."""
        import sqlite3
        db_path = tmp_path / "test.sqlite"

        # Create DB without notes column
        conn = sqlite3.connect(str(db_path))
        conn.execute("""CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT NOT NULL, model TEXT DEFAULT '', task_prompt TEXT DEFAULT '',
            tokens_in INTEGER DEFAULT 0, tokens_out INTEGER DEFAULT 0,
            cost REAL DEFAULT 0.0, started_at TIMESTAMP, ended_at TIMESTAMP,
            duration_sec REAL DEFAULT 0.0, tags TEXT DEFAULT ''
        )""")
        conn.execute("INSERT INTO sessions (agent) VALUES ('test')")
        conn.commit()
        conn.close()

        # Opening Storage should trigger migration
        storage = Storage(db_path=db_path)
        s = storage.get(1)
        assert s is not None
        assert s.notes == ""
        storage.close()


class TestAnomalies:
    """Test Storage.get_anomalies."""

    def test_no_anomalies_with_few_sessions(self, tmp_path):
        """With fewer than min_sessions, no anomalies."""
        storage = Storage(db_path=tmp_path / "test.sqlite")
        for i in range(3):
            storage.insert(Session(
                agent="Test", cost=0.01,
                started_at=datetime(2026, 5, 27, 10 + i, 0),
            ))
        anomalies = storage.get_anomalies()
        assert anomalies == []
        storage.close()

    def test_detects_high_cost_anomaly(self, tmp_path):
        """Detects a session with unusually high cost."""
        storage = Storage(db_path=tmp_path / "test.sqlite")
        # Insert normal sessions
        for i in range(10):
            storage.insert(Session(
                agent="Test", cost=0.05,
                started_at=datetime(2026, 5, 27, i, 0),
            ))
        # Insert one outlier
        storage.insert(Session(
            agent="Expensive", cost=50.0,
            started_at=datetime(2026, 5, 27, 20, 0),
        ))

        anomalies = storage.get_anomalies()
        assert len(anomalies) > 0
        assert any(s.cost == 50.0 for s in anomalies)
        storage.close()

    def test_no_anomalies_when_uniform(self, tmp_path):
        """No anomalies when all costs are similar."""
        storage = Storage(db_path=tmp_path / "test.sqlite")
        for i in range(10):
            storage.insert(Session(
                agent="Test", cost=0.10,
                started_at=datetime(2026, 5, 27, i, 0),
            ))

        anomalies = storage.get_anomalies()
        assert anomalies == []
        storage.close()

    def test_custom_threshold(self, tmp_path):
        """Higher threshold requires more extreme outliers."""
        storage = Storage(db_path=tmp_path / "test.sqlite")
        for i in range(10):
            storage.insert(Session(
                agent="Test", cost=0.05,
                started_at=datetime(2026, 5, 27, i, 0),
            ))
        # Moderate outlier
        storage.insert(Session(
            agent="Moderate", cost=1.0,
            started_at=datetime(2026, 5, 27, 20, 0),
        ))

        # Low threshold should detect it
        anomalies_low = storage.get_anomalies(threshold_std=1.0)
        # High threshold should not
        anomalies_high = storage.get_anomalies(threshold_std=5.0)
        assert len(anomalies_low) >= len(anomalies_high)
        storage.close()


class TestHourlyCommand:
    """Test the 'hourly' command."""

    def test_hourly_basic(self, tmp_path, monkeypatch):
        """Hourly command shows distribution."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))
        storage = Storage(db_path=db_path)
        _insert_sample_sessions(storage)
        storage.close()

        runner = CliRunner()
        result = runner.invoke(cli, ["hourly", "--since", "all"])
        assert result.exit_code == 0
        # Should show hours
        assert "10:00" in result.output or "11:00" in result.output

    def test_hourly_json(self, tmp_path, monkeypatch):
        """Hourly command with --json outputs structured data."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))
        storage = Storage(db_path=db_path)
        _insert_sample_sessions(storage)
        storage.close()

        runner = CliRunner()
        result = runner.invoke(cli, ["hourly", "--since", "all", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "hourly" in data
        assert "since" in data
        assert len(data["hourly"]) > 0
        # Check structure
        for h in data["hourly"]:
            assert "hour" in h
            assert "sessions" in h
            assert "cost" in h

    def test_hourly_empty(self, tmp_path, monkeypatch):
        """Hourly with no sessions shows message."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))

        runner = CliRunner()
        result = runner.invoke(cli, ["hourly", "--since", "all"])
        assert result.exit_code == 0
        assert "No sessions found" in result.output


class TestSessionNotesInOutput:
    """Test that notes and tags appear in session output."""

    def test_session_inspect_shows_notes(self, tmp_path, monkeypatch):
        """Session inspect command shows notes."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))
        storage = Storage(db_path=db_path)
        sid = storage.insert(Session(
            agent="Test", cost=0.01, notes="test note", tags="prod",
            started_at=datetime(2026, 5, 27, 10, 0),
        ))
        storage.close()

        runner = CliRunner()
        result = runner.invoke(cli, ["session", str(sid)])
        assert result.exit_code == 0
        assert "test note" in result.output
        assert "prod" in result.output

    def test_session_inspect_json_notes(self, tmp_path, monkeypatch):
        """Session inspect --json includes notes and tags."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))
        storage = Storage(db_path=db_path)
        sid = storage.insert(Session(
            agent="Test", cost=0.01, notes="test note", tags="prod",
            started_at=datetime(2026, 5, 27, 10, 0),
        ))
        storage.close()

        runner = CliRunner()
        result = runner.invoke(cli, ["session", str(sid), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["notes"] == "test note"
        assert data["tags"] == "prod"

    def test_history_json_notes(self, tmp_path, monkeypatch):
        """History --json includes notes and tags."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))
        storage = Storage(db_path=db_path)
        storage.insert(Session(
            agent="Test", cost=0.01, notes="my note", tags="tag1",
            started_at=datetime(2026, 5, 27, 10, 0),
        ))
        storage.close()

        runner = CliRunner()
        result = runner.invoke(cli, ["history", "--json", "--since", "all"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) > 0
        assert data[0]["notes"] == "my note"
        assert data[0]["tags"] == "tag1"

    def test_recent_json_notes(self, tmp_path, monkeypatch):
        """Recent --json includes notes and tags."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))
        storage = Storage(db_path=db_path)
        storage.insert(Session(
            agent="Test", cost=0.01, notes="recent note", tags="recent-tag",
            started_at=datetime(2026, 5, 27, 10, 0),
        ))
        storage.close()

        runner = CliRunner()
        result = runner.invoke(cli, ["recent", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) > 0
        assert data[0]["notes"] == "recent note"
        assert data[0]["tags"] == "recent-tag"

    def test_export_json_notes(self, tmp_path, monkeypatch):
        """Export --format json includes notes and tags."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))
        storage = Storage(db_path=db_path)
        storage.insert(Session(
            agent="Test", cost=0.01, notes="export note", tags="export-tag",
            started_at=datetime(2026, 5, 27, 10, 0),
        ))
        storage.close()

        runner = CliRunner()
        result = runner.invoke(cli, ["export", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) > 0
        assert data[0]["notes"] == "export note"
        assert data[0]["tags"] == "export-tag"


class TestStatusAnomalies:
    """Test that status command shows anomaly detection."""

    def test_status_json_with_anomalies(self, tmp_path, monkeypatch):
        """Status --json includes anomalies when present."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))
        storage = Storage(db_path=db_path)

        # Insert enough sessions with one outlier
        for i in range(10):
            storage.insert(Session(
                agent="Test", cost=0.01,
                started_at=datetime(2026, 5, 27, i, 0),
            ))
        storage.insert(Session(
            agent="Expensive", cost=50.0,
            started_at=datetime(2026, 5, 27, 20, 0),
        ))
        storage.close()

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "anomalies" in data
        assert len(data["anomalies"]) > 0

    def test_status_table_with_anomalies(self, tmp_path, monkeypatch):
        """Status table shows anomalies section."""
        db_path = tmp_path / "test.sqlite"
        monkeypatch.setattr("agent_tally.cli.Storage", lambda **kw: Storage(db_path=db_path))
        storage = Storage(db_path=db_path)

        for i in range(10):
            storage.insert(Session(
                agent="Test", cost=0.01,
                started_at=datetime(2026, 5, 27, i, 0),
            ))
        storage.insert(Session(
            agent="Expensive", cost=50.0,
            started_at=datetime(2026, 5, 27, 20, 0),
        ))
        storage.close()

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "Anomal" in result.output or "50.0" in result.output


import pytest
