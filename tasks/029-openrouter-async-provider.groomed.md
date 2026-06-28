# OpenRouter async provider with retries

Status: pending
Tags: `niah`, `openrouter`, `async`, `httpx`, `tenacity`, `retries`
Depends on: #002 (httpx, tenacity in [niah] extra)
Blocks: #030

## Scope

The HTTP backend for the NIAH runner: async OpenRouter chat completions with exponential-backoff retries on 429/5xx, fast-fail on 4xx (non-429), and concurrency control. Mocked exclusively in tests (no real API calls in CI).

### Files to create

- `src/fertiscope/niah/providers.py`
- `tests/unit/test_niah_providers.py`

### Files to modify

- None.

### Interface and contract

`src/fertiscope/niah/providers.py`:

```python
"""Async API providers for NIAH chat completions.

Currently: OpenRouter (one backend covers 100+ models).
Future: direct Anthropic + Gemini if needed for redundancy.

All providers expose `async def chat(model, messages, max_tokens) -> str`.
"""
from __future__ import annotations
import os
from typing import Protocol
import httpx
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, RetryError,
)


class ChatProvider(Protocol):
    async def chat(self, model: str, messages: list[dict], max_tokens: int = 200) -> str: ...
    async def aclose(self) -> None: ...


class ChatError(Exception):
    """Non-retryable provider error."""


class RetryableError(Exception):
    """Retryable provider error (429, 5xx)."""


def _is_retryable_status(status: int) -> bool:
    return status == 429 or 500 <= status < 600


class OpenRouterProvider:
    """OpenRouter chat-completions backend.

    - Requires OPENROUTER_API_KEY.
    - Retries on 429/5xx with exponential backoff (4 attempts, 1s → 8s).
    - Fast-fail on other 4xx.
    """

    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_concurrency: int = 4,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ChatError("OPENROUTER_API_KEY not set")
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://fertiscope.vercel.app",
                "X-Title": "FertiScope NIAH",
            },
            timeout=timeout,
        )
        import asyncio
        self._sem = asyncio.Semaphore(max_concurrency)

    async def chat(self, model: str, messages: list[dict], max_tokens: int = 200) -> str:
        async with self._sem:
            return await self._chat_with_retry(model, messages, max_tokens)

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(RetryableError),
        reraise=True,
    )
    async def _chat_with_retry(self, model: str, messages: list[dict], max_tokens: int) -> str:
        try:
            resp = await self._client.post(
                "/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.0,
                },
            )
        except httpx.TransportError as e:
            raise RetryableError(f"transport: {e}") from e

        if _is_retryable_status(resp.status_code):
            raise RetryableError(f"{resp.status_code}: {resp.text[:200]}")
        if resp.status_code >= 400:
            raise ChatError(f"{resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise ChatError(f"unexpected response shape: {data}") from e

    async def aclose(self) -> None:
        await self._client.aclose()
```

`tests/unit/test_niah_providers.py`:

```python
import pytest
import respx
import httpx
from fertiscope.niah.providers import OpenRouterProvider, ChatError, RetryableError


@pytest.mark.asyncio
async def test_chat_success(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    with respx.mock(base_url="https://openrouter.ai/api/v1") as mock:
        mock.post("/chat/completions").mock(return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": "hello back"}}]}
        ))
        p = OpenRouterProvider()
        out = await p.chat("openai/gpt-4o-mini", [{"role": "user", "content": "hi"}])
        await p.aclose()
        assert out == "hello back"


@pytest.mark.asyncio
async def test_chat_retries_on_429(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    with respx.mock(base_url="https://openrouter.ai/api/v1") as mock:
        route = mock.post("/chat/completions").mock(side_effect=[
            httpx.Response(429, json={"error": "rate limited"}),
            httpx.Response(429, json={"error": "rate limited"}),
            httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}),
        ])
        p = OpenRouterProvider()
        out = await p.chat("foo", [{"role": "user", "content": "x"}])
        await p.aclose()
        assert out == "ok"
        assert route.call_count == 3


@pytest.mark.asyncio
async def test_chat_fails_after_4_attempts(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    with respx.mock(base_url="https://openrouter.ai/api/v1") as mock:
        mock.post("/chat/completions").mock(return_value=httpx.Response(500, text="boom"))
        p = OpenRouterProvider()
        with pytest.raises(RetryableError):
            await p.chat("foo", [{"role": "user", "content": "x"}])
        await p.aclose()


@pytest.mark.asyncio
async def test_chat_no_retry_on_400(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    with respx.mock(base_url="https://openrouter.ai/api/v1") as mock:
        route = mock.post("/chat/completions").mock(return_value=httpx.Response(400, text="bad model"))
        p = OpenRouterProvider()
        with pytest.raises(ChatError, match="400"):
            await p.chat("nonexistent", [{"role": "user", "content": "x"}])
        await p.aclose()
        assert route.call_count == 1     # no retry


@pytest.mark.asyncio
async def test_concurrency_limit(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    import asyncio, time
    with respx.mock(base_url="https://openrouter.ai/api/v1") as mock:
        async def slow_response(request):
            await asyncio.sleep(0.05)
            return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})
        mock.post("/chat/completions").mock(side_effect=slow_response)
        p = OpenRouterProvider(max_concurrency=2)
        t0 = time.time()
        await asyncio.gather(*[p.chat("m", [{"role": "user", "content": "y"}]) for _ in range(4)])
        elapsed = time.time() - t0
        await p.aclose()
        # 4 calls, 2 at a time, each 50ms → ~0.1s
        assert elapsed >= 0.09


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ChatError, match="OPENROUTER_API_KEY"):
        OpenRouterProvider()
```

### Notes

- **`temperature=0.0`** for NIAH — we want deterministic recall behavior. Document.
- The `HTTP-Referer` and `X-Title` headers are OpenRouter best practice (helps with their model routing analytics).
- 4 retries with 1s → 8s backoff totals up to ~15s before giving up. For the 2880-call benchmark, even modest 429 rates won't blow up runtime.
- `respx` is the standard httpx mock — must be in `[dev]` extras.
- The `aclose()` pattern requires every caller to use `async with` or remember to close — the runner (#030) wraps both.
- For Anthropic / Gemini DIRECT (not via OpenRouter) — that's a future task. v0.2 OpenRouter-only is sufficient since OpenRouter proxies both.

## Acceptance Criteria

- [ ] `OpenRouterProvider()` raises `ChatError` if `OPENROUTER_API_KEY` is unset.
- [ ] `await p.chat(...)` returns the assistant message text on 200.
- [ ] Retries up to 4 times on 429.
- [ ] Retries up to 4 times on 5xx.
- [ ] Does NOT retry on 400 / 401 / 403 / 404.
- [ ] Raises `ChatError` on persistent 4xx.
- [ ] Raises `RetryableError` after 4 failed retries.
- [ ] `max_concurrency` limits parallel requests.
- [ ] All 6 tests pass with mocked HTTP (`respx`).
- [ ] No real network calls in CI.
- [ ] `mypy --strict src/fertiscope/niah/providers.py` passes.

## User Stories

### Story: Runner makes 2880 calls without blowing the rate limit

1. Sets `max_concurrency=4`.
2. Runner kicks off 2880 calls.
3. OpenRouter throttles → 429s appear.
4. Provider auto-retries with backoff.
5. Run completes; no manual intervention.

### Story: Bad model name fails fast

1. User typos `--model openai/gpt-4-wrong`.
2. First call returns 400.
3. Provider raises `ChatError("400: model not found")`.
4. No wasted retries.

### Story: CI runs offline

1. CI has no `OPENROUTER_API_KEY`.
2. Unit tests use `respx` mocks, never touch real API.
3. Tests pass, no charges.

---

Blocked by: #002
