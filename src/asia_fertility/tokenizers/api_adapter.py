"""API count-only adapters for closed-weight models (Anthropic, Gemini).

These tokenizers expose only .count() — token IDs are not returned by the APIs.
"""

from __future__ import annotations

import os

from .base import Tokenizer, TokenizerInfo
from .exceptions import TokenizerUnavailable
from .registry import register


class AnthropicCountTokenizer:
    def __init__(self, info: TokenizerInfo, model: str) -> None:
        self.info = info
        self._model = model
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise TokenizerUnavailable(info.id, "ANTHROPIC_API_KEY not set")
        try:
            from anthropic import Anthropic
        except ImportError as e:
            raise TokenizerUnavailable(info.id, f"missing extra 'api': {e}") from e
        self._client = Anthropic(api_key=key)

    def encode(self, text: str) -> list[int]:
        raise NotImplementedError(
            "Anthropic API is count-only — token IDs are not returned. Use .count(text)."
        )

    def count(self, text: str) -> int:
        r = self._client.messages.count_tokens(
            model=self._model,
            messages=[{"role": "user", "content": text}],
        )
        return int(r.input_tokens)


class GeminiCountTokenizer:
    def __init__(self, info: TokenizerInfo, model: str) -> None:
        self.info = info
        self._model = model
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise TokenizerUnavailable(info.id, "GEMINI_API_KEY (or GOOGLE_API_KEY) not set")
        try:
            from google import genai
        except ImportError as e:
            raise TokenizerUnavailable(info.id, f"missing extra 'api': {e}") from e
        self._client = genai.Client(api_key=key)

    def encode(self, text: str) -> list[int]:
        raise NotImplementedError(
            "Gemini API is count-only — token IDs are not returned. Use .count(text)."
        )

    def count(self, text: str) -> int:
        r = self._client.models.count_tokens(model=self._model, contents=text)
        return int(r.total_tokens)


_API_TOKENIZERS = [
    ("anthropic/claude", "claude-opus-4-5-20251101", "anthropic", AnthropicCountTokenizer),
    ("google/gemini", "gemini-2.5-pro", "google", GeminiCountTokenizer),
]


def _make_loader(info: TokenizerInfo, model: str, cls):
    def _load() -> Tokenizer:
        return cls(info, model)

    return _load


def register_all() -> None:
    for tid, model, family, cls in _API_TOKENIZERS:
        info = TokenizerInfo(
            id=tid,
            family=family,  # type: ignore[arg-type]
            backend="api",
            gated=True,
            extra="api",
            notes=f"count-only; model={model}",
        )
        register(info, _make_loader(info, model, cls))


register_all()
