"""Tests for the latency streaming provider — mocked OpenRouter SSE responses."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from asia_fertility.latency.runner import _StreamingProvider
from asia_fertility.niah.providers import ChatError, RetryableError


def _sse_response(chunks: list[str]) -> httpx.Response:
    """Build a fake SSE response body from a list of text chunks.

    Real OpenRouter SSE uses `data: <json>\n\n` event framing — two newlines
    between events. Use json.dumps for valid JSON (repr emits single quotes).
    """
    parts = []
    for c in chunks:
        payload = json.dumps({"choices": [{"delta": {"content": c}}]})
        parts.append(f"data: {payload}\n\n")
    parts.append("data: [DONE]\n\n")
    return httpx.Response(200, text="".join(parts), headers={"content-type": "text/event-stream"})


@pytest.mark.asyncio
async def test_stream_basic(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    with respx.mock(base_url="https://openrouter.ai/api/v1") as mock:
        mock.post("/chat/completions").mock(return_value=_sse_response(["hello", " world"]))
        p = _StreamingProvider(max_concurrency=1)
        ttft, total, text = await p.chat_with_timing("openai/gpt-4o-mini", "hi", max_tokens=20)
        await p.aclose()
        assert text == "hello world"
        assert ttft > 0
        assert total >= ttft


@pytest.mark.asyncio
async def test_stream_4xx_fast_fail(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    with respx.mock(base_url="https://openrouter.ai/api/v1") as mock:
        mock.post("/chat/completions").mock(return_value=httpx.Response(400, text="bad model"))
        p = _StreamingProvider(max_concurrency=1)
        with pytest.raises(ChatError, match="400"):
            await p.chat_with_timing("nonexistent", "hi")
        await p.aclose()


@pytest.mark.asyncio
async def test_stream_5xx_retries(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    with respx.mock(base_url="https://openrouter.ai/api/v1") as mock:
        route = mock.post("/chat/completions").mock(
            side_effect=[
                httpx.Response(503, text="upstream down"),
                httpx.Response(503, text="still down"),
                _sse_response(["recovered"]),
            ]
        )
        p = _StreamingProvider(max_concurrency=1)
        _, _, text = await p.chat_with_timing("openai/gpt-4o-mini", "hi")
        await p.aclose()
        assert text == "recovered"
        assert route.call_count == 3


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ChatError, match="OPENROUTER_API_KEY"):
        _StreamingProvider()


@pytest.mark.asyncio
async def test_persistent_5xx_eventually_raises(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    with respx.mock(base_url="https://openrouter.ai/api/v1") as mock:
        mock.post("/chat/completions").mock(return_value=httpx.Response(503, text="boom"))
        p = _StreamingProvider(max_concurrency=1)
        with pytest.raises(RetryableError):
            await p.chat_with_timing("openai/gpt-4o-mini", "hi")
        await p.aclose()
