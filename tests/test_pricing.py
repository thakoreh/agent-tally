"""Tests for pricing calculations."""

from agent_tally.pricing import PricingConfig, ModelPricing


class TestModelPricing:
    def test_cost_calculation(self):
        p = ModelPricing(name="test", input=3.00, output=15.00)
        # 1M in + 1M out = $18
        cost = p.cost(1_000_000, 1_000_000)
        assert cost == 18.00

    def test_zero_tokens(self):
        p = ModelPricing(name="test", input=3.00, output=15.00)
        assert p.cost(0, 0) == 0.0

    def test_small_usage(self):
        p = ModelPricing(name="test", input=3.00, output=15.00)
        # 1000 in + 500 out
        cost = p.cost(1000, 500)
        expected = (1000 / 1_000_000 * 3.00) + (500 / 1_000_000 * 15.00)
        assert abs(cost - expected) < 0.0001


class TestPricingConfig:
    def test_default_models_loaded(self):
        config = PricingConfig()
        models = config.all_models()
        assert "claude-sonnet-4" in models
        assert "gpt-5.4" in models
        assert "gemini-3.1-pro" in models

    def test_get_known_model(self):
        config = PricingConfig()
        model = config.get("claude-sonnet-4")
        assert model.input == 3.00
        assert model.output == 15.00

    def test_get_unknown_model(self):
        config = PricingConfig()
        model = config.get("some-future-model")
        assert model.name == "some-future-model"
        assert model.input == 0.0

    def test_fuzzy_match(self):
        config = PricingConfig()
        model = config.get("claude-sonnet-4-20250514")
        # Should fuzzy match to claude-sonnet-4
        assert model.input > 0

    def test_estimate(self):
        config = PricingConfig()
        cost = config.estimate("claude-sonnet-4", 1_000_000, 1_000_000)
        assert cost == 18.00
