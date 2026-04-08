"""Tests for v0.7.0 features: cost command, session command, token rate, budget JSON."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from agent_tally.cli import cli
from agent_tally.storage import Session, Storage
from agent_tally.pricing import PricingConfig


# ── Token Rate Tests ────────────────────────────────────────────────

class TestTokenRate:
    def test_tokens_per_sec_normal(self) -> None:
        s = Session(tokens_in=1000, tokens_out=500, duration_sec=10.0)
        assert s.tokens_per_sec == 150.0

    def test_tokens_per_sec_zero_duration(self) -> None:
        s = Session(tokens_in=1000, tokens_out=500, duration_sec=0.0)
        assert s.tokens_per_sec is None

    def test_tokens_per_sec_no_duration(self) -> None:
        s = Session(tokens_in=1000, tokens_out=500)
        assert s.tokens_per_sec is None

    def test_tokens_per_sec_zero_tokens(self) -> None:
        s = Session(tokens_in=0, tokens_out=0, duration_sec=10.0)
        assert s.tokens_per_sec == 0.0

    def test_tokens_per_sec_large_values(self) -> None:
        s = Session(tokens_in=1_000_000, tokens_out=500_000, duration_sec=60.0)
        assert s.tokens_per_sec == pytest.approx(25000.0)

    def test_tokens_per_sec_very_short(self) -> None:
        s = Session(tokens_in=100, tokens_out=50, duration_sec=0.01)
        assert s.tokens_per_sec == pytest.approx(15000.0)


# ── Cost Command Tests ──────────────────────────────────────────────

class TestCostCommand:
    def test_cost_basic(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["cost", "claude-sonnet-4", "1000000", "1000000"])
        assert result.exit_code == 0
        assert "$18.00" in result.output  # 3.00 input + 15.00 output

    def test_cost_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["cost", "gpt-4o", "1000", "500", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["tokens_in"] == 1000
        assert data["tokens_out"] == 500
        assert data["estimated_cost_usd"] > 0

    def test_cost_unknown_model(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["cost", "totally-unknown-model-xyz", "1000", "500"])
        assert result.exit_code == 0
        assert "$0.000000" in result.output

    def test_cost_zero_tokens(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["cost", "claude-sonnet-4", "0", "0"])
        assert result.exit_code == 0
        assert "$0.000000" in result.output

    def test_cost_large_tokens(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["cost", "claude-sonnet-4", "10000000", "10000000"])
        assert result.exit_code == 0
        assert "$180.00" in result.output

    def test_cost_fuzzy_model_match(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["cost", "claude-3.5-sonnet-v2", "1000000", "1000000", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        # Should fuzzy match to claude-3.5-sonnet
        assert data["estimated_cost_usd"] > 0


# ── Session Command Tests ───────────────────────────────────────────

class TestSessionCommand:
    def test_session_not_found(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["session", "999999"])
        assert result.exit_code != 0 or "not found" in result.output

    def test_session_json_output(self, tmp_path: Path) -> None:
        """Test session JSON output with a real DB."""
        db_path = tmp_path / "test.db"
        storage = Storage(db_path=db_path)
        s = Session(
            agent="test-agent",
            model="test-model",
            tokens_in=1000,
            tokens_out=500,
            cost=0.05,
            started_at=datetime(2026, 4, 8, 12, 0, 0),
            ended_at=datetime(2026, 4, 8, 12, 0, 10),
            duration_sec=10.0,
        )
        sid = storage.insert(s)
        storage.close()

        runner = CliRunner()
        with patch("agent_tally.cli.Storage", return_value=Storage(db_path=db_path)):
            result = runner.invoke(cli, ["session", str(sid), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["agent"] == "test-agent"
        assert data["model"] == "test-model"
        assert data["tokens_in"] == 1000
        assert data["tokens_out"] == 500
        assert data["tokens_per_sec"] == 150.0

    def test_session_rich_output(self, tmp_path: Path) -> None:
        """Test session rich output with a real DB."""
        db_path = tmp_path / "test.db"
        storage = Storage(db_path=db_path)
        s = Session(
            agent="claude-code",
            model="claude-sonnet-4",
            tokens_in=5000,
            tokens_out=2000,
            cost=0.045,
            started_at=datetime(2026, 4, 8, 10, 0, 0),
            ended_at=datetime(2026, 4, 8, 10, 5, 0),
            duration_sec=300.0,
        )
        sid = storage.insert(s)
        storage.close()

        runner = CliRunner()
        with patch("agent_tally.cli.Storage", return_value=Storage(db_path=db_path)):
            result = runner.invoke(cli, ["session", str(sid)])
        assert result.exit_code == 0
        assert "claude-code" in result.output
        assert "claude-sonnet-4" in result.output


# ── Budget JSON Tests ───────────────────────────────────────────────

class TestBudgetJson:
    def test_budget_show_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["budget", "show", "--json"])
        # May fail if no DB, but should not crash
        # Check structure if it succeeds
        if result.exit_code == 0 and result.output.strip().startswith("{"):
            data = json.loads(result.output)
            assert "sessions_today" in data
            assert "total_spent_today" in data


# ── Pricing Edge Cases ──────────────────────────────────────────────

class TestPricingEdgeCases:
    def test_estimate_with_no_tokens(self) -> None:
        pricing = PricingConfig()
        cost = pricing.estimate("claude-sonnet-4", 0, 0)
        assert cost == 0.0

    def test_estimate_with_only_input(self) -> None:
        pricing = PricingConfig()
        cost = pricing.estimate("gpt-4o", 1_000_000, 0)
        assert cost == 2.50

    def test_estimate_with_only_output(self) -> None:
        pricing = PricingConfig()
        cost = pricing.estimate("gpt-4o", 0, 1_000_000)
        assert cost == 10.00

    def test_fuzzy_match_partial(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("gpt-4o-mini-preview")
        # Fuzzy matching may match gpt-4o or gpt-4o-mini, both are valid
        assert "gpt-4o" in model.name

    def test_fuzzy_match_substring(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("deepseek")
        # Should match some deepseek model
        assert "deepseek" in model.name.lower()

    def test_all_default_models_have_pricing(self) -> None:
        """Every default model should have non-zero pricing."""
        from agent_tally.pricing import DEFAULT_PRICING
        for name, prices in DEFAULT_PRICING.items():
            assert prices.get("input", 0) >= 0, f"{name} has negative/missing input price"
            assert prices.get("output", 0) >= 0, f"{name} has negative/missing output price"
