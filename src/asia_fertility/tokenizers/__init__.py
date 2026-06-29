"""Tokenizer registry + adapter protocol.

The registry pattern: every tokenizer is registered with its TokenizerInfo and
a lazy loader factory. Importing this module triggers registration of all
known tokenizers (tiktoken via #006, HuggingFace via #007, API count-only via #008).
"""

from __future__ import annotations

# Side-effect imports: register adapters
from . import tiktoken_adapter as _tiktoken_adapter  # noqa: F401
from .base import CountOnlyTokenizer, Tokenizer, TokenizerInfo
from .exceptions import TokenizerError, TokenizerNotFound, TokenizerUnavailable
from .registry import get_tokenizer, is_available, list_tokenizers, register

try:
    from . import hf_adapter as _hf_adapter  # noqa: F401
except ImportError:
    # Without [hf] extra, register placeholder rows so list still shows them
    from . import hf_stub as _hf_stub  # noqa: F401

try:
    from . import api_adapter as _api_adapter  # noqa: F401
except ImportError:
    from . import api_stub as _api_stub  # noqa: F401

__all__ = [
    "CountOnlyTokenizer",
    "Tokenizer",
    "TokenizerError",
    "TokenizerInfo",
    "TokenizerNotFound",
    "TokenizerUnavailable",
    "get_tokenizer",
    "is_available",
    "list_tokenizers",
    "register",
]
