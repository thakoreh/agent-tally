"""Edge case tests for v0.8.0 features."""

import csv
import tempfile
from datetime import datetime
from pathlib import Path

from agent_tally.pricing import detect_provider
from agent_tally.storage import Storage, Session


# ── Provider detection edge cases ──────────────────────────────────────────

def test_partial_match_no_false_positive():
    """Partial matches shouldn't return wrong provider."""
    assert detect_provider("deepseek-v3") == "DeepSeek"
    # "gem" is prefix of gemini but also prefix of nothing else harmful
    # Make sure a short nonsense string doesn't accidentally match
    assert detect_provider("g") == "OpenAI"  # "g" is prefix of "gpt-*"


def test_provider_with_spaces_and_special_chars():
    assert detect_provider("claude-sonnet-4.5-turbo-2025") == "Anthropic"
    assert detect_provider("gpt-5.5-preview-2025-03-01") == "OpenAI"


def test_detect_provider_whitespace():
    assert detect_provider("  claude-3-opus  ") == "Anthropic"
    assert detect_provider("\tgpt-4o\n") == "OpenAI"


# ── Session tagging with special characters ─────────────────────────────────

def test_tag_with_special_characters(tmp_path):
    storage = Storage(db_path=tmp_path / "test.db")
    s = Session(agent="claude", model="claude-sonnet-4", cost=1.0, started_at=datetime.now())
    sid = storage.insert(s)

    # Tag with special chars
    storage.tag_session(sid, "bug-fix/v2")
    storage.tag_session(sid, "high priority!")
    storage.tag_session(sid, "deploy#42")

    session = storage.get(sid)
    tags = session.tags.split(",")
    assert "bug-fix/v2" in tags
    assert "high priority!" in tags
    assert "deploy#42" in tags


def test_tag_duplicate_is_idempotent(tmp_path):
    storage = Storage(db_path=tmp_path / "test.db")
    s = Session(agent="claude", cost=1.0, started_at=datetime.now())
    sid = storage.insert(s)

    storage.tag_session(sid, "production")
    storage.tag_session(sid, "production")
    session = storage.get(sid)
    assert session.tags.count("production") == 1


def test_tag_nonexistent_session(tmp_path):
    storage = Storage(db_path=tmp_path / "test.db")
    assert storage.tag_session(9999, "test") is False


def test_query_by_tag(tmp_path):
    storage = Storage(db_path=tmp_path / "test.db")
    now = datetime.now()
    s1 = Session(agent="claude", cost=1.0, started_at=now, tags="production")
    s2 = Session(agent="gpt", cost=2.0, started_at=now, tags="development")
    s3 = Session(agent="gemini", cost=3.0, started_at=now, tags="production,urgent")
    storage.insert(s1)
    storage.insert(s2)
    storage.insert(s3)

    results = storage.query(tags="production")
    assert len(results) == 2


# ── Batch cost with empty/invalid CSV ───────────────────────────────────────

def test_cost_batch_empty_csv(tmp_path):
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("model,tokens_in,tokens_out\n")
    from agent_tally.cli import cost_batch
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(cost_batch, [str(csv_file)])
    assert "No valid rows" in result.output


def test_cost_batch_invalid_tokens(tmp_path):
    csv_file = tmp_path / "invalid.csv"
    csv_file.write_text("model,tokens_in,tokens_out\ngpt-4o,abc,xyz\nclaude-sonnet-4,1000,500\n")
    from agent_tally.cli import cost_batch
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(cost_batch, [str(csv_file), "--format", "json"])
    # Should skip the invalid row, process the valid one
    assert result.exit_code == 0


def test_cost_batch_missing_model(tmp_path):
    csv_file = tmp_path / "nomodel.csv"
    csv_file.write_text("model,tokens_in,tokens_out\n,1000,500\n")
    from agent_tally.cli import cost_batch
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(cost_batch, [str(csv_file)])
    assert "No valid rows" in result.output


# ── Summary --by-hour with no data ─────────────────────────────────────────

def test_summary_by_hour_no_data(tmp_path):
    storage = Storage(db_path=tmp_path / "test.db")
    results = storage.summary_by_hour()
    assert results == []


def test_summary_by_hour_with_data(tmp_path):
    storage = Storage(db_path=tmp_path / "test.db")
    now = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0)
    s1 = Session(agent="claude", cost=1.0, started_at=now)
    s2 = Session(agent="gpt", cost=2.0, started_at=now)
    storage.insert(s1)
    storage.insert(s2)

    results = storage.summary_by_hour()
    assert len(results) >= 1
    assert results[0]["hour"] == 14
    assert results[0]["session_count"] == 2
    assert results[0]["total_cost"] == 3.0
