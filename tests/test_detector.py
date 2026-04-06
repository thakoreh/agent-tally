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
        assert result is not None or result == {}


class TestParseModel:
    def test_model_in_output(self):
        info = AGENT_MAP["claude"]
        output = "Using model: claude-sonnet-4-20250514"
        result = parse_model(output, info)
        assert result is not None
        assert "claude" in result.lower()
