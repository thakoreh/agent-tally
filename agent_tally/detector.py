"""Agent detection and command parsing."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AgentType(Enum):
    """Supported agent types."""
    CLAUDE_CODE = "claude-code"
    CODEX = "codex"
    GEMINI_CLI = "gemini-cli"
    OPENCLAW = "openclaw"
    NEMOCLAW = "nemoclaw"
    CURSOR = "cursor"
    AUGGIE = "auggie"
    GOOSE = "goose"
    KIRO = "kiro"
    GENERIC = "generic"


@dataclass
class AgentInfo:
    """Metadata about a detected agent CLI."""
    agent_type: AgentType
    display_name: str
    cli_command: str  # e.g. "claude", "codex", "openclaw"
    model_pattern: str  # regex to find model name in output
    token_patterns: list[str]  # regex patterns for token extraction


# Map of CLI binary name -> agent info
AGENT_MAP: dict[str, AgentInfo] = {
    "claude": AgentInfo(
        agent_type=AgentType.CLAUDE_CODE,
        display_name="Claude Code",
        cli_command="claude",
        model_pattern=r"model[:\s]+(\S+)",
        token_patterns=[
            # "15234 tokens in, 8321 out, cache 5000" (Claude Code)
            r"(\d+)\s*tokens?\s*in.*?(\d+).*?tokens?\s*out.*?(\d+)",
            # "Tokens: 15234 in, 8321 out"
            r"Tokens:\s*(\d+)\s*in.*?(\d+)\s*out",
            # "input: 5000 output: 2000"
            r"input[:\s]+(\d+).*?output[:\s]+(\d+)",
            # "Input tokens: 5000, Output tokens: 2000"
            r"[Ii]nput\s*tokens?[:\s]+(\d+).*?[Oo]utput\s*tokens?[:\s]+(\d+)",
            # JSON-style: "usage": {"input_tokens": 5000, "output_tokens": 2000}
            r'"input_tokens"[:\s]+(\d+).*?"output_tokens"[:\s]+(\d+)',
            # API-style: "prompt_tokens": 5000, "completion_tokens": 2000
            r'"prompt_tokens"[:\s]+(\d+).*?"completion_tokens"[:\s]+(\d+)',
            # Additional patterns for robustness
            r'total\s*tokens?[:\s]+(\d+)\s*,\s*tokens?\s*used[:\s]+(\d+)',
            r'(\d+)\s*token\s*in.*?(\d+)\s*token\s*out',
            r'(\d+)\s*input.*?(\d+)\s*output',
            r'(\d+)\s* consumed.*?(\d+)\s*generated',
            r'\b(\d+)\s*tokens?\s*input\b.*?\b(\d+)\s*tokens?\s*output\b',
            r'input=(\d+).*?output=(\d+)',
            # Streaming chunk format: "usage" with prompt/completion tokens
            r'"usage"\s*:\s*\{[^}]*"prompt_tokens"\s*:\s*(\d+)[^}]*"completion_tokens"\s*:\s*(\d+)',
            # Table format: "| Input | Output |" rows
            r'\|\s*(\d+)\s*\|\s*(\d+)\s*\|.*tokens',
            # SSE/data format: {"tokens": {"input": N, "output": M}}
            r'"tokens"\s*:\s*\{[^}]*"input"\s*:\s*(\d+)[^}]*"output"\s*:\s*(\d+)',
            # Aider format: "Cost: $0.42 (1.2k tokens)
            r'[Cc]ost[:\s]+\$[\d.]+\s*\((\d+).*?tokens?\)',
            # Logfmt: tokens_in=1234 tokens_out=5678
            r'tokens_in[:\s=]+(\d+).*?tokens_out[:\s=]+(\d+)',
            # Prometheus metrics style: llm_tokens_input 1234 llm_tokens_output 5678
            r'llm_tokens_input[:\s]+(\d+).*?llm_tokens_output[:\s]+(\d+)',
            # NDJSON streaming: {"t": "input", "c": N} / {"t": "output", "c": M}
            r'"t"\s*:\s*"input".*?"c"\s*:\s*(\d+).*?"t"\s*:\s*"output".*?"c"\s*:\s*(\d+)',
            # Anthropic streaming: message_start/message_delta with usage block
            r'"input_tokens"\s*:\s*(\d+).*?"output_tokens"\s*:\s*(\d+)',
            # Azure OpenAI streaming format
            r'"prompt_tokens"\s*:\s*(\d+).*?"completion_tokens"\s*:\s*(\d+).*?"total_tokens"',
            # Bedrock invoke response: usage.inputTokenCount/outputTokenCount
            r'inputTokenCount[\s":]+(\d+).*?outputTokenCount[\s":]+(\d+)',
            # Vertex AI: totalTokenCount + candidatesTokenCount
            r'"totalTokenCount"\s*:\s*(\d+).*?"candidatesTokenCount"\s*:\s*(\d+)',
            # Thinking/reasoning tokens: thinking_tokens: N, output_tokens: M
            r'thinking[_\s]?tokens?[:\s]+(\d+).*?output[_\s]?tokens?[:\s]+(\d+)',
            # Litellm format
            r'prompt_tokens\s*=\s*(\d+).*?completion_tokens\s*=\s*(\d+)',
            # Anthropic headers style
            r'x[-_]input[-_]tokens?[:\s]+(\d+).*?x[-_]output[-_]tokens?[:\s]+(\d+)',
            # Generic key=value: tokens_in=123 tokens_out=456
            r'tokens[_\s-]?in[=:\s]+(\d+).*?tokens[_\s-]?out[=:\s]+(\d+)',
            # Slash format: 1234/5678 tokens
            r'(\d+)\s*/\s*(\d+)\s*tokens',
            # Bracket format: [1234 in] [5678 out]
            r'\[\s*(\d+)\s*in\s*\].*?\[\s*(\d+)\s*out\s*\]',
        ],
    ),
    "codex": AgentInfo(
        agent_type=AgentType.CODEX,
        display_name="Codex CLI",
        cli_command="codex",
        model_pattern=r"model[:\s]+(\S+)",
        token_patterns=[
            r"tokens[_\s]*in[:\s]+(\d+).*?tokens[_\s]*out[:\s]+(\d+)",
            r"(\d+)\s*input\s*tokens.*?(\d+)\s*output\s*tokens",
            r"[Ii]nput[:\s]+(\d+).*?[Oo]utput[:\s]+(\d+)",
            r'"input_tokens"[:\s]+(\d+).*?"output_tokens"[:\s]+(\d+)',
        ],
    ),
    "gemini": AgentInfo(
        agent_type=AgentType.GEMINI_CLI,
        display_name="Gemini CLI",
        cli_command="gemini",
        model_pattern=r"model[:\s]+(\S+)",
        token_patterns=[
            r"input.*?(\d+).*?output.*?(\d+)",
            r"tokens.*?(\d+).*?tokens.*?(\d+)",
            r"[Ii]nput\s*tokens?[:\s]+(\d+).*?[Oo]utput\s*tokens?[:\s]+(\d+)",
            # Google API style: totalTokenCount / candidatesTokenCount
            r'"totalTokenCount"[:\s]+(\d+).*?"candidatesTokenCount"[:\s]+(\d+)',
        ],
    ),
    "openclaw": AgentInfo(
        agent_type=AgentType.OPENCLAW,
        display_name="OpenClaw",
        cli_command="openclaw",
        model_pattern=r"model[:\s]+(\S+)",
        token_patterns=[
            r"tokens.*?(\d+).*?tokens.*?(\d+)",
            r"input.*?(\d+).*?output.*?(\d+)",
            r"[Ii]nput\s*tokens?[:\s]+(\d+).*?[Oo]utput\s*tokens?[:\s]+(\d+)",
            r'"input_tokens"[:\s]+(\d+).*?"output_tokens"[:\s]+(\d+)',
        ],
    ),
    "nemoclaw": AgentInfo(
        agent_type=AgentType.NEMOCLAW,
        display_name="NeMoCLAW",
        cli_command="nemoclaw",
        model_pattern=r"model[:\s]+(\S+)",
        token_patterns=[
            r"tokens.*?(\d+).*?tokens.*?(\d+)",
            r"input.*?(\d+).*?output.*?(\d+)",
        ],
    ),
    "kiro": AgentInfo(
        agent_type=AgentType.KIRO,
        display_name="Kiro",
        cli_command="kiro",
        model_pattern=r"model[:\s]+(\S+)",
        token_patterns=[
            r"tokens.*?(\d+).*?tokens.*?(\d+)",
            r"[Ii]nput\s*tokens?[:\s]+(\d+).*?[Oo]utput\s*tokens?[:\s]+(\d+)",
        ],
    ),
    "auggie": AgentInfo(
        agent_type=AgentType.AUGGIE,
        display_name="Auggie",
        cli_command="auggie",
        model_pattern=r"model[:\s]+(\S+)",
        token_patterns=[
            r"tokens.*?(\d+).*?tokens.*?(\d+)",
            r"[Ii]nput\s*tokens?[:\s]+(\d+).*?[Oo]utput\s*tokens?[:\s]+(\d+)",
        ],
    ),
    "goose": AgentInfo(
        agent_type=AgentType.GOOSE,
        display_name="Goose CLI",
        cli_command="goose",
        model_pattern=r"model[:\s]+(\S+)",
        token_patterns=[
            r"tokens.*?(\d+).*?tokens.*?(\d+)",
            r"[Ii]nput\s*tokens?[:\s]+(\d+).*?[Oo]utput\s*tokens?[:\s]+(\d+)",
        ],
    ),
    "cursor": AgentInfo(
        agent_type=AgentType.CURSOR,
        display_name="Cursor",
        cli_command="cursor",
        model_pattern=r"model[:\s]+(\S+)",
        token_patterns=[
            r"(\d+)\s*tokens?\s*in.*?(\d+).*?tokens?\s*out",
            r"Tokens:\s*(\d+)\s*in.*?(\d+)\s*out",
            r"input[:\s]+(\d+).*?output[:\s]+(\d+)",
            r"[Ii]nput\s*tokens?[:\s]+(\d+).*?[Oo]utput\s*tokens?[:\s]+(\d+)",
            r'"input_tokens"[:\s]+(\d+).*?"output_tokens"[:\s]+(\d+)',
        ],
    ),
}


def detect_agent(args: list[str]) -> Optional[AgentInfo]:
    """Detect which agent CLI is being invoked from command args."""
    if not args:
        return None

    # The first arg should be the agent command
    cmd: str = args[0]

    # Handle paths like /usr/local/bin/claude
    binary: str = cmd.rsplit("/", 1)[-1]

    # Check direct match
    if binary in AGENT_MAP:
        return AGENT_MAP[binary]

    # Check if binary exists and match by name
    resolved: Optional[str] = shutil.which(binary)
    if resolved:
        resolved_name = resolved.rsplit("/", 1)[-1]
        if resolved_name in AGENT_MAP:
            return AGENT_MAP[resolved_name]

    # Check partial matches
    for key, info in AGENT_MAP.items():
        if key in binary:
            return info

    return AgentInfo(
        agent_type=AgentType.GENERIC,
        display_name=binary,
        cli_command=binary,
        model_pattern=r"model[:\s]+(\S+)",
        token_patterns=[
            # Try many formats for generic agents
            r'(\d+)\s*tokens?\s*in.*?(\d+).*?tokens?\s*out',
            r'input[:\s]+(\d+).*?output[:\s]+(\d+)',
            r'[Ii]nput\s*tokens?[:\s]+(\d+).*?[Oo]utput\s*tokens?[:\s]+(\d+)',
            r'"input_tokens"[:\s]+(\d+).*?"output_tokens"[:\s]+(\d+)',
            r'"prompt_tokens"[:\s]+(\d+).*?"completion_tokens"[:\s]+(\d+)',
            r'(\d+)\s*token.*?(\d+)',
            # Additional robust patterns
            r'total\s*tokens?[:\s]+(\d+)\s*,\s*tokens?\s*used[:\s]+(\d+)',
            r'(\d+)\s*token\s*in.*?(\d+)\s*token\s*out',
            r'(\d+)\s*input.*?(\d+)\s*output',
            r'(\d+)\s* consumed.*?(\d+)\s*generated',
            r'\b(\d+)\s*tokens?\s*input\b.*?\b(\d+)\s*tokens?\s*output\b',
            r'input=(\d+).*?output=(\d+)',
            r'tokens_in[:\s]+(\d+).*?tokens_out[:\s]+(\d+)',
            r'(\d+)\s*tokens?\s*\[in\].*?(\d+)\s*tokens?\s*\[out\]',
            r'(\d+)\s*tokens?\s*in,\s*(\d+)\s*tokens?\s*$',
            r'(\d+)\s*tokens?\s*read.*?(\d+)\s*tokens?\s*written',
            # Streaming chunk format
            r'"usage"\s*:\s*\{[^}]*"prompt_tokens"\s*:\s*(\d+)[^}]*"completion_tokens"\s*:\s*(\d+)',
            # Table format: "| Input | Output |" rows
            r'\|\s*(\d+)\s*\|\s*(\d+)\s*\|.*tokens',
            # SSE/data format
            r'"tokens"\s*:\s*\{[^}]*"input"\s*:\s*(\d+)[^}]*"output"\s*:\s*(\d+)',
            # Additional generic patterns
            r'inputTokenCount[\s":]+(\d+).*?outputTokenCount[\s":]+(\d+)',
            r'thinking[_\s]?tokens?[:\s]+(\d+).*?output[_\s]?tokens?[:\s]+(\d+)',
            r'prompt_tokens\s*=\s*(\d+).*?completion_tokens\s*=\s*(\d+)',
            r'(\d+)\s*/\s*(\d+)\s*tokens',
            r'\[\s*(\d+)\s*in\s*\].*?\[\s*(\d+)\s*out\s*\]',
        ],
    )


def parse_tokens(output: str, agent_info: AgentInfo) -> dict[str, int]:
    """Parse token usage from agent output.

    Returns a dict with 'tokens_in' and 'tokens_out' keys,
    or an empty dict if no tokens were found.
    """
    for pattern in agent_info.token_patterns:
        match = re.search(pattern, output, re.IGNORECASE | re.DOTALL)
        if match:
            groups = match.groups()
            if len(groups) >= 2:
                return {
                    "tokens_in": int(groups[0]),
                    "tokens_out": int(groups[1]),
                }
    return {}


def parse_model(output: str, agent_info: AgentInfo) -> Optional[str]:
    """Parse model name from agent output."""
    match = re.search(agent_info.model_pattern, output, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None
