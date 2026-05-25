"""Tests for v0.11.0: frontier models, new token patterns, edge cases."""

from agent_tally.pricing import PricingConfig, ModelPricing, DEFAULT_PRICING, PROVIDER_GROUPS, detect_provider
from agent_tally.detector import parse_tokens, detect_agent, AgentType


class TestFrontierModels2026Q2:
    """Tests for newly added 2026 Q2 frontier models."""

    def test_claude_sonnet_5_pricing(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("claude-sonnet-5")
        assert model.input == 3.50
        assert model.output == 17.50

    def test_claude_haiku_5_pricing(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("claude-haiku-5")
        assert model.input == 1.20
        assert model.output == 6.00

    def test_gpt65_pricing(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("gpt-6.5")
        assert model.input == 5.00
        assert model.output == 25.00

    def test_gpt65_turbo_pricing(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("gpt-6.5-turbo")
        assert model.input == 20.00
        assert model.output == 80.00

    def test_gemini50_pro_pricing(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("gemini-5.0-pro")
        assert model.input == 2.00
        assert model.output == 15.00

    def test_gemini50_flash_pricing(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("gemini-5.0-flash")
        assert model.input == 0.20
        assert model.output == 0.80

    def test_grok5_mini_pricing(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("grok-5-mini")
        assert model.input == 0.40
        assert model.output == 1.50

    def test_deepseek_v55_pricing(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("deepseek-v5.5")
        assert model.input == 0.22
        assert model.output == 0.88

    def test_deepseek_r5_pricing(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("deepseek-r5")
        assert model.input == 0.80
        assert model.output == 3.20

    def test_llama5_pricing(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("llama-5")
        assert model.input == 0.30
        assert model.output == 1.20

    def test_mistral_7b_v2_pricing(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("mistral-7b-v2")
        assert model.input == 0.10
        assert model.output == 0.30


class TestFrontierModelProviderDetection:
    """Ensure new models map to correct providers."""

    def test_claude_sonnet_5_is_anthropic(self) -> None:
        assert detect_provider("claude-sonnet-5") == "Anthropic"

    def test_claude_haiku_5_is_anthropic(self) -> None:
        assert detect_provider("claude-haiku-5") == "Anthropic"

    def test_gpt65_is_openai(self) -> None:
        assert detect_provider("gpt-6.5") == "OpenAI"

    def test_gpt65_turbo_is_openai(self) -> None:
        assert detect_provider("gpt-6.5-turbo") == "OpenAI"

    def test_gemini50_pro_is_google(self) -> None:
        assert detect_provider("gemini-5.0-pro") == "Google"

    def test_gemini50_flash_is_google(self) -> None:
        assert detect_provider("gemini-5.0-flash") == "Google"

    def test_grok5_mini_is_xai(self) -> None:
        assert detect_provider("grok-5-mini") == "xAI"

    def test_deepseek_v55_is_deepseek(self) -> None:
        assert detect_provider("deepseek-v5.5") == "DeepSeek"

    def test_deepseek_r5_is_deepseek(self) -> None:
        assert detect_provider("deepseek-r5") == "DeepSeek"

    def test_llama5_is_meta(self) -> None:
        assert detect_provider("llama-5") == "Meta"

    def test_mistral_7b_v2_is_mistral(self) -> None:
        assert detect_provider("mistral-7b-v2") == "Mistral"


class TestFrontierModelCostCalculation:
    """Verify cost calculations for new frontier models."""

    def test_gpt65_cost(self) -> None:
        pricing = PricingConfig()
        # 1M input + 500K output
        cost = pricing.estimate("gpt-6.5", 1_000_000, 500_000)
        expected = (1.0 * 5.00) + (0.5 * 25.00)
        assert abs(cost - expected) < 0.0001

    def test_gpt65_turbo_cost(self) -> None:
        pricing = PricingConfig()
        # 100K in + 50K out
        cost = pricing.estimate("gpt-6.5-turbo", 100_000, 50_000)
        expected = (0.1 * 20.00) + (0.05 * 80.00)
        assert abs(cost - expected) < 0.0001

    def test_gemini50_pro_cost(self) -> None:
        pricing = PricingConfig()
        cost = pricing.estimate("gemini-5.0-pro", 500_000, 200_000)
        expected = (0.5 * 2.00) + (0.2 * 15.00)
        assert abs(cost - expected) < 0.0001

    def test_deepseek_r5_cost(self) -> None:
        pricing = PricingConfig()
        cost = pricing.estimate("deepseek-r5", 2_000_000, 1_000_000)
        expected = (2.0 * 0.80) + (1.0 * 3.20)
        assert abs(cost - expected) < 0.0001

    def test_claude_sonnet_5_cost(self) -> None:
        p = ModelPricing(name="claude-sonnet-5", input=3.50, output=17.50)
        cost = p.cost(500_000, 100_000)
        expected = (500_000 / 1_000_000 * 3.50) + (100_000 / 1_000_000 * 17.50)
        assert abs(cost - expected) < 0.0001


class TestNewTokenPatterns2026:
    """Tests for newly added 2026 token detection patterns."""

    def _parse(self, output: str) -> dict[str, int]:
        agent_info = detect_agent(["claude"])
        return parse_tokens(output, agent_info)

    def test_token_usage_json_format(self) -> None:
        result = self._parse('token_usage: {input: 5000, output: 2000}')
        assert result == {"tokens_in": 5000, "tokens_out": 2000}

    def test_usage_stats_format(self) -> None:
        result = self._parse('usage_stats {input_tokens: 3000 output_tokens: 1500}')
        assert result == {"tokens_in": 3000, "tokens_out": 1500}

    def test_tok_in_eq_format(self) -> None:
        result = self._parse('tok_in=1234 tok_out=5678')
        assert result == {"tokens_in": 1234, "tokens_out": 5678}

    def test_num_tokens_format(self) -> None:
        result = self._parse('num_tokens {input: 999 output: 888}')
        assert result == {"tokens_in": 999, "tokens_out": 888}

    def test_cost_prefixed_format(self) -> None:
        result = self._parse('$0.42 (5000 in / 2500 out)')
        assert result == {"tokens_in": 5000, "tokens_out": 2500}

    def test_arrow_token_format(self) -> None:
        result = self._parse('1234 → 5678 tokens')
        assert result == {"tokens_in": 1234, "tokens_out": 5678}

    def test_token_count_ndjson_format(self) -> None:
        result = self._parse('{"token_count": {"input": 4000, "output": 2000}}')
        assert result == {"tokens_in": 4000, "tokens_out": 2000}


class TestGenericAgentNewPatterns:
    """Test new patterns work with generic agent detection."""

    def _parse(self, output: str) -> dict[str, int]:
        agent_info = detect_agent(["unknown-agent"])
        return parse_tokens(output, agent_info)

    def test_generic_token_usage(self) -> None:
        result = self._parse('token_usage: {input: 100, output: 200}')
        assert result == {"tokens_in": 100, "tokens_out": 200}

    def test_generic_usage_stats(self) -> None:
        result = self._parse('usage_stats {input_tokens: 111 output_tokens: 222}')
        assert result == {"tokens_in": 111, "tokens_out": 222}

    def test_generic_tok_format(self) -> None:
        result = self._parse('tok_in=42 tok_out=24')
        assert result == {"tokens_in": 42, "tokens_out": 24}

    def test_generic_arrow_tokens(self) -> None:
        result = self._parse('1000 → 2000 tokens')
        assert result == {"tokens_in": 1000, "tokens_out": 2000}

    def test_generic_token_count_ndjson(self) -> None:
        result = self._parse('{"token_count": {"input": 333, "output": 444}}')
        assert result == {"tokens_in": 333, "tokens_out": 444}


class TestProviderGroupsCompletenessV11:
    """Ensure all DEFAULT_PRICING models appear in PROVIDER_GROUPS."""

    def test_all_priced_models_detectable(self) -> None:
        unknown = []
        for model_name in DEFAULT_PRICING:
            if detect_provider(model_name) == "Unknown":
                unknown.append(model_name)
        assert unknown == [], f"Unknown provider for: {unknown}"

    def test_frontier_models_in_provider_groups(self) -> None:
        assert "claude-sonnet-5" in PROVIDER_GROUPS["Anthropic"]
        assert "gpt-6.5" in PROVIDER_GROUPS["OpenAI"]
        assert "gemini-5.0-pro" in PROVIDER_GROUPS["Google"]
        assert "grok-5-mini" in PROVIDER_GROUPS["xAI"]
        assert "deepseek-r5" in PROVIDER_GROUPS["DeepSeek"]
        assert "llama-5" in PROVIDER_GROUPS["Meta"]
        assert "mistral-7b-v2" in PROVIDER_GROUPS["Mistral"]

    def test_provider_group_count(self) -> None:
        """Should have 19+ providers."""
        assert len(PROVIDER_GROUPS) >= 19

    def test_total_model_count_increased(self) -> None:
        """Should have 130+ models total."""
        assert len(DEFAULT_PRICING) >= 130


class TestEdgeCasesV11:
    """Edge case tests for robustness."""

    def test_empty_model_name_detection(self) -> None:
        assert detect_provider("") == "Unknown"

    def test_whitespace_model_name(self) -> None:
        assert detect_provider("  ") == "Unknown"

    def test_case_insensitive_provider_detection(self) -> None:
        assert detect_provider("Claude-Sonnet-5") == "Anthropic"

    def test_partial_model_match(self) -> None:
        """Partial prefix should still match."""
        assert detect_provider("claude-sonnet-5-turbo") == "Anthropic"

    def test_unknown_model(self) -> None:
        assert detect_provider("totally-unknown-model-xyz") == "Unknown"

    def test_model_with_special_chars(self) -> None:
        assert detect_provider("gpt-6.5-turbo") == "OpenAI"

    def test_pricing_unknown_model_returns_zero(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("nonexistent-model-xyz")
        assert model.input == 0.0
        assert model.output == 0.0
        assert model.cost(1000, 1000) == 0.0

    def test_pricing_fuzzy_match(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("claude-sonnet-5-custom")
        # Should fuzzy match to claude-sonnet-5
        assert model.input == 3.50

    def test_zero_tokens_cost(self) -> None:
        p = ModelPricing(name="test", input=5.0, output=10.0)
        assert p.cost(0, 0) == 0.0

    def test_large_token_cost(self) -> None:
        p = ModelPricing(name="test", input=1.0, output=1.0)
        cost = p.cost(1_000_000_000, 1_000_000_000)
        assert abs(cost - 2000.0) < 0.01

    def test_detect_agent_generic_fallback(self) -> None:
        agent = detect_agent(["totally-unknown-cli"])
        assert agent.agent_type == AgentType.GENERIC
        assert agent.display_name == "totally-unknown-cli"

    def test_detect_agent_empty_args(self) -> None:
        assert detect_agent([]) is None

    def test_parse_tokens_empty_output(self) -> None:
        agent = detect_agent(["claude"])
        assert parse_tokens("", agent) == {}

    def test_parse_tokens_no_match(self) -> None:
        agent = detect_agent(["claude"])
        assert parse_tokens("just some random text without tokens", agent) == {}
