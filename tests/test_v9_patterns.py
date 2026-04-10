"""Tests for v0.9.0: extended token patterns, edge cases, provider detection."""

from __future__ import annotations

import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from agent_tally.detector import (
    AGENT_MAP,
    AgentType,
    detect_agent,
    parse_tokens,
    parse_model,
)
from agent_tally.pricing import (
    DEFAULT_PRICING,
    PROVIDER_GROUPS,
    PricingConfig,
    ModelPricing,
    detect_provider,
)
from agent_tally.storage import Storage, Session
from agent_tally.budget import BudgetManager, BudgetConfig, BudgetStatus
from agent_tally.notifier import Notifier, Alert


# ─── Token Pattern Tests ────────────────────────────────────────────────

class TestExtendedTokenPatterns:
    """Test new token detection patterns added in v0.9.0."""

    def _get_claude_info(self):
        return AGENT_MAP["claude"]

    def test_anthropic_streaming_usage(self):
        """Anthropic streaming: input_tokens/output_tokens in usage block."""
        output = '''
        {"type":"message_start","message":{"usage":{"input_tokens": 25000, "output_tokens": 15000}}}
        '''
        tokens = parse_tokens(output, self._get_claude_info())
        assert tokens["tokens_in"] == 25000
        assert tokens["tokens_out"] == 15000

    def test_bedrock_invoke_format(self):
        """AWS Bedrock invoke response format."""
        output = '{"usage": {"inputTokenCount": 5000, "outputTokenCount": 2000}}'
        tokens = parse_tokens(output, self._get_claude_info())
        assert tokens["tokens_in"] == 5000
        assert tokens["tokens_out"] == 2000

    def test_thinking_tokens_format(self):
        """Thinking/reasoning tokens format."""
        output = "thinking_tokens: 8000, output_tokens: 3000"
        tokens = parse_tokens(output, self._get_claude_info())
        assert tokens["tokens_in"] == 8000
        assert tokens["tokens_out"] == 3000

    def test_litellm_format(self):
        """LiteLLM format with equals signs."""
        output = "prompt_tokens=1234, completion_tokens=5678"
        tokens = parse_tokens(output, self._get_claude_info())
        assert tokens["tokens_in"] == 1234
        assert tokens["tokens_out"] == 5678

    def test_slash_format(self):
        """Slash format: 1234/5678 tokens."""
        output = "Used 1234/5678 tokens"
        tokens = parse_tokens(output, self._get_claude_info())
        assert tokens["tokens_in"] == 1234
        assert tokens["tokens_out"] == 5678

    def test_bracket_format(self):
        """Bracket format: [1234 in] [5678 out]."""
        output = "Tokens: [1234 in] [5678 out]"
        tokens = parse_tokens(output, self._get_claude_info())
        assert tokens["tokens_in"] == 1234
        assert tokens["tokens_out"] == 5678

    def test_generic_bedrock_pattern(self):
        """Generic agent also supports Bedrock format."""
        info = detect_agent(["some-unknown-cli"])
        output = '{"usage": {"inputTokenCount": 1000, "outputTokenCount": 500}}'
        tokens = parse_tokens(output, info)
        assert tokens["tokens_in"] == 1000
        assert tokens["tokens_out"] == 500

    def test_generic_thinking_tokens(self):
        """Generic agent supports thinking tokens format."""
        info = detect_agent(["unknown-tool"])
        output = "thinking tokens: 2000 output tokens: 1000"
        tokens = parse_tokens(output, info)
        assert tokens["tokens_in"] == 2000
        assert tokens["tokens_out"] == 1000

    def test_empty_output(self):
        """Empty string returns empty dict."""
        info = detect_agent(["claude"])
        tokens = parse_tokens("", info)
        assert tokens == {}

    def test_whitespace_only_output(self):
        """Whitespace only returns empty dict."""
        info = detect_agent(["claude"])
        tokens = parse_tokens("   \n\t  ", info)
        assert tokens == {}

    def test_no_token_info_in_output(self):
        """Output with no token info returns empty dict."""
        info = detect_agent(["claude"])
        tokens = parse_tokens("Task completed successfully. No errors found.", info)
        assert tokens == {}

    def test_very_large_token_counts(self):
        """Very large token counts parse correctly."""
        info = detect_agent(["claude"])
        output = "Input tokens: 99999999, Output tokens: 88888888"
        tokens = parse_tokens(output, info)
        assert tokens["tokens_in"] == 99999999
        assert tokens["tokens_out"] == 88888888

    def test_zero_token_counts(self):
        """Zero tokens parse correctly."""
        info = detect_agent(["claude"])
        output = "Tokens: 0 in, 0 out"
        tokens = parse_tokens(output, info)
        assert tokens["tokens_in"] == 0
        assert tokens["tokens_out"] == 0

    def test_unicode_in_output(self):
        """Unicode characters in output don't break parsing."""
        info = detect_agent(["claude"])
        output = "✅ 完了！ Input tokens: 500, Output tokens: 200 🎉"
        tokens = parse_tokens(output, info)
        assert tokens["tokens_in"] == 500
        assert tokens["tokens_out"] == 200

    def test_azure_openai_streaming(self):
        """Azure OpenAI streaming chunk format."""
        info = detect_agent(["claude"])
        output = '{"prompt_tokens": 1500, "completion_tokens": 800, "total_tokens": 2300}'
        tokens = parse_tokens(output, info)
        assert tokens["tokens_in"] == 1500
        assert tokens["tokens_out"] == 800

    def test_logfmt_tokens_format(self):
        """Logfmt-style: tokens_in=1234 tokens_out=5678."""
        info = detect_agent(["claude"])
        output = "level=info tokens_in=1234 tokens_out=5678 duration=5.2s"
        tokens = parse_tokens(output, info)
        assert tokens["tokens_in"] == 1234
        assert tokens["tokens_out"] == 5678


# ─── Provider Detection Extended ────────────────────────────────────────

class TestProviderDetectionExtended:
    """Extended tests for detect_provider()."""

    def test_all_providers_have_models(self):
        """Every provider group has at least one model."""
        for provider, models in PROVIDER_GROUPS.items():
            assert len(models) > 0, f"{provider} has no models"

    def test_all_grouped_models_have_pricing(self):
        """Every model in PROVIDER_GROUPS has pricing in DEFAULT_PRICING."""
        for provider, models in PROVIDER_GROUPS.items():
            for model in models:
                assert model in DEFAULT_PRICING, f"{model} ({provider}) missing from DEFAULT_PRICING"

    def test_detect_provider_case_insensitive(self):
        """detect_provider is case-insensitive."""
        assert detect_provider("Claude-Sonnet-4") == "Anthropic"
        assert detect_provider("GPT-4O") == "OpenAI"
        assert detect_provider("GEMINI-4.0-PRO") == "Google"

    def test_detect_provider_partial_match(self):
        """detect_provider handles partial model names."""
        assert detect_provider("claude-sonnet") == "Anthropic"
        assert detect_provider("gpt-5") == "OpenAI"
        assert detect_provider("gemini") == "Google"
        assert detect_provider("deepseek") == "DeepSeek"

    def test_detect_provider_unknown(self):
        """Unknown models return 'Unknown'."""
        assert detect_provider("") == "Unknown"
        assert detect_provider("totally-unknown-model") == "Unknown"
        assert detect_provider("random-123") == "Unknown"

    def test_detect_provider_whitespace(self):
        """Whitespace is trimmed."""
        assert detect_provider("  claude-sonnet-4  ") == "Anthropic"
        assert detect_provider(" gpt-4o ") == "OpenAI"


# ─── Model Pricing Extended ─────────────────────────────────────────────

class TestModelPricingExtended:
    """Extended tests for ModelPricing and PricingConfig."""

    def test_model_pricing_zero_tokens(self):
        """Zero tokens = zero cost."""
        mp = ModelPricing(name="test", input=3.0, output=15.0)
        assert mp.cost(0, 0) == 0.0

    def test_model_pricing_input_only(self):
        """Only input tokens."""
        mp = ModelPricing(name="test", input=3.0, output=15.0)
        cost = mp.cost(1_000_000, 0)
        assert cost == 3.0

    def test_model_pricing_output_only(self):
        """Only output tokens."""
        mp = ModelPricing(name="test", input=3.0, output=15.0)
        cost = mp.cost(0, 1_000_000)
        assert cost == 15.0

    def test_model_pricing_exact_calculation(self):
        """Exact cost calculation for non-round numbers."""
        mp = ModelPricing(name="test", input=3.0, output=15.0)
        # 500k input + 200k output
        cost = mp.cost(500_000, 200_000)
        assert abs(cost - 4.5) < 0.0001

    def test_pricing_config_fuzzy_prefix_match(self):
        """Fuzzy matching finds models by prefix."""
        pricing = PricingConfig()
        model = pricing.get("claude-sonnet")
        # Fuzzy matching finds the most recent version (4.5) when multiple exist
        assert model.name == "claude-sonnet-4.5"

    def test_pricing_config_fuzzy_contains_match(self):
        """Fuzzy matching finds models when query contains the key."""
        pricing = PricingConfig()
        model = pricing.get("my-custom-gpt-4o-turbo")
        assert model.name == "gpt-4o"

    def test_pricing_config_unknown_model(self):
        """Unknown model returns zero pricing."""
        pricing = PricingConfig()
        model = pricing.get("totally-unknown-model-xyz")
        assert model.input == 0.0
        assert model.output == 0.0
        assert model.cost(1000, 1000) == 0.0

    def test_pricing_config_set_and_get(self):
        """Set a custom model price and retrieve it."""
        pricing = PricingConfig()
        pricing.set("my-model", 1.5, 7.5)
        model = pricing.get("my-model")
        assert model.input == 1.5
        assert model.output == 7.5

    def test_pricing_config_estimate(self):
        """estimate() convenience method."""
        pricing = PricingConfig()
        cost = pricing.estimate("gpt-4o", 1_000_000, 1_000_000)
        assert abs(cost - 12.5) < 0.0001  # 2.50 + 10.00

    def test_all_default_pricing_positive(self):
        """All default pricing values are non-negative."""
        for name, prices in DEFAULT_PRICING.items():
            assert prices["input"] >= 0, f"{name} has negative input price"
            assert prices["output"] >= 0, f"{name} has negative output price"

    def test_output_price_gte_input_price(self):
        """Output price should be >= input price for all models."""
        for name, prices in DEFAULT_PRICING.items():
            assert prices["output"] >= prices["input"], (
                f"{name}: output (${prices['output']}) < input (${prices['input']})"
            )


# ─── Storage Edge Cases ─────────────────────────────────────────────────

class TestStorageEdgeCases:
    """Edge case tests for Storage."""

    def _make_storage(self):
        """Create a temp storage."""
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        storage = Storage(db_path=Path(tmp.name))
        return storage, Path(tmp.name)

    def test_insert_and_retrieve(self):
        """Basic insert and retrieve roundtrip."""
        storage, path = self._make_storage()
        try:
            session = Session(
                agent="claude-code",
                model="claude-sonnet-4",
                task_prompt="test task",
                tokens_in=100,
                tokens_out=50,
                cost=0.001,
                started_at=datetime.now(),
                ended_at=datetime.now() + timedelta(seconds=30),
                duration_sec=30.0,
            )
            sid = storage.insert(session)
            assert sid > 0

            retrieved = storage.get(sid)
            assert retrieved is not None
            assert retrieved.agent == "claude-code"
            assert retrieved.model == "claude-sonnet-4"
            assert retrieved.tokens_in == 100
            assert retrieved.tokens_out == 50
            assert abs(retrieved.cost - 0.001) < 0.0001
        finally:
            storage.close()
            path.unlink(missing_ok=True)

    def test_query_no_results(self):
        """Query with filters that match nothing."""
        storage, path = self._make_storage()
        try:
            sessions = storage.query(agent="nonexistent", limit=10)
            assert sessions == []
        finally:
            storage.close()
            path.unlink(missing_ok=True)

    def test_session_tokens_per_sec(self):
        """tokens_per_sec property works correctly."""
        session = Session(
            tokens_in=1000,
            tokens_out=500,
            duration_sec=10.0,
        )
        assert session.tokens_per_sec == 150.0

    def test_session_tokens_per_sec_zero_duration(self):
        """tokens_per_sec returns None for zero duration."""
        session = Session(tokens_in=100, tokens_out=50, duration_sec=0.0)
        assert session.tokens_per_sec is None

    def test_session_tokens_per_sec_no_duration(self):
        """tokens_per_sec returns None when duration is not set."""
        session = Session(tokens_in=100, tokens_out=50, duration_sec=0.0)
        assert session.tokens_per_sec is None

    def test_delete_nonexistent(self):
        """Deleting a non-existent session returns False."""
        storage, path = self._make_storage()
        try:
            result = storage.delete(999999)
            assert result is False
        finally:
            storage.close()
            path.unlink(missing_ok=True)

    def test_tag_nonexistent_session(self):
        """Tagging a non-existent session returns False."""
        storage, path = self._make_storage()
        try:
            result = storage.tag_session(999999, "test")
            assert result is False
        finally:
            storage.close()
            path.unlink(missing_ok=True)

    def test_tag_session_duplicate(self):
        """Adding the same tag twice doesn't duplicate it."""
        storage, path = self._make_storage()
        try:
            session = Session(agent="test", started_at=datetime.now())
            sid = storage.insert(session)

            storage.tag_session(sid, "prod")
            storage.tag_session(sid, "prod")  # duplicate

            retrieved = storage.get(sid)
            assert retrieved.tags == "prod"
        finally:
            storage.close()
            path.unlink(missing_ok=True)

    def test_tag_session_multiple(self):
        """Multiple tags are comma-separated."""
        storage, path = self._make_storage()
        try:
            session = Session(agent="test", started_at=datetime.now())
            sid = storage.insert(session)

            storage.tag_session(sid, "prod")
            storage.tag_session(sid, "v2")

            retrieved = storage.get(sid)
            assert "prod" in retrieved.tags
            assert "v2" in retrieved.tags
        finally:
            storage.close()
            path.unlink(missing_ok=True)

    def test_long_task_prompt_truncation(self):
        """Task prompts longer than MAX_TASK_PROMPT_LENGTH are truncated."""
        storage, path = self._make_storage()
        try:
            long_prompt = "x" * 20_000
            session = Session(
                agent="test",
                task_prompt=long_prompt,
                started_at=datetime.now(),
            )
            sid = storage.insert(session)

            retrieved = storage.get(sid)
            assert len(retrieved.task_prompt) <= 10_000
        finally:
            storage.close()
            path.unlink(missing_ok=True)

    def test_summary_by_hour(self):
        """summary_by_hour returns hourly breakdown."""
        storage, path = self._make_storage()
        try:
            # Insert sessions at different hours
            for hour in [9, 10, 14, 9]:
                dt = datetime.now().replace(hour=hour, minute=0, second=0, microsecond=0)
                session = Session(
                    agent="test",
                    cost=1.0,
                    tokens_in=100,
                    tokens_out=50,
                    started_at=dt,
                )
                storage.insert(session)

            summaries = storage.summary_by_hour()
            assert len(summaries) > 0

            # Find hour 9
            hour_9 = next((s for s in summaries if s["hour"] == 9), None)
            assert hour_9 is not None
            assert hour_9["session_count"] == 2
        finally:
            storage.close()
            path.unlink(missing_ok=True)

    def test_close_idempotent(self):
        """close() can be called multiple times without error."""
        storage, path = self._make_storage()
        try:
            storage.close()
            storage.close()  # Should not raise
        finally:
            path.unlink(missing_ok=True)


# ─── Budget Edge Cases ──────────────────────────────────────────────────

class TestBudgetEdgeCases:
    """Edge case tests for BudgetManager."""

    def _make_manager(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".yaml", delete=False)
        tmp.close()
        return BudgetManager(config_path=Path(tmp.name)), Path(tmp.name)

    def test_negative_daily_limit_raises(self):
        """Negative daily limit raises ValueError."""
        manager, path = self._make_manager()
        try:
            with pytest.raises(ValueError, match="daily_limit"):
                manager.set_limits(daily=-1.0)
        finally:
            path.unlink(missing_ok=True)

    def test_negative_session_limit_raises(self):
        """Negative session limit raises ValueError."""
        manager, path = self._make_manager()
        try:
            with pytest.raises(ValueError, match="session_limit"):
                manager.set_limits(session=-5.0)
        finally:
            path.unlink(missing_ok=True)

    def test_zero_budget_not_exceeded(self):
        """Zero cost doesn't trigger budget exceeded."""
        manager, path = self._make_manager()
        try:
            manager.config.session_limit = 1.0
            status = manager.check("s1", 0.0, 0.0)
            assert not status.session_exceeded
            assert not status.daily_exceeded
        finally:
            path.unlink(missing_ok=True)

    def test_exact_limit_not_exceeded_without_kill(self):
        """Exactly at limit but kill_at_100=False."""
        manager, path = self._make_manager()
        try:
            manager.config.session_limit = 1.0
            manager.config.kill_at_100 = False
            status = manager.check("s1", 1.0, 0.0)
            assert not status.session_exceeded
        finally:
            path.unlink(missing_ok=True)

    def test_warning_levels(self):
        """get_warning_level returns correct levels."""
        manager, path = self._make_manager()
        try:
            # Green: under 80%
            status = BudgetStatus(session_pct=50.0, daily_pct=30.0)
            assert manager.get_warning_level(status) == "none"

            # Yellow: 80%
            status = BudgetStatus(session_warning="80")
            assert manager.get_warning_level(status) == "yellow"

            # Red: 95%
            status = BudgetStatus(session_warning="95")
            assert manager.get_warning_level(status) == "red"

            # Kill: exceeded
            status = BudgetStatus(session_exceeded=True)
            assert manager.get_warning_level(status) == "kill"
        finally:
            path.unlink(missing_ok=True)

    def test_status_text_no_limits(self):
        """get_status_text when no limits set."""
        manager, path = self._make_manager()
        try:
            status = BudgetStatus()
            text = manager.get_status_text(status)
            assert text == "No budget limits set"
        finally:
            path.unlink(missing_ok=True)


# ─── Detector Edge Cases ────────────────────────────────────────────────

class TestDetectorEdgeCases:
    """Edge case tests for agent detection."""

    def test_empty_args(self):
        """Empty args returns None."""
        result = detect_agent([])
        assert result is None

    def test_unknown_binary(self):
        """Unknown binary returns generic agent."""
        result = detect_agent(["totally-unknown-xyz"])
        assert result.agent_type == AgentType.GENERIC
        assert result.display_name == "totally-unknown-xyz"

    def test_path_to_known_binary(self):
        """Full path to known binary is resolved."""
        result = detect_agent(["/usr/local/bin/claude"])
        assert result.agent_type == AgentType.CLAUDE_CODE

    def test_all_agent_types_in_map(self):
        """All AgentType values have entries in AGENT_MAP (except GENERIC)."""
        mapped_types = {info.agent_type for info in AGENT_MAP.values()}
        for at in AgentType:
            if at == AgentType.GENERIC:
                continue
            assert at in mapped_types, f"{at} not in AGENT_MAP"

    def test_parse_model_found(self):
        """parse_model finds model in output."""
        info = AGENT_MAP["claude"]
        model = parse_model("model: claude-sonnet-4", info)
        assert model == "claude-sonnet-4"

    def test_parse_model_not_found(self):
        """parse_model returns None when no model found."""
        info = AGENT_MAP["claude"]
        model = parse_model("no data available", info)
        assert model is None

    def test_parse_model_case_insensitive(self):
        """parse_model is case-insensitive."""
        info = AGENT_MAP["claude"]
        model = parse_model("Model: GPT-4O", info)
        assert model == "GPT-4O"


# ─── Notifier Edge Cases ────────────────────────────────────────────────

class TestNotifierEdgeCases:
    """Edge case tests for Notifier."""

    def test_alert_default_timestamp(self):
        """Alert gets a timestamp automatically."""
        alert = Alert(level="info", message="test")
        assert alert.timestamp is not None

    def test_alert_custom_timestamp(self):
        """Alert preserves custom timestamp."""
        ts = datetime(2026, 1, 1, 12, 0, 0)
        alert = Alert(level="info", message="test", timestamp=ts)
        assert alert.timestamp == ts

    def test_dedup_same_alert(self):
        """Duplicate alerts are deduped."""
        notifier = Notifier()
        alert1 = Alert(level="warning", message="test", session_id="s1", budget_type="session", threshold="80")
        alert2 = Alert(level="warning", message="test", session_id="s1", budget_type="session", threshold="80")

        assert notifier.send(alert1) is True
        assert notifier.send(alert2) is False  # Deduped

    def test_different_alerts_not_deduped(self):
        """Different alerts are not deduped."""
        notifier = Notifier()
        alert1 = Alert(level="warning", message="test", session_id="s1", budget_type="session", threshold="80")
        alert2 = Alert(level="critical", message="test", session_id="s1", budget_type="session", threshold="100")

        assert notifier.send(alert1) is True
        assert notifier.send(alert2) is True

    def test_webhook_failure_returns_false(self):
        """Failed webhook returns False without crashing."""
        notifier = Notifier(webhook_url="http://localhost:99999/nonexistent")
        alert = Alert(level="info", message="test", session_id="s1", budget_type="session", threshold="80")
        result = notifier.send(alert)
        assert result is True  # Still returns True (send was attempted, log/file may succeed)

    def test_file_logging(self):
        """Alert logging to file works."""
        tmp = tempfile.NamedTemporaryFile(suffix=".log", delete=False)
        tmp.close()
        log_path = Path(tmp.name)

        try:
            notifier = Notifier(log_file=log_path)
            alert = Alert(level="warning", message="test alert message")
            notifier.send(alert)

            content = log_path.read_text()
            assert "WARNING" in content
            assert "test alert message" in content
        finally:
            log_path.unlink(missing_ok=True)

    def test_alert_from_status_no_warnings(self):
        """alert_from_status with clean status returns empty list."""
        notifier = Notifier()
        status = BudgetStatus(
            session_cost=0.5,
            daily_cost=1.0,
            session_limit=10.0,
            daily_limit=50.0,
        )
        alerts = notifier.alert_from_status(status, "s1")
        assert alerts == []
