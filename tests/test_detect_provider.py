"""Tests for detect_provider utility."""

from agent_tally.pricing import detect_provider


def test_exact_match_anthropic():
    assert detect_provider("claude-sonnet-4") == "Anthropic"


def test_exact_match_openai():
    assert detect_provider("gpt-4o") == "OpenAI"


def test_exact_match_google():
    assert detect_provider("gemini-2.5-pro") == "Google"


def test_exact_match_xai():
    assert detect_provider("grok-3") == "xAI"


def test_exact_match_deepseek():
    assert detect_provider("deepseek-v4") == "DeepSeek"


def test_case_insensitive():
    assert detect_provider("CLAUDE-3.5-SONNET") == "Anthropic"
    assert detect_provider("GPT-5.4") == "OpenAI"


def test_unknown_model():
    assert detect_provider("totally-fake-model") == "Unknown"


def test_empty_string():
    assert detect_provider("") == "Unknown"


def test_partial_prefix_match():
    assert detect_provider("claude") == "Anthropic"
    assert detect_provider("gpt") == "OpenAI"
    assert detect_provider("gemini") == "Google"


def test_model_name_contains_known():
    assert detect_provider("deepseek-v3-custom-finetune") == "DeepSeek"
