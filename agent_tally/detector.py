"""Agent detection and command parsing."""

from __future__ import annotations
import re
import shutil
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AgentType(Enum):
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
            r"(\d+)\s*tokens?\s*in.*?(\d+).*?tokens?\s*out.*?(\d+)",
            r"input[:\s]+(\d+).*?output[:\s]+(\d+)",
            r"Tokens:\s*(\d+)\s*in.*?(\d+)\s*out",
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
        ],
    ),
    "nemoclaw": AgentInfo(
        agent_type=AgentType.NEMOCLAW,
        display_name="NeMoCLAW",
        cli_command="nemoclaw",
        model_pattern=r"model[:\s]+(\S+)",
        token_patterns=[
            r"tokens.*?(\d+).*?tokens.*?(\d+)",
        ],
    ),
    "kiro": AgentInfo(
        agent_type=AgentType.KIRO,
        display_name="Kiro",
        cli_command="kiro",
        model_pattern=r"model[:\s]+(\S+)",
        token_patterns=[
            r"tokens.*?(\d+).*?tokens.*?(\d+)",
        ],
    ),
    "auggie": AgentInfo(
        agent_type=AgentType.AUGGIE,
        display_name="Auggie",
        cli_command="auggie",
        model_pattern=r"model[:\s]+(\S+)",
        token_patterns=[
            r"tokens.*?(\d+).*?tokens.*?(\d+)",
        ],
    ),
    "goose": AgentInfo(
        agent_type=AgentType.GOOSE,
        display_name="Goose CLI",
        cli_command="goose",
        model_pattern=r"model[:\s]+(\S+)",
        token_patterns=[
            r"tokens.*?(\d+).*?tokens.*?(\d+)",
        ],
    ),
}


def detect_agent(args: list[str]) -> Optional[AgentInfo]:
    """Detect which agent CLI is being invoked from command args."""
    if not args:
        return None

    # The first arg should be the the agent command
    cmd = args[0]

    # Handle paths like /usr/local/bin/claude
    binary = cmd.rsplit("/", 1)[-1]

    # Check direct match
    if binary in AGENT_MAP:
        return AGENT_MAP[binary]

    # Check if binary exists and match by name
    resolved = shutil.which(binary)
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
        token_patterns=[r"(\d+)\s*token.*?(\d+)", r"input[:\s]+(\d+).*?output[:\s]+(\d+)"],
    )


def parse_tokens(output: str, agent_info: AgentInfo) -> dict:
    """Parse token usage from agent output."""
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
