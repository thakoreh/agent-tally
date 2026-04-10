"""Test new model pricing and edge cases."""

from __future__ import annotations

import pytest
from agent_tally.pricing import PricingConfig, ModelPricing


class TestNewModelPricing:
    """Test newly added model pricing data."""

    def test_new_openai_models(self):
        """Test new OpenAI model pricing."""
        pricing = PricingConfig()
        
        # Test GPT-5.2 Pro (new flagship)
        model = pricing.get("gpt-5.2-pro")
        assert model.input == 21.00
        assert model.output == 168.00
        
        # Test GPT-5 Mini (new budget model)
        model = pricing.get("gpt-5-mini")
        assert model.input == 0.25
        assert model.output == 2.00
        
        # Test GPT-5 Nano (new ultra-budget model)
        model = pricing.get("gpt-5-nano")
        assert model.input == 0.05
        assert model.output == 0.40

    def test_new_anthropic_models(self):
        """Test new Anthropic model pricing."""
        pricing = PricingConfig()
        
        # Test Claude Opus 4.6 (newer model)
        model = pricing.get("claude-opus-4.6")
        assert model.input == 5.00
        assert model.output == 25.00

    def test_new_xai_models(self):
        """Test new xAI model pricing."""
        pricing = PricingConfig()
        
        # Test Grok 4.1 (newer model)
        model = pricing.get("grok-4.1")
        assert model.input == 0.20
        assert model.output == 0.50

    def test_new_google_models(self):
        """Test new Google model pricing."""
        pricing = PricingConfig()
        
        # Test Gemini 2.5 Flash 1.2 (updated pricing)
        model = pricing.get("gemini-2.5-flash-1.2")
        assert model.input == 0.30
        assert model.output == 2.50

    def test_cost_estimation_new_models(self):
        """Test cost estimation for new models."""
        pricing = PricingConfig()
        
        # Test GPT-5.2 Pro cost
        cost = pricing.estimate("gpt-5.2-pro", 1000000, 1000000)  # 1M each
        assert cost == 189.00  # 21 + 168
        
        # Test Grok 4.1 cost
        cost = pricing.estimate("grok-4.1", 1000000, 1000000)  # 1M each
        assert cost == 0.70  # 0.20 + 0.50
        
        # Test GPT-5 Nano cost
        cost = pricing.estimate("gpt-5-nano", 1000000, 1000000)  # 1M each
        assert cost == 0.45  # 0.05 + 0.40

    def test_fuzzy_matching_new_models(self):
        """Test fuzzy matching for new model names."""
        pricing = PricingConfig()
        
        # Test partial matches
        model = pricing.get("gpt-5")
        assert model.name in ["gpt-5.5", "gpt-5.4", "gpt-5.2-pro", "gpt-5-mini", "gpt-5-nano"]
        
        model = pricing.get("grok-4")
        assert model.name in ["grok-4.20", "grok-4", "grok-4.1"]
        
        model = pricing.get("claude-opus")
        assert model.name in ["claude-opus-4.5", "claude-opus-4", "claude-opus-4.6"]
        
        model = pricing.get("gemini-2.5")
        assert model.name in ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-1.2"]

    def test_provider_detection_new_models(self):
        """Test provider detection for new models."""
        from agent_tally.pricing import detect_provider
        
        # Test new OpenAI models
        assert detect_provider("gpt-5.2-pro") == "OpenAI"
        assert detect_provider("gpt-5-mini") == "OpenAI"
        assert detect_provider("gpt-5-nano") == "OpenAI"
        
        # Test new Anthropic models
        assert detect_provider("claude-opus-4.6") == "Anthropic"
        
        # Test new xAI models
        assert detect_provider("grok-4.1") == "xAI"
        
        # Test new Google models
        assert detect_provider("gemini-2.5-flash-1.2") == "Google"


class TestPricingEdgeCases:
    """Test edge cases for pricing configuration."""

    def test_zero_cost_models(self):
        """Test models with zero cost (if any exist)."""
        pricing = PricingConfig()
        
        # Test that all models have valid pricing
        for model_name in pricing.all_models():
            model = pricing.get(model_name)
            assert isinstance(model.input, (int, float))
            assert isinstance(model.output, (int, float))
            assert model.input >= 0
            assert model.output >= 0

    def test_very_large_token_counts(self):
        """Test cost calculation with very large token counts."""
        pricing = PricingConfig()
        
        # Test with extremely large token counts (near limits)
        # Using numbers that might cause floating point precision issues
        large_tokens = 10_000_000_000  # 10 billion tokens
        cost = pricing.estimate("gpt-4o", large_tokens, large_tokens)
        assert isinstance(cost, float)
        assert cost > 0

    def test_custom_model_overrides(self):
        """Test that custom pricing overrides work correctly."""
        pricing = PricingConfig()
        
        # Test setting custom pricing for a new model
        pricing.set("test-custom-model", 1.50, 7.50)
        
        model = pricing.get("test-custom-model")
        assert model.input == 1.50
        assert model.output == 7.50
        assert model.name == "test-custom-model"

    def test_model_not_found_fallback(self):
        """Test fallback behavior for unknown models."""
        pricing = PricingConfig()
        
        # Test completely unknown model
        model = pricing.get("completely-unknown-model-12345")
        assert model.name == "completely-unknown-model-12345"
        assert model.input == 0.0
        assert model.output == 0.0

    def test_model_similarity_detection(self):
        """Test detection of similar model names."""
        pricing = PricingConfig()
        
        # Test models that are similar but different
        gpt5_models = ["gpt-5", "gpt-5.5", "gpt-5.4", "gpt-5.2", "gpt-5.2-pro"]
        detected_models = []
        
        for model_name in gpt5_models:
            model = pricing.get(model_name)
            detected_models.append(model.name)
        
        # Should find different GPT-5 variants
        assert len(set(detected_models)) > 1

    def test_cost_precision(self):
        """Test cost calculation precision."""
        pricing = PricingConfig()
        
        # Test with small token counts
        cost = pricing.estimate("gpt-4o-mini", 100, 50)
        assert isinstance(cost, float)
        assert cost >= 0
        
        # Test cost should be reasonable (not zero for non-zero tokens)
        assert cost > 0

    def test_provider_grouping_consistency(self):
        """Test that provider grouping is consistent."""
        from agent_tally.pricing import PROVIDER_GROUPS
        
        # Check that all models in provider groups exist
        pricing = PricingConfig()
        all_models = pricing.all_models()
        
        for provider, models in PROVIDER_GROUPS.items():
            for model_name in models:
                assert model_name in all_models, f"Model {model_name} in provider {provider} not found in pricing"

    def test_models_by_provider(self):
        """Test models_by_provider method."""
        pricing = PricingConfig()
        
        provider_models = pricing.models_by_provider()
        
        # Should return a dict
        assert isinstance(provider_models, dict)
        
        # Should have some providers
        assert len(provider_models) > 0
        
        # Each provider should have a list of (model_name, ModelPricing) tuples
        for provider, models in provider_models.items():
            assert isinstance(models, list)
            for model_name, model_obj in models:
                assert isinstance(model_name, str)
                assert isinstance(model_obj, ModelPricing)