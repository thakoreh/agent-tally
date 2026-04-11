"""Tests for new token patterns and models."""

import pytest
from agent_tally.detector import parse_tokens, AGENT_MAP
from agent_tally.pricing import PricingConfig, detect_provider


class TestNewTokenPatterns:
    """Test newly added token patterns for modern AI output formats."""

    def test_new_gemini_prompt_tokens_pattern(self):
        """Test Google Gemini 2.0 format: prompt_tokens / candidates_token_count."""
        info = AGENT_MAP["gemini"]
        output = 'prompt_tokens: 1800, candidates_token_count: 600'
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 1800
        assert result["tokens_out"] == 600

    def test_new_gemini_total_token_count_candidates_format(self):
        """Test Google API style: totalTokenCount / candidatesTokenCount."""
        info = AGENT_MAP["gemini"]
        output = '{"totalTokenCount": 5000, "candidatesTokenCount": 2000}'
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 5000
        assert result["tokens_out"] == 2000

    def test_anthropic_reasoning_tokens_format(self):
        """Test Anthropic reasoning tokens format."""
        info = AGENT_MAP["claude"]
        output = 'input_tokens: 1500, output_tokens: 750, reasoning_tokens: 300'
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 1500
        assert result["tokens_out"] == 750

    def test_openai_o1_reasoning_format(self):
        """Test OpenAI o1 model format."""
        info = AGENT_MAP["claude"]
        output = 'prompt_tokens: 2000, completion_tokens: 800, reasoning_tokens: 150'
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 2000
        assert result["tokens_out"] == 800

    def test_mistral_cache_tokens_format(self):
        """Test Mistral AI cache token format."""
        info = AGENT_MAP["claude"]
        output = 'input_tokens: 2500, output_tokens: 900, cache_creation_input_tokens: 100'
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 2500
        assert result["tokens_out"] == 900

    def test_cohere_billed_tokens_format(self):
        """Test Cohere billed tokens format."""
        info = AGENT_MAP["claude"]
        output = 'billed_input_tokens: 3000, billed_output_tokens: 1200'
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 3000
        assert result["tokens_out"] == 1200

    def test_llama_simple_format(self):
        """Test LLaMA simple format."""
        info = AGENT_MAP["claude"]
        output = 'input: 3500, output: 1100, ctx: 8000'
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 3500
        assert result["tokens_out"] == 1100

    def test_streaming_usage_format(self):
        """Test OpenAI streaming chunk usage format."""
        info = AGENT_MAP["claude"]
        output = '{"usage": {"prompt_tokens": 1200, "completion_tokens": 400, "total_tokens": 1600}}'
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 1200
        assert result["tokens_out"] == 400


class TestNewModels:
    """Test newly added models to the pricing configuration."""

    def test_new_anthropic_models(self):
        """Test new Anthropic models are priced correctly."""
        pricing = PricingConfig()
        
        # Test Claude 3.5 Sonnet 2024 format
        model = pricing.get("claude-3.5-sonnet-20241022")
        assert model.name == "claude-3.5-sonnet-20241022"
        assert model.input == 3.00
        assert model.output == 15.00
        
        # Calculate cost
        cost = model.cost(1000000, 500000)
        assert cost == (1.0 * 3.00) + (0.5 * 15.00)  # $3.00 + $7.50 = $10.50

    def test_new_openai_models(self):
        """Test new OpenAI models are priced correctly."""
        pricing = PricingConfig()
        
        # Test GPT-5o
        model = pricing.get("gpt-5o")
        assert model.name == "gpt-5o"
        assert model.input == 2.50
        assert model.output == 10.00
        
        # Calculate cost
        cost = model.cost(1000000, 500000)
        assert cost == (1.0 * 2.50) + (0.5 * 10.00)  # $2.50 + $5.00 = $7.50

    def test_new_google_models(self):
        """Test new Google models are priced correctly."""
        pricing = PricingConfig()
        
        # Test Gemini 4.0 Flash Experimental
        model = pricing.get("gemini-4.0-flash-exp")
        assert model.name == "gemini-4.0-flash-exp"
        assert model.input == 0.12
        assert model.output == 0.48
        
        # Calculate cost
        cost = model.cost(1000000, 500000)
        assert cost == (1.0 * 0.12) + (0.5 * 0.48)  # $0.12 + $0.24 = $0.36

    def test_new_xai_models(self):
        """Test new xAI models are priced correctly."""
        pricing = PricingConfig()
        
        # Test Grok 5
        model = pricing.get("grok-5")
        assert model.name == "grok-5"
        assert model.input == 2.50
        assert model.output == 12.50
        
        # Calculate cost
        cost = model.cost(1000000, 500000)
        assert cost == (1.0 * 2.50) + (0.5 * 12.50)  # $2.50 + $6.25 = $8.75

    def test_new_deepseek_models(self):
        """Test new DeepSeek models are priced correctly."""
        pricing = PricingConfig()
        
        # Test DeepSeek R3
        model = pricing.get("deepseek-r3")
        assert model.name == "deepseek-r3"
        assert model.input == 0.60
        assert model.output == 2.40
        
        # Calculate cost
        cost = model.cost(1000000, 500000)
        assert cost == (1.0 * 0.60) + (0.5 * 2.40)  # $0.60 + $1.20 = $1.80

    def test_new_meta_models(self):
        """Test new Meta models are priced correctly."""
        pricing = PricingConfig()
        
        # Test LLaMA 4.0
        model = pricing.get("llama-4.0")
        assert model.name == "llama-4.0"
        assert model.input == 0.25
        assert model.output == 1.00
        
        # Calculate cost
        cost = model.cost(1000000, 500000)
        assert cost == (1.0 * 0.25) + (0.5 * 1.00)  # $0.25 + $0.50 = $0.75

    def test_new_mistral_models(self):
        """Test new Mistral models are priced correctly."""
        pricing = PricingConfig()
        
        # Test Mistral Large 3
        model = pricing.get("mistral-large-3")
        assert model.name == "mistral-large-3"
        assert model.input == 2.50
        assert model.output == 7.50
        
        # Calculate cost
        cost = model.cost(1000000, 500000)
        assert cost == (1.0 * 2.50) + (0.5 * 7.50)  # $2.50 + $3.75 = $6.25

    def test_new_model_provider_detection(self):
        """Test that new models are correctly detected by provider."""
        # Test new Anthropic model
        assert detect_provider("claude-3.5-sonnet-20241022") == "Anthropic"
        
        # Test new OpenAI model
        assert detect_provider("gpt-5o") == "OpenAI"
        
        # Test new Google model
        assert detect_provider("gemini-4.0-flash-exp") == "Google"
        
        # Test new xAI model
        assert detect_provider("grok-5") == "xAI"
        
        # Test new DeepSeek model
        assert detect_provider("deepseek-r3") == "DeepSeek"
        
        # Test new Meta model
        assert detect_provider("llama-4.0") == "Meta"
        
        # Test new Mistral model
        assert detect_provider("mistral-large-3") == "Mistral"

    def test_fuzzy_model_matching(self):
        """Test that new models are matched correctly even with partial/fuzzy input."""
        pricing = PricingConfig()
        
        # Test partial matching
        model1 = pricing.get("claude-3.5-sonnet-2024")
        assert model1.input == 3.00  # Should match claude-3.5-sonnet-20241022
        
        model2 = pricing.get("gpt-5o-mini")  # Should fallback to gpt-5o
        assert model2.input == 2.50
        
        model3 = pricing.get("gemini-4.0-flash-exp")  # Exact match
        assert model3.input == 0.12

    def test_large_token_numbers_with_new_models(self):
        """Test that new models handle large token counts correctly."""
        pricing = PricingConfig()
        
        # Test with very large token counts
        model = pricing.get("grok-5")
        cost = model.cost(10000000, 5000000)  # 10M in, 5M out
        expected_cost = (10.0 * 2.50) + (5.0 * 12.50)  # $25.00 + $62.50 = $87.50
        assert cost == expected_cost
        
        # Test zero tokens
        zero_cost = model.cost(0, 0)
        assert zero_cost == 0.0