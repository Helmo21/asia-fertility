"""OpenRouter async provider with retry."""
from __future__ import annotations

import asyncio
import os

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class ChatError(Exception):
    """Non-retryable provider error."""


class RetryableError(Exception):
    """Retryable provider error (429, 5xx)."""


def _retryable(status: int) -> bool:
    return status == 429 or 500 <= status < 600


class OpenRouterProvider:
    """OpenRouter chat-completions backend with exponential-backoff retries."""

    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
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
                "HTTP-Referer": "https://github.com/Helmo21/asia-fertility",
                "X-Title": "asia-fertility NIAH",
            },
            timeout=timeout,
        )
        self._sem = asyncio.Semaphore(max_concurrency)

    async def chat(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 200,
        temperature: float = 0.0,
    ) -> str:
        async with self._sem:
            return await self._chat_with_retry(model, messages, max_tokens, temperature)

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(RetryableError),
        reraise=True,
    )
    async def _chat_with_retry(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> str:
        try:
            resp = await self._client.post(
                "/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
        except httpx.TransportError as e:
            raise RetryableError(f"transport: {e}") from e

        if _retryable(resp.status_code):
            raise RetryableError(f"{resp.status_code}: {resp.text[:200]}")
        if resp.status_code >= 400:
            raise ChatError(f"{resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise ChatError(f"unexpected response shape: {data}") from e

    async def aclose(self) -> None:
        await self._client.aclose()
