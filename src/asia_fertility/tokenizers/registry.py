"""Central tokenizer registry + lazy loader."""
from __future__ import annotations

from typing import Callable

from .base import Tokenizer, TokenizerInfo
from .exceptions import TokenizerNotFound, TokenizerUnavailable

_REGISTRY: dict[str, tuple[TokenizerInfo, Callable[[], Tokenizer]]] = {}
_CACHE: dict[str, Tokenizer] = {}


def register(info: TokenizerInfo, loader: Callable[[], Tokenizer]) -> None:
    """Register a tokenizer ID with a lazy loader factory."""
    if info.id in _REGISTRY:
        raise ValueError(f"Tokenizer '{info.id}' already registered")
    _REGISTRY[info.id] = (info, loader)


def get_tokenizer(tokenizer_id: str) -> Tokenizer:
    if tokenizer_id not in _REGISTRY:
        raise TokenizerNotFound(
            f"Unknown tokenizer '{tokenizer_id}'. Use list_tokenizers() to see registered IDs."
        )
    if tokenizer_id in _CACHE:
        return _CACHE[tokenizer_id]
    info, loader = _REGISTRY[tokenizer_id]
    try:
        tok = loader()
    except TokenizerUnavailable:
        raise
    except ImportError as e:
        raise TokenizerUnavailable(tokenizer_id, f"missing extra '{info.extra}': {e}") from e
    _CACHE[tokenizer_id] = tok
    return tok


def list_tokenizers(available_only: bool = False) -> list[TokenizerInfo]:
    rows = [info for info, _ in _REGISTRY.values()]
    rows.sort(key=lambda i: (i.family, i.id))
    if available_only:
        rows = [r for r in rows if is_available(r.id)]
    return rows


def is_available(tokenizer_id: str) -> bool:
    try:
        get_tokenizer(tokenizer_id)
        return True
    except (TokenizerUnavailable, TokenizerNotFound):
        return False


def _reset_for_testing() -> None:
    """Test-only hook to clear registry + cache between tests."""
    _REGISTRY.clear()
    _CACHE.clear()
