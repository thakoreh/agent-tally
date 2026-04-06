"""Tests for storage layer."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from agent_tally.storage import Session, Storage


class TestStorage:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = Path(self.tmp) / "test.db"
        self.storage = Storage(db_path=self.db_path)

    def teardown_method(self):
        self.storage.close()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_insert_and_get(self):
        session = Session(
            agent="Claude Code",
            model="claude-sonnet-4",
            task_prompt="fix the bug",
            tokens_in=5000,
            tokens_out=2000,
            cost=0.045,
            started_at=datetime.now(),
            duration_sec=12.5,
        )
        sid = self.storage.insert(session)
        assert sid > 0

        retrieved = self.storage.get(sid)
        assert retrieved is not None
        assert retrieved.agent == "Claude Code"
        assert retrieved.tokens_in == 5000

    def test_update(self):
        session = Session(agent="Codex", started_at=datetime.now())
        sid = self.storage.insert(session)

        session.id = sid
        session.tokens_in = 10000
        session.tokens_out = 3000
        session.cost = 0.055
        session.ended_at = datetime.now()
        session.duration_sec = 30.0
        self.storage.update(session)

        retrieved = self.storage.get(sid)
        assert retrieved.tokens_in == 10000
        assert retrieved.cost == 0.055

    def test_query(self):
        for i in range(5):
            self.storage.insert(Session(
                agent="Claude Code",
                started_at=datetime.now() - timedelta(minutes=i * 10),
            ))
        for i in range(3):
            self.storage.insert(Session(
                agent="Codex",
                started_at=datetime.now() - timedelta(minutes=i * 10),
            ))

        sessions = self.storage.query(limit=10)
        assert len(sessions) == 8

        claude_sessions = self.storage.query(agent="Claude Code", limit=10)
        assert len(claude_sessions) == 5

    def test_summary(self):
        self.storage.insert(Session(
            agent="Claude Code",
            tokens_in=10000,
            tokens_out=5000,
            cost=0.105,
            started_at=datetime.now(),
            duration_sec=15.0,
        ))
        self.storage.insert(Session(
            agent="Claude Code",
            tokens_in=8000,
            tokens_out=3000,
            cost=0.069,
            started_at=datetime.now(),
            duration_sec=10.0,
        ))
        self.storage.insert(Session(
            agent="Codex",
            tokens_in=20000,
            tokens_out=8000,
            cost=0.2,
            started_at=datetime.now(),
            duration_sec=20.0,
        ))

        summaries = self.storage.summary(group_by="agent")
        assert len(summaries) == 2
        # Claude Code should have 2 sessions
        cc = [s for s in summaries if s["grp_key"] == "Claude Code"][0]
        assert cc["session_count"] == 2
