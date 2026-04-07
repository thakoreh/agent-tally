"""Tests for agent detection and token parsing."""

from agent_tally.detector import detect_agent, parse_tokens, parse_model, AgentType, AGENT_MAP


class TestDetectAgent:
    def test_claude_code(self):
        info = detect_agent(["claude", "--print", "fix the bug"])
        assert info is not None
        assert info.agent_type == AgentType.CLAUDE_CODE
        assert info.display_name == "Claude Code"

    def test_codex(self):
        info = detect_agent(["codex", "exec", "add tests"])
        assert info is not None
        assert info.agent_type == AgentType.CODEX

    def test_gemini(self):
        info = detect_agent(["gemini", "build", "the app"])
        assert info is not None
        assert info.agent_type == AgentType.GEMINI_CLI

    def test_openclaw(self):
        info = detect_agent(["openclaw", "run", "deploy"])
        assert info is not None
        assert info.agent_type == AgentType.OPENCLAW

    def test_generic_fallback(self):
        info = detect_agent(["some-new-agent", "do", "stuff"])
        assert info is not None
        assert info.agent_type == AgentType.GENERIC

    def test_empty_args(self):
        info = detect_agent([])
        assert info is None

    def test_path_binary(self):
        info = detect_agent(["/usr/local/bin/claude", "hello"])
        assert info is not None
        assert info.agent_type == AgentType.CLAUDE_CODE

    def test_nemoclaw(self):
        info = detect_agent(["nemoclaw", "run"])
        assert info is not None
        assert info.agent_type == AgentType.NEMOCLAW

    def test_kiro(self):
        info = detect_agent(["kiro", "analyze"])
        assert info is not None
        assert info.agent_type == AgentType.KIRO

    def test_auggie(self):
        info = detect_agent(["auggie", "build"])
        assert info is not None
        assert info.agent_type == AgentType.AUGGIE

    def test_goose(self):
        info = detect_agent(["goose", "task"])
        assert info is not None
        assert info.agent_type == AgentType.GOOSE

    def test_partial_match_in_binary(self):
        """Binary containing 'claude' in the name should match."""
        info = detect_agent(["my-claude-wrapper"])
        assert info is not None
        assert info.agent_type == AgentType.CLAUDE_CODE


class TestParseTokens:
    def test_claude_code_format(self):
        info = AGENT_MAP["claude"]
        output = "Tokens: 15234 in, 8321 out\nDone."
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 15234
        assert result["tokens_out"] == 8321

    def test_input_output_format(self):
        info = AGENT_MAP["codex"]
        output = "input: 5000 output: 2000"
        result = parse_tokens(output, info)
        assert result is not None

    def test_no_tokens(self):
        info = AGENT_MAP["claude"]
        output = "Just some output without tokens"
        result = parse_tokens(output, info)
        assert result == {}

    def test_json_input_tokens_format(self):
        info = AGENT_MAP["claude"]
        output = 'Response: {"input_tokens": 12000, "output_tokens": 4500}'
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 12000
        assert result["tokens_out"] == 4500

    def test_prompt_completion_tokens_format(self):
        info = AGENT_MAP["claude"]
        output = '{"prompt_tokens": 8000, "completion_tokens": 3000}'
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 8000
        assert result["tokens_out"] == 3000

    def test_google_api_format(self):
        """Google API style: totalTokenCount / candidatesTokenCount."""
        info = AGENT_MAP["gemini"]
        output = '{"totalTokenCount": 5000, "candidatesTokenCount": 2000}'
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 5000
        assert result["tokens_out"] == 2000

    def test_streaming_usage_format(self):
        """OpenAI streaming chunk usage format."""
        info = AGENT_MAP["claude"]
        output = '{"usage": {"prompt_tokens": 15000, "completion_tokens": 7500, "total_tokens": 22500}}'
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 15000
        assert result["tokens_out"] == 7500

    def test_tokens_in_out_kv_format(self):
        info = AGENT_MAP["claude"]
        output = "tokens_in: 3456 tokens_out: 1234"
        result = parse_tokens(output, info)
        assert result is not None

    def test_input_equals_output_format(self):
        info = AGENT_MAP["claude"]
        output = "input=9999 output=5555"
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 9999
        assert result["tokens_out"] == 5555

    def test_generic_agent_all_formats(self):
        """Generic agent should match multiple formats."""
        info = detect_agent(["custom-llm"])
        # test standard tokens in/out
        result = parse_tokens("5000 tokens in, 3000 tokens out", info)
        assert result is not None
        assert result["tokens_in"] == 5000

    def test_table_format_tokens(self):
        """Token table: | 5000 | 2000 | tokens"""
        info = AGENT_MAP["claude"]
        output = "| 5000 | 2000 | tokens used"
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 5000
        assert result["tokens_out"] == 2000

    def test_sse_tokens_format(self):
        """SSE data format: {"tokens": {"input": N, "output": M}}."""
        info = AGENT_MAP["claude"]
        output = 'data: {"tokens": {"input": 7500, "output": 3200}}'
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 7500
        assert result["tokens_out"] == 3200

    def test_cache_tokens_in_claude_format(self):
        info = AGENT_MAP["claude"]
        output = "15234 tokens in, 8321 tokens out, cache 5000"
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 15234
        assert result["tokens_out"] == 8321

    def test_large_token_numbers(self):
        info = AGENT_MAP["claude"]
        output = "Tokens: 1000000 in, 500000 out"
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 1000000
        assert result["tokens_out"] == 500000

    def test_zero_tokens(self):
        info = AGENT_MAP["claude"]
        output = "Tokens: 0 in, 0 out"
        result = parse_tokens(output, info)
        assert result is not None
        assert result["tokens_in"] == 0
        assert result["tokens_out"] == 0


class TestParseModel:
    def test_model_in_output(self):
        info = AGENT_MAP["claude"]
        output = "Using model: claude-sonnet-4-20250514"
        result = parse_model(output, info)
        assert result is not None
        assert "claude" in result.lower()

    def test_model_not_found(self):
        info = AGENT_MAP["claude"]
        output = "No info here"
        result = parse_model(output, info)
        assert result is None

    def test_model_from_different_agents(self):
        for agent_name in ["codex", "gemini", "openclaw"]:
            info = AGENT_MAP[agent_name]
            output = f"model: test-model-{agent_name}"
            result = parse_model(output, info)
            assert result is not None
            assert agent_name in result

    def test_model_case_insensitive(self):
        info = AGENT_MAP["claude"]
        output = "Model: Claude-Sonnet-4"
        result = parse_model(output, info)
        assert result is not None
