# Tokenizer Protocol + registry shell

Status: pending
Tags: `tokenizers`, `protocol`, `registry`, `architecture`
Depends on: #004
Blocks: #006, #007, #008, #009

## Scope

Define the `Tokenizer` Protocol, `TokenizerInfo` dataclass, registry lookup, and the `TokenizerUnavailable` exception. No real tokenizer is wired yet — that lands in #006 (tiktoken), #007 (HF), #008 (API). Mock adapter is provided in tests so the registry can be exercised without any real backend.

### Files to create

- `src/fertiscope/tokenizers/__init__.py`
- `src/fertiscope/tokenizers/base.py`
- `src/fertiscope/tokenizers/registry.py`
- `src/fertiscope/tokenizers/exceptions.py`
- `tests/unit/test_tokenizers_registry.py`
- `tests/unit/_mock_tokenizer.py`

### Files to modify

- None.

### Interface and contract

`exceptions.py`:

```python
class TokenizerError(Exception):
    """Base class for tokenizer-related errors."""

class TokenizerUnavailable(TokenizerError):
    """Tokenizer is registered but cannot be loaded (missing extra, gating, key)."""
    def __init__(self, tokenizer_id: str, reason: str) -> None:
        self.tokenizer_id = tokenizer_id
        self.reason = reason
        super().__init__(f"Tokenizer '{tokenizer_id}' unavailable: {reason}")

class TokenizerNotFound(TokenizerError):
    """Tokenizer ID is not in the registry."""
```

`base.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable, Literal

Backend = Literal["tiktoken", "hf", "api"]
Family  = Literal["openai", "meta", "google", "mistral", "qwen", "deepseek", "bigscience", "cohere", "anthropic"]

@dataclass(frozen=True)
class TokenizerInfo:
    id: str                           # "openai/o200k_base"
    family: Family
    backend: Backend
    gated: bool = False               # True if HF_TOKEN or API key required
    extra: str | None = None          # "oai" | "hf" | "api"
    notes: str = ""

@runtime_checkable
class Tokenizer(Protocol):
    info: TokenizerInfo
    def encode(self, text: str) -> list[int]: ...
    def count(self, text: str) -> int: ...

class CountOnlyTokenizer(Protocol):
    """For API-backed tokenizers that only expose count_tokens, not raw IDs."""
    info: TokenizerInfo
    def count(self, text: str) -> int: ...
```

`registry.py`:

```python
from __future__ import annotations
from typing import Callable
from .base import Tokenizer, TokenizerInfo
from .exceptions import TokenizerNotFound, TokenizerUnavailable

# Registered: id -> (info, loader_factory)
_REGISTRY: dict[str, tuple[TokenizerInfo, Callable[[], Tokenizer]]] = {}
_CACHE: dict[str, Tokenizer] = {}

def register(info: TokenizerInfo, loader: Callable[[], Tokenizer]) -> None:
    """Register a tokenizer ID with a lazy loader factory."""
    if info.id in _REGISTRY:
        raise ValueError(f"Tokenizer '{info.id}' already registered")
    _REGISTRY[info.id] = (info, loader)

def get_tokenizer(tokenizer_id: str) -> Tokenizer:
    if tokenizer_id not in _REGISTRY:
        raise TokenizerNotFound(f"Unknown tokenizer '{tokenizer_id}'. Use list_tokenizers() to see registered IDs.")
    if tokenizer_id in _CACHE:
        return _CACHE[tokenizer_id]
    info, loader = _REGISTRY[tokenizer_id]
    try:
        tok = loader()
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
    except TokenizerUnavailable:
        return False

def _reset_for_testing() -> None:
    """Test-only hook to clear registry + cache between tests."""
    _REGISTRY.clear()
    _CACHE.clear()
```

`__init__.py`:

```python
from .base import Tokenizer, TokenizerInfo, CountOnlyTokenizer
from .exceptions import TokenizerError, TokenizerUnavailable, TokenizerNotFound
from .registry import register, get_tokenizer, list_tokenizers, is_available

__all__ = [
    "Tokenizer", "TokenizerInfo", "CountOnlyTokenizer",
    "TokenizerError", "TokenizerUnavailable", "TokenizerNotFound",
    "register", "get_tokenizer", "list_tokenizers", "is_available",
]
```

`tests/unit/_mock_tokenizer.py`:

```python
from fertiscope.tokenizers.base import Tokenizer, TokenizerInfo

class MockTokenizer:
    def __init__(self, info: TokenizerInfo, factor: int = 1) -> None:
        self.info = info
        self._factor = factor
    def encode(self, text: str) -> list[int]:
        return list(range(len(text) * self._factor))
    def count(self, text: str) -> int:
        return len(text) * self._factor
```

`tests/unit/test_tokenizers_registry.py` covers:

- Registering two mocks succeeds.
- Double-registering same ID raises `ValueError`.
- `get_tokenizer("unknown")` raises `TokenizerNotFound`.
- A loader factory that raises `ImportError` produces `TokenizerUnavailable` with the extra name in the message.
- `is_available()` returns `False` for that ID, `True` for a working mock.
- `list_tokenizers(available_only=True)` filters correctly.
- `_CACHE` is hit on second call (same Python object identity).
- `_reset_for_testing()` clears state.

### Notes

- The registry is module-global. This is intentional — there is exactly one tokenizer namespace per process. Tests must call `_reset_for_testing()` in setup if they register anything.
- Loaders are lazy — `register()` does NOT call the loader. The first `get_tokenizer(id)` triggers it. This is what lets us register HF tokenizers without `transformers` installed.
- The `@runtime_checkable` Protocol allows `isinstance(tok, Tokenizer)` at runtime, useful for adapter validation.
- `Backend` and `Family` are `Literal` types so `mypy --strict` catches typos in adapter code.

## Acceptance Criteria

- [ ] `from fertiscope.tokenizers import Tokenizer, TokenizerInfo, register, get_tokenizer, list_tokenizers, is_available, TokenizerUnavailable, TokenizerNotFound` works.
- [ ] `list_tokenizers()` returns `[]` on a fresh import (nothing registered yet).
- [ ] All 8 unit tests in `test_tokenizers_registry.py` pass.
- [ ] `isinstance(MockTokenizer(...), Tokenizer)` returns `True`.
- [ ] `get_tokenizer("x")` raising `TokenizerNotFound` includes the suggestion "Use list_tokenizers()".
- [ ] An adapter raising `ImportError("No module named 'tiktoken'")` from its loader is wrapped as `TokenizerUnavailable("openai/...", "missing extra 'oai': ...")`.
- [ ] `_CACHE` cache hit: `get_tokenizer("mock") is get_tokenizer("mock")`.
- [ ] `mypy --strict src/fertiscope/tokenizers/` passes.

## User Stories

### Story: Adapter author writes a new backend in #007

1. Author writes `hf_adapter.py`.
2. Inside its module init, calls `register(TokenizerInfo(id="meta/llama-3.1", ...), _make_llama_loader())`.
3. The loader returns a `HuggingFaceTokenizer` instance.
4. Author's tests use `_reset_for_testing()` then call `register(...)` then `get_tokenizer(...)`.

### Story: User without optional extras

1. User installs `pip install fertiscope` (no extras).
2. The tiktoken adapter module fails to import internally.
3. `list_tokenizers()` still returns the OpenAI rows.
4. `get_tokenizer("openai/o200k_base")` raises `TokenizerUnavailable("openai/o200k_base", "missing extra 'oai': ...")`.
5. User reads the error, runs `pip install fertiscope[oai]`, retries, works.

---

Blocked by: #004
