# API count-only adapter (Anthropic + Gemini)

Status: pending
Tags: `tokenizers`, `anthropic`, `gemini`, `count-tokens`, `api`
Depends on: #005
Blocks: #009, #019

## Scope

Wrap the `count_tokens` endpoints of Anthropic and Google so closed-weight models can appear in the leaderboard alongside open ones. Adapters are **count-only**: they return integer token counts but cannot return raw IDs. No real generation calls are ever made — only the free count_tokens endpoints.

### Files to create

- `src/fertiscope/tokenizers/api_adapter.py`
- `tests/unit/test_api_adapter.py`

### Files to modify

- `src/fertiscope/tokenizers/__init__.py` — register `anthropic/claude` and `google/gemini` rows.

### Interface and contract

`api_adapter.py`:

```python
from __future__ import annotations
import os
from .base import TokenizerInfo, CountOnlyTokenizer, Tokenizer
from .registry import register
from .exceptions import TokenizerUnavailable


class AnthropicCountTokenizer:
    """Count-only — Anthropic API does not expose token IDs."""

    def __init__(self, info: TokenizerInfo, model: str) -> None:
        self.info = info
        self._model = model
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise TokenizerUnavailable(info.id, "ANTHROPIC_API_KEY not set")
        try:
            from anthropic import Anthropic       # type: ignore
        except ImportError as e:
            raise TokenizerUnavailable(info.id, f"missing extra 'api': {e}") from e
        self._client = Anthropic(api_key=key)

    def encode(self, text: str) -> list[int]:
        raise NotImplementedError(
            "Anthropic API is count-only — token IDs are not returned. "
            "Use .count(text) instead."
        )

    def count(self, text: str) -> int:
        r = self._client.messages.count_tokens(
            model=self._model,
            messages=[{"role": "user", "content": text}],
        )
        return int(r.input_tokens)


class GeminiCountTokenizer:
    """Count-only — Gemini API does not expose token IDs."""

    def __init__(self, info: TokenizerInfo, model: str) -> None:
        self.info = info
        self._model = model
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise TokenizerUnavailable(info.id, "GEMINI_API_KEY (or GOOGLE_API_KEY) not set")
        try:
            from google import genai             # type: ignore
        except ImportError as e:
            raise TokenizerUnavailable(info.id, f"missing extra 'api': {e}") from e
        self._client = genai.Client(api_key=key)

    def encode(self, text: str) -> list[int]:
        raise NotImplementedError(
            "Gemini API is count-only — token IDs are not returned. "
            "Use .count(text) instead."
        )

    def count(self, text: str) -> int:
        r = self._client.models.count_tokens(model=self._model, contents=text)
        return int(r.total_tokens)


_API_TOKENIZERS = {
    "anthropic/claude": ("claude-opus-4-7", "anthropic"),
    "google/gemini":    ("gemini-2.5-pro", "google"),
}


def register_all() -> None:
    for tid, (model, family) in _API_TOKENIZERS.items():
        info = TokenizerInfo(
            id=tid,
            family=family,                       # type: ignore[arg-type]
            backend="api",
            gated=True,
            extra="api",
            notes=f"count-only; model={model}",
        )
        cls = AnthropicCountTokenizer if family == "anthropic" else GeminiCountTokenizer
        def _make(info=info, model=model, cls=cls):
            def _load() -> Tokenizer:
                return cls(info, model)
            return _load
        register(info, _make())


register_all()
```

`tests/unit/test_api_adapter.py` covers:

- Both IDs appear in `list_tokenizers()` regardless of env or extras.
- Both have `backend == "api"`, `gated == True`, `extra == "api"`.
- With no API keys: `get_tokenizer("anthropic/claude")` raises `TokenizerUnavailable("anthropic/claude", "ANTHROPIC_API_KEY not set")`.
- With API key set but `anthropic` not installed (simulated): raises `TokenizerUnavailable` mentioning extra `'api'`.
- With mocked `Anthropic` client: `.count("hello")` returns the mocked integer.
- `.encode()` raises `NotImplementedError` with a helpful message.
- Gemini `GEMINI_API_KEY` and `GOOGLE_API_KEY` are both accepted (test both).

Mock pattern (using `monkeypatch` to swap out `anthropic.Anthropic`):

```python
def test_anthropic_count(monkeypatch):
    fake = type("FakeClient", (), {"messages": type("FakeMessages", (), {
        "count_tokens": staticmethod(lambda **kw: type("R", (), {"input_tokens": 42})())
    })()})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setattr("anthropic.Anthropic", lambda **kw: fake)
    tok = get_tokenizer("anthropic/claude")
    assert tok.count("hello") == 42
```

### Notes

- **Anthropic `count_tokens` is free** and returns input token count for the specified model. It does NOT consume any quota beyond a small rate limit. Document in `docs/methodology.md`.
- **Gemini `countTokens`** is similarly free.
- Both adapters are **count-only**: `encode()` raises `NotImplementedError`. The study runner (#024) must handle this — for API-backed rows, it sets `tokens_sum = sum(.count(s) for s in sentences)` but reports `bpt = NaN` because BPT requires per-sentence byte/token alignment that's still computable (BPT = total_bytes / total_tokens, both summed independently).
- BPT is still computable for count-only tokenizers — it's just `sum(bytes) / sum(count(s))`. So count-only does NOT lock you out of BPT.
- **Do not register the same model under multiple Anthropic/Gemini IDs**. Use the latest production model (`claude-opus-4-7`, `gemini-2.5-pro`). When new models ship, swap the `model` constant — token boundaries are stable for the families.
- **Cost**: ~$0/run, but rate limits exist. Document in NIAH task (#030) for the case where someone tries to bulk-tokenize 10,000 sentences via API.

## Acceptance Criteria

- [ ] `list_tokenizers()` includes `anthropic/claude` and `google/gemini` regardless of env.
- [ ] Both have `gated == True`, `backend == "api"`, `extra == "api"`.
- [ ] `get_tokenizer("anthropic/claude")` without `ANTHROPIC_API_KEY` raises `TokenizerUnavailable` with reason "ANTHROPIC_API_KEY not set".
- [ ] `get_tokenizer("google/gemini")` accepts either `GEMINI_API_KEY` or `GOOGLE_API_KEY`.
- [ ] With mocked Anthropic client: `.count("test")` returns mocked integer.
- [ ] `.encode("test")` raises `NotImplementedError` for both adapters.
- [ ] All 7 unit tests in `test_api_adapter.py` pass.
- [ ] No real API calls in CI (verified by `respx`/monkeypatch coverage).
- [ ] `mypy --strict src/fertiscope/tokenizers/api_adapter.py` passes.

## User Stories

### Story: Researcher compares Claude vs GPT-4o on Tamil

1. Sets `ANTHROPIC_API_KEY`.
2. Runs `fertiscope measure --text "<tamil>" --lang tam --tokenizer anthropic/claude`.
3. Sees Claude's count (call hits Anthropic's free count_tokens endpoint).
4. Compares with `--tokenizer openai/o200k_base`.
5. Decision: Claude tokenizer is X% better/worse for Tamil.

### Story: User attempts to read raw IDs

1. Calls `get_tokenizer("anthropic/claude").encode("hello")`.
2. `NotImplementedError`: "Anthropic API is count-only — use .count(text)".
3. Switches to `openai/o200k_base` if they need IDs.

### Story: CI without keys

1. CI has no API keys.
2. `fertiscope tokenizers list` shows API rows as `unavailable: ANTHROPIC_API_KEY not set`.
3. No test failure, no surprise charges.

---

Blocked by: #005
