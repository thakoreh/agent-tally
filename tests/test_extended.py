"""Extended tests for token detection and pricing edge cases."""

import pytest
from agent_tally.detector import (
    detect_agent, parse_tokens, parse_model, AgentType, AGENT_MAP,
)
from agent_tally.pricing import PricingConfig, ModelPricing, DEFAULT_PRICING


class TestParseTokensExtended:
    """Extended token parsing tests covering new regex patterns."""

    def test_claude_json_input_output_tokens(self):
        """Test JSON-style token output."""
        info = AGENT_MAP["claude"]
        output = 'Usage: {"input_tokens": 5000, "output_tokens": 2500}'
        result = parse_tokens(output, info)
        assert result["tokens_in"] == 5000
        assert result["tokens_out"] == 2500

    def test_claude_prompt_completion_tokens(self):
        """Test API-style prompt/completion tokens."""
        info = AGENT_MAP["claude"]
        output = '{"prompt_tokens": 10000, "completion_tokens": 3000}'
        result = parse_tokens(output, info)
        assert result["tokens_in"] == 10000
        assert result["tokens_out"] == 3000

    def test_input_tokens_with_case_variations(self):
        """Test Input tokens / Output tokens with mixed case."""
        info = AGENT_MAP["claude"]
        output = "Input tokens: 7500, Output tokens: 3200"
        result = parse_tokens(output, info)
        assert result["tokens_in"] == 7500
        assert result["tokens_out"] == 3200

    def test_codex_json_style(self):
        """Test Codex with JSON-style output."""
        info = AGENT_MAP["codex"]
        output = '{"input_tokens": 15000, "output_tokens": 6000}'
        result = parse_tokens(output, info)
        assert result["tokens_in"] == 15000
        assert result["tokens_out"] == 6000

    def test_gemini_google_api_style(self):
        """Test Gemini with Google API token format."""
        info = AGENT_MAP["gemini"]
        output = '{"totalTokenCount": 8000, "candidatesTokenCount": 4000}'
        result = parse_tokens(output, info)
        assert result["tokens_in"] == 8000
        assert result["tokens_out"] == 4000

    def test_openclaw_json_style(self):
        """Test OpenClaw with JSON output."""
        info = AGENT_MAP["openclaw"]
        output = '{"input_tokens": 12000, "output_tokens": 5000}'
        result = parse_tokens(output, info)
        assert result["tokens_in"] == 12000
        assert result["tokens_out"] == 5000

    def test_generic_json_tokens(self):
        """Test generic agent with JSON-style tokens."""
        info = detect_agent(["my-agent"])
        output = '{"prompt_tokens": 9000, "completion_tokens": 1000}'
        result = parse_tokens(output, info)
        assert result["tokens_in"] == 9000
        assert result["tokens_out"] == 1000

    def test_empty_output(self):
        """Test with empty output string."""
        info = AGENT_MAP["claude"]
        result = parse_tokens("", info)
        assert result == {}

    def test_no_matching_tokens(self):
        """Test output that has no token information."""
        info = AGENT_MAP["claude"]
        output = "The task is complete. All files have been updated."
        result = parse_tokens(output, info)
        assert result == {}

    def test_large_token_counts(self):
        """Test with very large token counts."""
        info = AGENT_MAP["claude"]
        output = "Tokens: 5000000 in, 3000000 out"
        result = parse_tokens(output, info)
        assert result["tokens_in"] == 5_000_000
        assert result["tokens_out"] == 3_000_000

    def test_multiline_output_with_tokens(self):
        """Test token extraction from multiline output."""
        info = AGENT_MAP["claude"]
        output = """Processing your request...
        Doing some work...
        Done!

        Tokens: 25000 in, 12000 out
        Model: claude-sonnet-4"""
        result = parse_tokens(output, info)
        assert result["tokens_in"] == 25000
        assert result["tokens_out"] == 12000


class TestDetectAgentExtended:
    """Extended agent detection tests."""

    def test_cursor_binary(self):
        """Cursor is now in AGENT_MAP, should be detected properly."""
        info = detect_agent(["cursor", "fix the code"])
        assert info is not None
        assert info.agent_type == AgentType.CURSOR

    def test_binary_with_path_prefix(self):
        """Test binary name with full path."""
        info = detect_agent(["/home/user/.local/bin/gemini", "hello"])
        assert info is not None
        assert info.agent_type == AgentType.GEMINI_CLI

    def test_binary_with_relative_path(self):
        """Test binary with relative path."""
        info = detect_agent(["./claude", "do stuff"])
        assert info is not None
        assert info.agent_type == AgentType.CLAUDE_CODE

    def test_all_known_agents(self):
        """All agents in the map should be detectable."""
        for cmd in AGENT_MAP:
            info = detect_agent([cmd])
            assert info is not None, f"Failed to detect agent: {cmd}"
            assert info.agent_type != AgentType.GENERIC, f"{cmd} should not be GENERIC"


class TestParseModel:
    """Extended model parsing tests."""

    def test_model_in_json_output(self):
        info = AGENT_MAP["claude"]
        output = 'Using model: claude-sonnet-4-20250514 for this session'
        result = parse_model(output, info)
        assert result is not None
        assert "claude-sonnet-4" in result

    def test_model_not_found(self):
        info = AGENT_MAP["claude"]
        output = "Task completed successfully. All files updated."
        result = parse_model(output, info)
        assert result is None

    def test_model_case_insensitive(self):
        info = AGENT_MAP["claude"]
        output = "Model: GPT-5.4"
        result = parse_model(output, info)
        assert result == "GPT-5.4"


class TestPricingExtended:
    """Extended pricing tests for new models."""

    def test_all_default_models_have_pricing(self):
        """Every model in DEFAULT_PRICING should have input and output."""
        for name, prices in DEFAULT_PRICING.items():
            assert "input" in prices, f"{name} missing input price"
            assert "output" in prices, f"{name} missing output price"
            assert prices["input"] >= 0, f"{name} has negative input price"
            assert prices["output"] >= 0, f"{name} has negative output price"

    def test_pricing_has_all_providers(self):
        """Check we have models from each major provider."""
        config = PricingConfig()
        models = config.all_models()

        # Anthropic
        assert any("claude" in k for k in models), "Missing Anthropic models"

        # OpenAI
        assert any("gpt" in k for k in models), "Missing OpenAI models"

        # Google
        assert any("gemini" in k for k in models), "Missing Google models"

        # xAI
        assert any("grok" in k for k in models), "Missing xAI models"

        # DeepSeek
        assert any("deepseek" in k for k in models), "Missing DeepSeek models"

        # Mistral
        assert any("mistral" in k for k in models), "Missing Mistral models"

        # Cohere
        assert any("command" in k for k in models), "Missing Cohere models"

    def test_fuzzy_match_partial(self):
        """Test fuzzy matching for model name substrings."""
        config = PricingConfig()

        # Should match claude-sonnet-4
        model = config.get("claude-sonnet-4-20250514")
        assert model.input > 0

    def test_fuzzy_match_prefix(self):
        """Test fuzzy matching with model prefix."""
        config = PricingConfig()
        model = config.get("deepseek")
        # Should match one of the deepseek models
        assert model.name.startswith("deepseek")

    def test_unknown_model_returns_zero(self):
        """Unknown models should return zero pricing."""
        config = PricingConfig()
        model = config.get("future-model-v99")
        assert model.input == 0.0
        assert model.output == 0.0
        cost = model.cost(1_000_000, 1_000_000)
        assert cost == 0.0

    def test_estimate_with_known_model(self):
        """Test cost estimation for a specific model."""
        config = PricingConfig()
        # gpt-4o: $2.50/M input, $10.00/M output
        cost = config.estimate("gpt-4o", 100_000, 50_000)
        expected = (100_000 / 1_000_000 * 2.50) + (50_000 / 1_000_000 * 10.00)
        assert abs(cost - expected) < 0.0001

    def test_model_pricing_cost_calculation(self):
        """Test ModelPricing.cost() with various values."""
        p = ModelPricing(name="test", input=1.0, output=5.0)

        # Zero tokens
        assert p.cost(0, 0) == 0.0

        # Only input
        assert p.cost(1_000_000, 0) == 1.0

        # Only output
        assert p.cost(0, 1_000_000) == 5.0

        # Both
        assert p.cost(1_000_000, 1_000_000) == 6.0

    def test_at_least_30_models(self):
        """We should have a decent model catalog."""
        assert len(DEFAULT_PRICING) >= 30, f"Only {len(DEFAULT_PRICING)} models, expected 30+"
