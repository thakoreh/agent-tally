"""agent-tally — track costs across every AI coding agent in real-time."""

__version__ = "0.8.0"

from .budget import BudgetManager, BudgetConfig, BudgetStatus
from .config import AgentTallyConfig, load_config, save_config
from .ticker import CostTicker, IncrementalCostTracker
from .notifier import Notifier, Alert
from .dashboard import Dashboard
from .storage import Storage, Session
from .pricing import PricingConfig, detect_provider
from .detector import detect_agent, parse_tokens, parse_model

__all__ = [
    "BudgetManager",
    "BudgetConfig",
    "BudgetStatus",
    "AgentTallyConfig",
    "load_config",
    "save_config",
    "CostTicker",
    "IncrementalCostTracker",
    "Notifier",
    "Alert",
    "Dashboard",
    "Storage",
    "Session",
    "PricingConfig",
    "detect_provider",
    "detect_agent",
    "parse_tokens",
    "parse_model",
]
