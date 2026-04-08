"""SQLite storage for agent session data."""

from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

DEFAULT_DB_PATH = Path.home() / ".agent-tally" / "db.sqlite"
MAX_TASK_PROMPT_LENGTH = 10_000


@dataclass
class Session:
    """A single agent tracking session."""
    id: Optional[int] = None
    agent: str = ""
    model: str = ""
    task_prompt: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_sec: float = 0.0

    @property
    def tokens_per_sec(self) -> Optional[float]:
        """Token throughput rate (tokens/second)."""
        if self.duration_sec and self.duration_sec > 0:
            return (self.tokens_in + self.tokens_out) / self.duration_sec
        return None


class Storage:
    """SQLite-backed storage for session data."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_table()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _ensure_table(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent TEXT NOT NULL,
                model TEXT DEFAULT '',
                task_prompt TEXT DEFAULT '',
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                cost REAL DEFAULT 0.0,
                started_at TIMESTAMP,
                ended_at TIMESTAMP,
                duration_sec REAL DEFAULT 0.0
            )
        """)
        conn.commit()
        conn.close()

    def insert(self, session: Session) -> int:
        """Insert a new session, return the ID."""
        # Validate task_prompt length
        if len(session.task_prompt) > MAX_TASK_PROMPT_LENGTH:
            session = Session(
                agent=session.agent,
                model=session.model,
                task_prompt=session.task_prompt[:MAX_TASK_PROMPT_LENGTH],
                tokens_in=session.tokens_in,
                tokens_out=session.tokens_out,
                cost=session.cost,
                started_at=session.started_at,
                ended_at=session.ended_at,
                duration_sec=session.duration_sec,
            )
        cursor = self.conn.execute(
            """INSERT INTO sessions (agent, model, task_prompt, tokens_in, tokens_out, cost, started_at, ended_at, duration_sec)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session.agent,
                session.model,
                session.task_prompt,
                session.tokens_in,
                session.tokens_out,
                session.cost,
                session.started_at.isoformat() if session.started_at else None,
                session.ended_at.isoformat() if session.ended_at else None,
                session.duration_sec,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def update(self, session: Session) -> None:
        """Update an existing session."""
        if session.id is None:
            return
        self.conn.execute(
            """UPDATE sessions SET tokens_in=?, tokens_out=?, cost=?, ended_at=?, duration_sec=?, model=?
               WHERE id=?""",
            (
                session.tokens_in,
                session.tokens_out,
                session.cost,
                session.ended_at.isoformat() if session.ended_at else None,
                session.duration_sec,
                session.model,
                session.id,
            ),
        )
        self.conn.commit()

    def get(self, session_id: int) -> Optional[Session]:
        """Get a session by ID."""
        row = self.conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def query(
        self,
        agent: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[Session]:
        """Query sessions with optional filters."""
        query = "SELECT * FROM sessions WHERE 1=1"
        params: list = []

        if agent:
            query += " AND agent = ?"
            params.append(agent)
        if since:
            query += " AND started_at >= ?"
            params.append(since.isoformat())
        if until:
            query += " AND started_at <= ?"
            params.append(until.isoformat())

        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_session(r) for r in rows]

    def summary(
        self,
        since: Optional[datetime] = None,
        group_by: str = "agent",
    ) -> list[dict]:
        """Get aggregated summary."""
        if group_by == "agent":
            col = "agent"
        elif group_by == "model":
            col = "model"
        elif group_by == "task":
            col = "task_prompt"
        else:
            col = "agent"

        query = f"""
            SELECT {col} as grp_key,
                   COUNT(*) as session_count,
                   SUM(tokens_in) as total_tokens_in,
                   SUM(tokens_out) as total_tokens_out,
                   SUM(cost) as total_cost,
                   AVG(duration_sec) as avg_duration
            FROM sessions WHERE 1=1
        """
        params: list = []
        if since:
            query += " AND started_at >= ?"
            params.append(since.isoformat())

        query += f" GROUP BY {col} ORDER BY total_cost DESC"

        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def _row_to_session(self, row: sqlite3.Row) -> Session:
        return Session(
            id=row["id"],
            agent=row["agent"],
            model=row["model"],
            task_prompt=row["task_prompt"],
            tokens_in=row["tokens_in"],
            tokens_out=row["tokens_out"],
            cost=row["cost"],
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
            duration_sec=row["duration_sec"],
        )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
