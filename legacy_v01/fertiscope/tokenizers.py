"""Tokenizer wrappers. Same interface for tiktoken + HuggingFace tokenizers libs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict


@dataclass(frozen=True)
class TokenizerSpec:
    """Static description of a tokenizer FertiScope can analyze."""
    id: str
    family: str
    display_name: str
    notes: str
    # Optional: the HF repo id for tokenizer-only download.
    # Empty for tiktoken-native tokenizers.
    hf_repo: str = ""


# v0.1 launch tokenizers. tiktoken-native ones are zero-friction;
# HF ones need a one-time download of the tokenizer files (no model weights).
TOKENIZERS: Dict[str, TokenizerSpec] = {
    "cl100k": TokenizerSpec(
        id="cl100k",
        family="tiktoken",
        display_name="OpenAI cl100k_base (GPT-3.5 / GPT-4 / GPT-4 Turbo)",
        notes="Default for OpenAI chat models pre-GPT-4o.",
    ),
    "o200k": TokenizerSpec(
        id="o200k",
        family="tiktoken",
        display_name="OpenAI o200k_base (GPT-4o family)",
        notes="Larger vocab, better cross-lingual coverage than cl100k.",
    ),
    "llama-3.1": TokenizerSpec(
        id="llama-3.1",
        family="hf",
        display_name="Meta Llama 3.1",
        notes="Un-gated tokenizer-only mirror via unsloth (no model weights download).",
        hf_repo="unsloth/Llama-3.1-8B",
    ),
    "sea-lion-v3": TokenizerSpec(
        id="sea-lion-v3",
        family="hf",
        display_name="AI Singapore SEA-LION v3 (Llama-based)",
        notes="SEA-tuned tokenizer covering 11 Southeast Asian languages.",
        hf_repo="aisingapore/Llama-SEA-LION-v3-8B-IT",
    ),
}


def list_tokenizers() -> Dict[str, TokenizerSpec]:
    return dict(TOKENIZERS)


def get_tokenize_fn(tokenizer_id: str) -> Callable[[str], int]:
    """Return a callable that takes a string and returns the token count.

    Pure function. No state. Caches the underlying tokenizer object internally
    so repeated calls don't re-download or re-initialize.
    """
    if tokenizer_id not in TOKENIZERS:
        raise ValueError(f"unknown tokenizer {tokenizer_id!r}; see TOKENIZERS for valid ids")

    spec = TOKENIZERS[tokenizer_id]

    if spec.family == "tiktoken":
        import tiktoken
        enc_name = "cl100k_base" if spec.id == "cl100k" else "o200k_base"
        enc = tiktoken.get_encoding(enc_name)

        def _tok(text: str) -> int:
            return len(enc.encode(text))

        return _tok

    if spec.family == "hf":
        from tokenizers import Tokenizer
        # Tokenizer.from_pretrained downloads only the tokenizer.json file
        # (no model weights). For Llama-3.1 via unsloth, this is ~5MB.
        tok = Tokenizer.from_pretrained(spec.hf_repo)

        def _tok(text: str) -> int:
            return len(tok.encode(text).ids)

        return _tok

    raise ValueError(f"unknown tokenizer family {spec.family!r}")
