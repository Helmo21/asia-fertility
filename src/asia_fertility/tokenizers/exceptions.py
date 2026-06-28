"""Tokenizer-related exceptions."""
from __future__ import annotations


class TokenizerError(Exception):
    """Base class for tokenizer errors."""


class TokenizerUnavailable(TokenizerError):
    """Tokenizer is registered but cannot be loaded (missing extra, gating, key)."""

    def __init__(self, tokenizer_id: str, reason: str) -> None:
        self.tokenizer_id = tokenizer_id
        self.reason = reason
        super().__init__(f"Tokenizer '{tokenizer_id}' unavailable: {reason}")


class TokenizerNotFound(TokenizerError):
    """Tokenizer ID is not in the registry."""
