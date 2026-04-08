"""Pricing configuration for AI models."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


DEFAULT_CONFIG_DIR = Path.home() / ".agent-tally"
DEFAULT_PRICING_FILE = DEFAULT_CONFIG_DIR / "pricing.yaml"
DEFAULT_DB_PATH = DEFAULT_CONFIG_DIR / "db.sqlite"


class ModelPricing:
    """Pricing for a single model (per million tokens)."""

    def __init__(self, name: str, input: float = 0.0, output: float = 0.0) -> None:
        self.name = name
        self.input = input
        self.output = output

    def cost(self, tokens_in: int, tokens_out: int) -> float:
        """Calculate cost for given token usage."""
        return (tokens_in / 1_000_000 * self.input) + (tokens_out / 1_000_000 * self.output)


# Default pricing for known models (per million tokens, USD)
DEFAULT_PRICING: dict[str, dict[str, float]] = {
    # ── Anthropic ──────────────────────────────────────────────
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "claude-opus-4": {"input": 15.00, "output": 75.00},
    "claude-haiku-3.5": {"input": 0.80, "output": 4.00},
    "claude-code": {"input": 3.00, "output": 15.00},
    "claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3.5-haiku": {"input": 0.80, "output": 4.00},
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    # ── OpenAI ─────────────────────────────────────────────────
    "gpt-5.2-codex": {"input": 2.50, "output": 10.00},
    "gpt-5.4": {"input": 2.50, "output": 10.00},
    "gpt-5.4-thinking": {"input": 5.00, "output": 20.00},
    "o3-mini": {"input": 1.10, "output": 4.40},
    "o3": {"input": 2.50, "output": 10.00},
    "o4-mini": {"input": 1.10, "output": 4.40},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    # ── Google ─────────────────────────────────────────────────
    "gemini-3.1-flash": {"input": 0.15, "output": 0.60},
    "gemini-3.1-pro": {"input": 1.25, "output": 10.00},
    "gemini-3.1-ultra": {"input": 2.50, "output": 15.00},
    "gemini-3.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    # ── xAI ───────────────────────────────────────────────────
    "grok-4.20": {"input": 3.00, "output": 15.00},
    "grok-3": {"input": 0.50, "output": 2.00},
    "grok-3-mini": {"input": 0.30, "output": 1.00},
    "grok-2": {"input": 2.00, "output": 10.00},
    # ── DeepSeek ───────────────────────────────────────────────
    "deepseek-v4": {"input": 0.27, "output": 1.10},
    "deepseek-v4-reasoning": {"input": 0.55, "output": 2.19},
    "deepseek-v3": {"input": 0.27, "output": 1.10},
    "deepseek-r1": {"input": 0.55, "output": 2.19},
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    # ── Meta ───────────────────────────────────────────────────
    "llama-4-maverick": {"input": 0.20, "output": 0.80},
    "llama-4-scout": {"input": 0.10, "output": 0.40},
    "llama-3.3-70b": {"input": 0.20, "output": 0.80},
    # ── Mistral ────────────────────────────────────────────────
    "mistral-large": {"input": 2.00, "output": 6.00},
    "mistral-medium": {"input": 0.40, "output": 1.50},
    "mistral-small": {"input": 0.20, "output": 0.60},
    "codestral": {"input": 0.30, "output": 0.90},
    # ── Cohere ─────────────────────────────────────────────────
    "command-r-plus": {"input": 2.50, "output": 10.00},
    "command-r": {"input": 0.50, "output": 1.50},
    # ── Open source / Chinese providers ────────────────────────
    "glm-5": {"input": 0.10, "output": 0.40},
    "glm-4": {"input": 0.10, "output": 0.40},
    "glm-5.1": {"input": 0.10, "output": 0.40},
    "qwen-3": {"input": 0.15, "output": 0.60},
    "qwen-2.5-coder": {"input": 0.15, "output": 0.60},
    "qwen-3-max": {"input": 0.40, "output": 1.20},
    "qwen-3-plus": {"input": 0.20, "output": 0.60},
    "yi-large": {"input": 0.30, "output": 0.90},
    "dbrx-instruct": {"input": 0.25, "output": 0.50},
    "mixtral-8x7b": {"input": 0.15, "output": 0.30},
    "llama-3.1-8b": {"input": 0.05, "output": 0.15},
    "llama-3.1-70b": {"input": 0.20, "output": 0.80},
    # ── Cursor ─────────────────────────────────────────────────
    "cursor-small": {"input": 0.15, "output": 0.60},
    "cursor-pro": {"input": 3.00, "output": 15.00},
}


class PricingConfig:
    """Manages model pricing configuration."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.config_path: Path = config_path or DEFAULT_PRICING_FILE
        self._models: dict[str, ModelPricing] = {}
        self._load()

    def _load(self) -> None:
        """Load pricing from config file, falling back to defaults."""
        # Start with defaults
        self._models = {
            name: ModelPricing(name=name, **prices)
            for name, prices in DEFAULT_PRICING.items()
        }

        # Override with user config if exists
        if self.config_path.exists():
            with open(self.config_path) as f:
                user_config: dict = yaml.safe_load(f) or {}

            if user_config and "models" in user_config:
                for name, prices in user_config["models"].items():
                    self._models[name] = ModelPricing(
                        name=name,
                        input=prices.get("input", 0.0),
                        output=prices.get("output", 0.0),
                    )

    def get(self, model_name: str) -> ModelPricing:
        """Get pricing for a model, with fuzzy matching."""
        # Exact match
        if model_name in self._models:
            return self._models[model_name]

        # Fuzzy: strip version suffixes, prefixes
        normalized = model_name.lower().strip()
        for key, pricing in self._models.items():
            if key in normalized or normalized in key:
                return pricing

        # Default: return unknown model pricing
        return ModelPricing(name=model_name)

    def set(self, model_name: str, input_price: float, output_price: float) -> None:
        """Set pricing for a model."""
        self._models[model_name] = ModelPricing(
            name=model_name,
            input=input_price,
            output=output_price,
        )
        self._save()

    def _save(self) -> None:
        """Save current config to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            yaml.dump(
                {
                    "models": {
                        name: {"input": p.input, "output": p.output}
                        for name, p in self._models.items()
                    }
                },
                f,
                default_flow_style=False,
            )

    def all_models(self) -> dict[str, ModelPricing]:
        """Return all configured models."""
        return dict(self._models)

    def estimate(self, model_name: str, tokens_in: int, tokens_out: int) -> float:
        """Estimate cost for given model and token usage."""
        return self.get(model_name).cost(tokens_in, tokens_out)
