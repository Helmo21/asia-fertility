"""Multi-turn needle-in-haystack benchmark."""

from __future__ import annotations

from .haystack import Haystack, build_haystack
from .markers import SCRIPT_MARKERS, get_marker, supported_scripts
from .providers import ChatError, OpenRouterProvider, RetryableError
from .runner import NIAHConfig, NIAHRow, estimate_cost_usd, run_niah
from .scoring import recall_score

__all__ = [
    "SCRIPT_MARKERS",
    "ChatError",
    "Haystack",
    "NIAHConfig",
    "NIAHRow",
    "OpenRouterProvider",
    "RetryableError",
    "build_haystack",
    "estimate_cost_usd",
    "get_marker",
    "recall_score",
    "run_niah",
    "supported_scripts",
]
