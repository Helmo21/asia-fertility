"""HuggingFace `transformers` adapter — 8 tokenizer families.

Gated repos (Llama, Gemma) require HF_TOKEN + license acceptance on huggingface.co.
Ungated repos (Mistral, Qwen, DeepSeek, BLOOM, Aya) work without HF_TOKEN.
"""
from __future__ import annotations

import os

from .base import Tokenizer, TokenizerInfo
from .exceptions import TokenizerUnavailable
from .registry import register

# (id, repo_id, family, gated, notes)
_HF_TOKENIZERS: list[tuple[str, str, str, bool, str]] = [
    ("meta/llama-3.1", "meta-llama/Llama-3.1-8B", "meta", True, "Same tokenizer as SEA-LION v3"),
    ("mistral/tekken", "mistralai/Mistral-Nemo-Base-2407", "mistral", False, "Tekken tokenizer"),
    ("qwen/qwen3", "Qwen/Qwen2.5-7B", "qwen", False, "Qwen2.5 tokenizer (Qwen3 family)"),
    ("deepseek/v3", "deepseek-ai/DeepSeek-V2.5", "deepseek", False, ""),
    ("bigscience/bloom", "bigscience/bloom-560m", "bigscience", False, "Multilingual baseline (BLOOM tokenizer)"),
    ("cohere/aya-expanse", "CohereForAI/aya-expanse-8b", "cohere", True, "Multilingual-optimized baseline"),
    ("google/gemma-2", "google/gemma-2-9b", "google", True, "Gemma 2 (latest stable)"),
]


class HuggingFaceTokenizer:
    def __init__(self, info: TokenizerInfo, repo_id: str) -> None:
        try:
            from transformers import AutoTokenizer
        except ImportError as e:
            raise TokenizerUnavailable(info.id, f"missing extra 'hf': {e}") from e

        token = os.environ.get("HF_TOKEN")
        try:
            self._tok = AutoTokenizer.from_pretrained(
                repo_id, token=token, trust_remote_code=False, use_fast=True
            )
        except OSError as e:
            msg = str(e).lower()
            if "401" in msg or "403" in msg or "gated" in msg or "access" in msg or "restricted" in msg:
                raise TokenizerUnavailable(
                    info.id, "gated repo, HF_TOKEN missing or lacks license access"
                ) from e
            raise TokenizerUnavailable(info.id, f"failed to download tokenizer: {e}") from e
        except Exception as e:
            raise TokenizerUnavailable(info.id, f"load error: {e}") from e
        self.info = info

    def encode(self, text: str) -> list[int]:
        return self._tok.encode(text, add_special_tokens=False)

    def count(self, text: str) -> int:
        return len(self.encode(text))


def _make_loader(info: TokenizerInfo, repo_id: str):
    def _load() -> Tokenizer:
        return HuggingFaceTokenizer(info, repo_id)

    return _load


def register_all() -> None:
    for tid, repo_id, family, gated, notes in _HF_TOKENIZERS:
        info = TokenizerInfo(
            id=tid,
            family=family,  # type: ignore[arg-type]
            backend="hf",
            gated=gated,
            extra="hf",
            notes=notes,
        )
        register(info, _make_loader(info, repo_id))


register_all()
