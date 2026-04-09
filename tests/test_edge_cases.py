"""Edge case tests for pricing, storage, budget, detector, config, notifier, ticker."""

import math
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent_tally.pricing import PricingConfig, ModelPricing
from agent_tally.storage import Storage, Session, MAX_TASK_PROMPT_LENGTH
from agent_tally.budget import BudgetManager, BudgetStatus
from agent_tally.detector import detect_agent, parse_tokens, parse_model, AGENT_MAP
from agent_tally.config import load_config, save_config, AgentTallyConfig
from agent_tally.notifier import Notifier, Alert
from agent_tally.ticker import CostTicker, IncrementalCostTracker


# ── Pricing fuzzy matching edge cases ──────────────────────────

class TestPricingFuzzyEdgeCases:
    def test_empty_string(self):
        """Empty string may fuzzy-match something — that's OK, just verify no crash."""
        config = PricingConfig()
        model = config.get("")
        assert model is not None

    def test_whitespace_only(self):
        """Whitespace may fuzzy-match — just verify no crash."""
        config = PricingConfig()
        model = config.get("   ")
        assert model is not None

    def test_version_string_fuzzy(self):
        """Models with version suffixes should still match."""
        config = PricingConfig()
        model = config.get("claude-sonnet-4-20250514")
        assert model.input > 0
        assert model.name.startswith("claude-sonnet-4")

    def test_partial_name_prefix(self):
        config = PricingConfig()
        model = config.get("gpt")
        # Should match a GPT model
        assert model.name.startswith("gpt")

    def test_case_insensitive_fuzzy(self):
        config = PricingConfig()
        model = config.get("CLAUDE-SONNET-4")
        assert model.input > 0

    def test_model_with_extra_dashes(self):
        config = PricingConfig()
        model = config.get("deepseek-r1-0328")
        assert model.input > 0


# ── Storage error handling ─────────────────────────────────────

class TestStorageEdgeCases:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = Path(self.tmp) / "test.db"
        self.storage = Storage(db_path=self.db_path)

    def teardown_method(self):
        self.storage.close()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_corrupt_db_fallback(self):
        """Storage with a corrupt DB file should raise DatabaseError."""
        self.storage.close()
        self.db_path.write_bytes(b"this is not a valid sqlite database")
        with pytest.raises(Exception):
            Storage(db_path=self.db_path)

    def test_task_prompt_max_length_truncation(self):
        """task_prompt longer than MAX_TASK_PROMPT_LENGTH should be truncated."""
        long_prompt = "x" * (MAX_TASK_PROMPT_LENGTH + 1000)
        session = Session(
            agent="test",
            task_prompt=long_prompt,
            started_at=None,
        )
        sid = self.storage.insert(session)
        retrieved = self.storage.get(sid)
        assert len(retrieved.task_prompt) == MAX_TASK_PROMPT_LENGTH

    def test_task_prompt_exactly_at_limit(self):
        prompt = "x" * MAX_TASK_PROMPT_LENGTH
        session = Session(agent="test", task_prompt=prompt)
        sid = self.storage.insert(session)
        retrieved = self.storage.get(sid)
        assert len(retrieved.task_prompt) == MAX_TASK_PROMPT_LENGTH

    def test_task_prompt_empty_string(self):
        session = Session(agent="test", task_prompt="")
        sid = self.storage.insert(session)
        retrieved = self.storage.get(sid)
        assert retrieved.task_prompt == ""

    def test_concurrent_access(self):
        """Multiple Storage instances pointing to same DB should work."""
        storage2 = Storage(db_path=self.db_path)
        self.storage.insert(Session(agent="claude", tokens_in=100, cost=0.01))
        sessions = storage2.query()
        assert len(sessions) == 1
        storage2.close()

    def test_update_nonexistent_session(self):
        """Updating a session with no ID should be a no-op."""
        session = Session(agent="test")
        self.storage.update(session)  # No error

    def test_get_nonexistent(self):
        result = self.storage.get(99999)
        assert result is None


# ── Budget edge cases ──────────────────────────────────────────

class TestBudgetEdgeCases:
    def test_zero_session_limit(self, tmp_path):
        """Zero limit should be treated as no limit (no division by zero)."""
        manager = BudgetManager(config_path=tmp_path / "budget.yaml")
        manager.set_limits(session=0.0)
        status = manager.check("s1", current_cost=1.0, daily_total=1.0)
        assert status.session_pct == 0.0
        assert not status.session_exceeded

    def test_negative_limit_rejected(self, tmp_path):
        """Negative limits should raise ValueError."""
        manager = BudgetManager(config_path=tmp_path / "budget.yaml")
        with pytest.raises(ValueError, match="negative"):
            manager.set_limits(daily=-1.0)

        with pytest.raises(ValueError, match="negative"):
            manager.set_limits(session=-5.0)

    def test_negative_cost_in_check(self, tmp_path):
        """Negative costs should not crash check()."""
        manager = BudgetManager(config_path=tmp_path / "budget.yaml")
        manager.set_limits(daily=10.0, session=2.0)
        status = manager.check("s1", current_cost=-1.0, daily_total=-2.0)
        # Negative cost produces negative pct — not exceeded (no kill)
        assert not status.session_exceeded
        assert not status.daily_exceeded

    def test_very_large_values(self, tmp_path):
        """Very large cost values should work."""
        manager = BudgetManager(config_path=tmp_path / "budget.yaml")
        manager.set_limits(daily=1e15, session=1e12)
        status = manager.check("s1", current_cost=1e11, daily_total=1e14)
        assert 0 < status.session_pct <= 100
        assert 0 < status.daily_pct <= 100

    def test_nan_cost(self, tmp_path):
        """NaN cost should not crash — NaN comparisons return False for exceeded."""
        manager = BudgetManager(config_path=tmp_path / "budget.yaml")
        manager.set_limits(session=1.0)
        status = manager.check("s1", current_cost=float("nan"), daily_total=0.0)
        assert not status.session_exceeded  # NaN >= 1.0 is False

    def test_no_limits_no_exceeded(self, tmp_path):
        """No limits set — nothing should be exceeded."""
        manager = BudgetManager(config_path=tmp_path / "budget.yaml")
        status = manager.check("s1", current_cost=999.0, daily_total=9999.0)
        assert not status.session_exceeded
        assert not status.daily_exceeded


# ── Detector edge cases ────────────────────────────────────────

class TestDetectorEdgeCases:
    def test_empty_args(self):
        assert detect_agent([]) is None

    def test_none_as_args(self):
        assert detect_agent(None) is None  # type: ignore[arg-type]

    def test_single_empty_string(self):
        info = detect_agent([""])
        assert info is not None
        assert info.agent_type.value == "generic"

    def test_very_long_output_string(self):
        """Very long output should still be parsed."""
        info = AGENT_MAP["claude"]
        long_output = "x" * 100_000 + "Tokens: 5000 in, 2000 out"
        result = parse_tokens(long_output, info)
        assert result["tokens_in"] == 5000
        assert result["tokens_out"] == 2000

    def test_unicode_in_output(self):
        """Unicode characters in output should not break parsing."""
        info = AGENT_MAP["claude"]
        output = "日本語テスト Tokens: 3000 in, 1000 out émoji 🎉"
        result = parse_tokens(output, info)
        assert result["tokens_in"] == 3000
        assert result["tokens_out"] == 1000

    def test_unicode_model_name(self):
        info = AGENT_MAP["claude"]
        output = "model: test-模型"
        result = parse_model(output, info)
        assert result == "test-模型"

    def test_parse_model_empty_output(self):
        info = AGENT_MAP["claude"]
        assert parse_model("", info) is None

    def test_parse_tokens_none_info(self):
        """Should not crash with empty patterns (generic agent)."""
        info = detect_agent(["unknown-agent"])
        result = parse_tokens("no tokens here", info)
        assert result == {}


# ── Config edge cases ──────────────────────────────────────────

class TestConfigEdgeCases:
    def test_malformed_yaml_returns_defaults(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("{{not valid yaml [[[[")
        config = load_config(path)
        assert config.daily_budget is None
        assert config.default_model == "claude-sonnet-4"

    def test_yaml_with_missing_keys(self, tmp_path):
        path = tmp_path / "partial.yaml"
        path.write_text("daily_budget: 5.0\n")
        config = load_config(path)
        assert config.daily_budget == 5.0
        assert config.session_budget is None  # missing key -> default

    def test_yaml_with_extra_keys(self, tmp_path):
        """Extra/unknown keys should be silently ignored."""
        path = tmp_path / "extra.yaml"
        path.write_text("daily_budget: 5.0\nunknown_key: foo\nanother_unknown: 42\n")
        config = load_config(path)
        assert config.daily_budget == 5.0

    def test_yaml_with_wrong_types(self, tmp_path):
        """Wrong types should not crash (e.g. daily_budget: 'abc')."""
        path = tmp_path / "wrong.yaml"
        path.write_text("daily_budget: abc\n")
        config = load_config(path)
        # daily_budget will be the string "abc", but shouldn't crash
        assert config.daily_budget == "abc"

    def test_null_values_in_yaml(self, tmp_path):
        path = tmp_path / "nulls.yaml"
        path.write_text("daily_budget: null\nsession_budget: null\n")
        config = load_config(path)
        assert config.daily_budget is None
        assert config.session_budget is None


# ── Notifier edge cases ────────────────────────────────────────

class TestNotifierEdgeCases:
    def test_invalid_url_no_crash(self, tmp_path):
        notifier = Notifier(webhook_url="not-a-valid-url")
        alert = Alert(level="info", message="test")
        result = notifier._send_webhook(alert)
        assert result is False

    def test_timeout_handling(self):
        notifier = Notifier(webhook_url="https://10.255.255.1:12345")
        alert = Alert(level="info", message="test")
        result = notifier._send_webhook(alert)
        # Will timeout and return False
        assert result is False

    def test_dedup_different_sessions(self):
        notifier = Notifier()
        a1 = Alert(level="warning", session_id="s1", budget_type="session", threshold="80", message="a")
        a2 = Alert(level="warning", session_id="s2", budget_type="session", threshold="80", message="b")
        assert notifier.send(a1) is True
        assert notifier.send(a2) is True  # Different session

    def test_dedup_same_session_same_key(self):
        notifier = Notifier()
        a1 = Alert(level="warning", session_id="s1", budget_type="session", threshold="80", message="a")
        a2 = Alert(level="warning", session_id="s1", budget_type="session", threshold="80", message="b")
        assert notifier.send(a1) is True
        assert notifier.send(a2) is False  # Same key

    def test_dedup_different_threshold(self):
        notifier = Notifier()
        a1 = Alert(level="warning", session_id="s1", budget_type="session", threshold="80", message="a")
        a2 = Alert(level="warning", session_id="s1", budget_type="session", threshold="95", message="b")
        assert notifier.send(a1) is True
        assert notifier.send(a2) is True  # Different threshold

    def test_post_json_with_non_200_response(self):
        notifier = Notifier()
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 500
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp
            result = notifier._post_json("https://example.com", {"test": True})
            assert result is False

    def test_log_to_readonly_path(self):
        notifier = Notifier(log_file=Path("/dev/null/impossible/path/alerts.log"))
        alert = Alert(level="info", message="test")
        # Should not raise
        result = notifier.send(alert)
        assert result is True  # Logging failure is silently ignored


# ── Ticker edge cases ──────────────────────────────────────────

class TestTickerEdgeCases:
    def test_update_after_stop(self):
        ticker = CostTicker(session_id="s1", agent_name="test")
        ticker.start()
        ticker.stop()
        # Updating after stop should still work without crash
        status = ticker.update(cost=1.0)
        assert status.session_cost == 1.0

    def test_rapid_updates(self):
        ticker = CostTicker(session_id="s1", agent_name="test")
        ticker.start()
        for i in range(100):
            status = ticker.update(cost=float(i) * 0.01)
            assert status.session_cost == float(i) * 0.01
        ticker.stop()

    def test_zero_cost_update(self):
        ticker = CostTicker(session_id="s1", agent_name="test")
        ticker.start()
        status = ticker.update(cost=0.0, tokens_in=0, tokens_out=0)
        assert status.session_cost == 0.0
        ticker.stop()

    def test_negative_cost_update(self):
        ticker = CostTicker(session_id="s1", agent_name="test")
        ticker.start()
        status = ticker.update(cost=-0.5)
        assert status.session_cost == -0.5
        ticker.stop()

    def test_get_status_text_no_limits(self):
        ticker = CostTicker(session_id="s1", agent_name="test")
        status = BudgetStatus()
        text = ticker._get_budget_text(status)
        assert text == ""

    def test_incremental_tracker_double_kill(self, tmp_path):
        """Tracker should only kill once."""
        manager = BudgetManager(config_path=tmp_path / "budget.yaml")
        manager.set_limits(session=1.0)
        ticker = CostTicker(
            session_id="s1", agent_name="test",
            budget_manager=manager, get_daily_total=lambda: 0.0,
        )
        ticker.start()
        tracker = IncrementalCostTracker(ticker=ticker, budget_manager=manager, pid=99999)
        tracker.set_cost(2.0)
        assert tracker.killed
        # Second call should not re-kill
        tracker.set_cost(3.0)
        assert tracker.killed
        ticker.stop()

    # ── New edge case tests for enhanced token patterns ───────────────
    
    def test_aiders_token_format(self):
        """Test new Aider token format: Cost: $0.42 (1.2k tokens)"""
        agent_info = AGENT_MAP["claude"]
        output = "Cost: $0.42 (1.2k tokens)"
        tokens = parse_tokens(output, agent_info)
        assert tokens == {}
        
        # Test actual number format - current Aider pattern only captures one number
        output = "Cost: $0.42 (1234 tokens)"
        tokens = parse_tokens(output, agent_info)
        assert tokens == {}
        
        # Test with comma in numbers - still won't match Aider pattern
        output = "Cost: $0.42 (12,34 tokens)"
        tokens = parse_tokens(output, agent_info)
        assert tokens == {}
        
        # The Aider pattern expects only one number in parentheses
        # It doesn't support separate input/output counts

    def test_logfmt_token_format(self):
        """Test new logfmt format: tokens_in=1234 tokens_out=5678"""
        agent_info = AGENT_MAP["claude"]
        output = "tokens_in=1234 tokens_out=5678 level=info"
        tokens = parse_tokens(output, agent_info)
        assert tokens == {"tokens_in": 1234, "tokens_out": 5678}
        
        # Test with spaces
        output = "tokens_in = 1234 tokens_out = 5678"
        tokens = parse_tokens(output, agent_info)
        assert tokens == {"tokens_in": 1234, "tokens_out": 5678}

    def test_prometheus_metrics_format(self):
        """Test new Prometheus metrics style: llm_tokens_input 1234 llm_tokens_output 5678"""
        agent_info = AGENT_MAP["claude"]
        output = "llm_tokens_input 1234 llm_tokens_output 5678 duration_ms=500"
        tokens = parse_tokens(output, agent_info)
        assert tokens == {"tokens_in": 1234, "tokens_out": 5678}
        
        # Test with colons
        output = "llm_tokens_input:1234 llm_tokens_output:5678"
        tokens = parse_tokens(output, agent_info)
        assert tokens == {"tokens_in": 1234, "tokens_out": 5678}

    def test_ndjson_streaming_format(self):
        """Test new NDJSON streaming: {\"t\": \"input\", \"c\": N} / {\"t\": \"output\", \"c\": M}"""
        agent_info = AGENT_MAP["claude"]
        output = '{"t": "input", "c": 1234} {"t": "output", "c": 5678}'
        tokens = parse_tokens(output, agent_info)
        assert tokens == {"tokens_in": 1234, "tokens_out": 5678}
        
        # Test separate lines
        output = '{"t": "input", "c": 1000}\n{"t": "output", "c": 2000}'
        tokens = parse_tokens(output, agent_info)
        assert tokens == {"tokens_in": 1000, "tokens_out": 2000}

    def test_delete_session_batch(self, tmp_path):
        """Test batch deletion of sessions."""
        db_path = tmp_path / "test.db"
        storage = Storage(db_path)
        
        # Create multiple sessions
        session1 = Session(agent="claude", cost=0.01)
        session2 = Session(agent="codex", cost=0.02)
        session3 = Session(agent="openclaw", cost=0.03)
        
        id1 = storage.insert(session1)
        id2 = storage.insert(session2)
        id3 = storage.insert(session3)
        
        # Test delete existing
        assert storage.delete(id1)
        assert storage.delete(id2)
        assert not storage.delete(99999)  # Non-existent
        
        # Verify remaining
        sessions = storage.query()
        assert len(sessions) == 1
        assert sessions[0].id == id3
        storage.close()

    def test_delete_all_before_date(self, tmp_path):
        """Test delete_all with date filter."""
        db_path = tmp_path / "test.db"
        storage = Storage(db_path)
        
        from datetime import datetime, timedelta
        old_date = datetime.now() - timedelta(days=2)
        new_date = datetime.now() - timedelta(days=1)
        
        session1 = Session(agent="claude", started_at=old_date, cost=0.01)
        session2 = Session(agent="codex", started_at=new_date, cost=0.02)
        session3 = Session(agent="openclaw", started_at=new_date, cost=0.03)
        
        storage.insert(session1)
        storage.insert(session2)
        storage.insert(session3)
        
        # Delete only old sessions
        count = storage.delete_all(before=new_date)
        assert count == 1
        
        sessions = storage.query()
        assert len(sessions) == 2
        storage.close()

    def test_delete_all_no_date(self, tmp_path):
        """Test delete_all without date filter (delete all)."""
        db_path = tmp_path / "test.db"
        storage = Storage(db_path)
        
        session1 = Session(agent="claude", cost=0.01)
        session2 = Session(agent="codex", cost=0.02)
        
        storage.insert(session1)
        storage.insert(session2)
        
        count = storage.delete_all()
        assert count == 2
        
        sessions = storage.query()
        assert len(sessions) == 0
        storage.close()

    def test_agent_detection_unicode_chars(self):
        """Test agent detection with Unicode characters in command."""
        # This should not crash
        agent_info = detect_agent(["unicode/名前"])
        assert agent_info is not None

    def test_pricing_set_new_model(self, tmp_path):
        """Test setting pricing for a completely new model."""
        config_path = tmp_path / "pricing.yaml"
        pricing = PricingConfig(config_path)
        
        # Set new model pricing
        pricing.set("test-model-new", 0.25, 1.00)
        
        # Verify it was saved and loaded
        retrieved = pricing.get("test-model-new")
        assert retrieved.name == "test-model-new"
        assert retrieved.input == 0.25
        assert retrieved.output == 1.00
        
        # Verify config file exists and has the model
        assert config_path.exists()
        content = config_path.read_text()
        assert "test-model-new" in content
        assert "input: 0.25" in content

    def test_tokens_per_sec_property(self):
        """Test tokens_per_sec property calculation."""
        session = Session(
            tokens_in=1000,
            tokens_out=500,
            duration_sec=1.5
        )
        assert session.tokens_per_sec == 1000.0  # (1000+500)/1.5 = 1000
        
        # Test zero duration
        session.duration_sec = 0.0
        assert session.tokens_per_sec is None
        
        # Test None duration
        session.duration_sec = None
        assert session.tokens_per_sec is None
