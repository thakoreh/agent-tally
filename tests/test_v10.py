"""Tests for v0.10.0 additions: new providers, models, and provider detection."""

from agent_tally.pricing import PricingConfig, ModelPricing, DEFAULT_PRICING, PROVIDER_GROUPS, detect_provider


class TestNewProviders:
    """Tests for Snowflake, Writer, and Microsoft providers."""

    def test_snowflake_arctic_instruct_pricing(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("arctic-instruct")
        assert model.input == 0.20
        assert model.output == 0.60

    def test_snowflake_arctic_embed_pricing(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("arctic-embed")
        assert model.input == 0.05
        assert model.output == 0.05

    def test_writer_palmyra_x5_pricing(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("palmyra-x5")
        assert model.input == 1.00
        assert model.output == 4.00

    def test_writer_palmyra_x4_pricing(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("palmyra-x4")
        assert model.input == 0.50
        assert model.output == 2.00

    def test_microsoft_phi4_pricing(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("phi-4")
        assert model.input == 0.15
        assert model.output == 0.60

    def test_microsoft_maidsr1_pricing(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("mai-ds-r1")
        assert model.input == 0.20
        assert model.output == 0.80


class TestNewModels:
    """Tests for newly added model variants."""

    def test_claude_haiku_4(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("claude-haiku-4")
        assert model.input == 1.00
        assert model.output == 5.00

    def test_grok_35(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("grok-3.5")
        assert model.input == 0.60
        assert model.output == 2.50

    def test_grok_mini(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("grok-mini")
        assert model.input == 0.15
        assert model.output == 0.50

    def test_deepseek_v51(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("deepseek-v5.1")
        assert model.input == 0.18
        assert model.output == 0.70

    def test_deepseek_coder_v3(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("deepseek-coder-v3")
        assert model.input == 0.20
        assert model.output == 0.80

    def test_glm_71(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("glm-7.1")
        assert model.input == 0.16
        assert model.output == 0.64

    def test_qwen_4(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("qwen-4")
        assert model.input == 0.20
        assert model.output == 0.80

    def test_qwen_4_coder(self) -> None:
        pricing = PricingConfig()
        model = pricing.get("qwen-4-coder")
        assert model.input == 0.15
        assert model.output == 0.60


class TestNewProviderDetection:
    """Tests for detect_provider with new providers."""

    def test_detect_snowflake(self) -> None:
        assert detect_provider("arctic-instruct") == "Snowflake"
        assert detect_provider("arctic-embed") == "Snowflake"

    def test_detect_writer(self) -> None:
        assert detect_provider("palmyra-x5") == "Writer"
        assert detect_provider("palmyra-x4") == "Writer"

    def test_detect_microsoft(self) -> None:
        assert detect_provider("phi-4") == "Microsoft"
        assert detect_provider("mai-ds-r1") == "Microsoft"

    def test_detect_new_claude(self) -> None:
        assert detect_provider("claude-haiku-4") == "Anthropic"

    def test_detect_new_grok(self) -> None:
        assert detect_provider("grok-3.5") == "xAI"
        assert detect_provider("grok-mini") == "xAI"

    def test_detect_new_deepseek(self) -> None:
        assert detect_provider("deepseek-v5.1") == "DeepSeek"
        assert detect_provider("deepseek-coder-v3") == "DeepSeek"

    def test_detect_new_glm(self) -> None:
        assert detect_provider("glm-7.1") == "Chinese/Z.ai"

    def test_detect_new_qwen(self) -> None:
        assert detect_provider("qwen-4") == "Chinese/Z.ai"
        assert detect_provider("qwen-4-coder") == "Chinese/Z.ai"


class TestCostCalculationNewModels:
    """Verify cost calculations for new models."""

    def test_phi4_cost(self) -> None:
        p = ModelPricing(name="phi-4", input=0.15, output=0.60)
        # 100K in + 50K out
        cost = p.cost(100_000, 50_000)
        assert cost == (100_000 / 1_000_000 * 0.15) + (50_000 / 1_000_000 * 0.60)
        assert abs(cost - 0.045) < 0.0001

    def test_deepseek_coder_cost(self) -> None:
        pricing = PricingConfig()
        cost = pricing.estimate("deepseek-coder-v3", 500_000, 200_000)
        expected = (500_000 / 1_000_000 * 0.20) + (200_000 / 1_000_000 * 0.80)
        assert abs(cost - expected) < 0.0001

    def test_palmyra_cost(self) -> None:
        pricing = PricingConfig()
        cost = pricing.estimate("palmyra-x5", 1_000_000, 500_000)
        expected = (1 * 1.00) + (0.5 * 4.00)
        assert abs(cost - expected) < 0.0001


class TestProviderGroupsCompleteness:
    """Ensure all DEFAULT_PRICING models appear in PROVIDER_GROUPS."""

    def test_all_priced_models_in_provider_groups(self) -> None:
        """Every model in DEFAULT_PRICING should be findable via detect_provider."""
        unknown_models = []
        for model_name in DEFAULT_PRICING:
            provider = detect_provider(model_name)
            if provider == "Unknown":
                unknown_models.append(model_name)
        assert unknown_models == [], f"Models with Unknown provider: {unknown_models}"

    def test_provider_groups_has_new_entries(self) -> None:
        assert "Snowflake" in PROVIDER_GROUPS
        assert "Writer" in PROVIDER_GROUPS
        assert "Microsoft" in PROVIDER_GROUPS
        assert "arctic-instruct" in PROVIDER_GROUPS["Snowflake"]
        assert "palmyra-x5" in PROVIDER_GROUPS["Writer"]
        assert "phi-4" in PROVIDER_GROUPS["Microsoft"]
