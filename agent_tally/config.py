"""Unified configuration file support for agent-tally."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


DEFAULT_CONFIG_PATH = Path.home() / ".agent-tally" / "config.yaml"


@dataclass
class AgentTallyConfig:
    """Root configuration for agent-tally."""

    # Default budget settings
    daily_budget: Optional[float] = None
    session_budget: Optional[float] = None

    # Default model to assume when detection fails
    default_model: str = "claude-sonnet-4"

    # Display preferences
    currency: str = "USD"
    timezone: str = "UTC"

    # Webhook for alerts
    webhook_url: Optional[str] = None

    # Budget thresholds
    warn_at_80: bool = True
    warn_at_95: bool = True
    kill_at_100: bool = True

    # Custom model pricing overrides (model_name -> {input, output})
    model_pricing: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Ignored agents (won't track these)
    ignored_agents: list[str] = field(default_factory=list)


def load_config(config_path: Optional[Path] = None) -> AgentTallyConfig:
    """Load configuration from YAML file, returning defaults if missing."""
    path = config_path or DEFAULT_CONFIG_PATH

    if not path.exists():
        return AgentTallyConfig()

    try:
        with open(path) as f:
            data: Dict[str, Any] = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return AgentTallyConfig()

    return AgentTallyConfig(
        daily_budget=data.get("daily_budget"),
        session_budget=data.get("session_budget"),
        default_model=data.get("default_model", "claude-sonnet-4"),
        currency=data.get("currency", "USD"),
        timezone=data.get("timezone", "UTC"),
        webhook_url=data.get("webhook_url"),
        warn_at_80=data.get("warn_at_80", True),
        warn_at_95=data.get("warn_at_95", True),
        kill_at_100=data.get("kill_at_100", True),
        model_pricing=data.get("model_pricing", {}),
        ignored_agents=data.get("ignored_agents", []),
    )


def save_config(config: AgentTallyConfig, config_path: Optional[Path] = None) -> None:
    """Save configuration to YAML file."""
    path = config_path or DEFAULT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    data: Dict[str, Any] = {
        "daily_budget": config.daily_budget,
        "session_budget": config.session_budget,
        "default_model": config.default_model,
        "currency": config.currency,
        "timezone": config.timezone,
        "warn_at_80": config.warn_at_80,
        "warn_at_95": config.warn_at_95,
        "kill_at_100": config.kill_at_100,
    }

    if config.webhook_url:
        data["webhook_url"] = config.webhook_url
    if config.model_pricing:
        data["model_pricing"] = config.model_pricing
    if config.ignored_agents:
        data["ignored_agents"] = config.ignored_agents

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def generate_default_config(config_path: Optional[Path] = None) -> str:
    """Generate a sample config file with comments."""
    content = """# agent-tally configuration
# Place at ~/.agent-tally/config.yaml

# Default budget limits (USD)
# daily_budget: 10.0
# session_budget: 2.0

# Default model when detection fails
# default_model: claude-sonnet-4

# Currency for display
# currency: USD

# Timezone for timestamps
# timezone: UTC

# Budget thresholds
# warn_at_80: true
# warn_at_95: true
# kill_at_100: true

# Webhook URL for alerts (Discord/Slack)
# webhook_url: https://discord.com/api/webhooks/...

# Custom model pricing (per million tokens)
# model_pricing:
#   my-custom-model:
#     input: 1.00
#     output: 5.00

# Agents to ignore (won't track)
# ignored_agents:
#   - some-tool
"""
    return content
