"""agent-tally — track costs across every AI coding agent in real-time."""

__version__ = "0.2.0"

from .budget import BudgetManager, BudgetConfig, BudgetStatus
from .ticker import CostTicker, IncrementalCostTracker
from .notifier import Notifier, Alert
from .dashboard import Dashboard
from .storage import Storage, Session
from .pricing import PricingConfig
from .detector import detect_agent, parse_tokens, parse_model

__all__ = [
    "BudgetManager",
    "BudgetConfig",
    "BudgetStatus",
    "CostTicker",
    "IncrementalCostTracker",
    "Notifier",
    "Alert",
    "Dashboard",
    "Storage",
    "Session",
    "PricingConfig",
    "detect_agent",
    "parse_tokens",
    "parse_model",
]
