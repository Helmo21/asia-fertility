"""NIAH haystack builder with real-tokenizer sizing."""
from __future__ import annotations

from dataclasses import dataclass

from asia_fertility.corpora.base import Sentence
from asia_fertility.tokenizers.base import Tokenizer


@dataclass(frozen=True)
class Haystack:
    text: str
    target_tokens: int
    actual_tokens: int
    marker: str
    position_pct: float
    marker_position_tokens: int
    n_sentences_used: int


def _fill_to_tokens(
    sentences: list[Sentence],
    target: int,
    tokenizer: Tokenizer,
    sep: str,
    *,
    start_idx: int,
) -> tuple[str, int]:
    parts: list[str] = []
    n = 0
    accum = 0
    if not sentences:
        return "", 0
    idx = start_idx % len(sentences)
    while accum < target and n < 10000:
        parts.append(sentences[idx].text)
        n += 1
        if n % 5 == 0 or n == 1:
            accum = tokenizer.count(sep.join(parts))
        else:
            accum += tokenizer.count(sentences[idx].text) + 1
        idx = (idx + 1) % len(sentences)
    return sep.join(parts), n


def build_haystack(
    sentences: list[Sentence],
    *,
    target_tokens: int,
    tokenizer: Tokenizer,
    marker: str,
    position_pct: float,
    sentence_separator: str = " ",
) -> Haystack:
    if not 0.0 < position_pct < 1.0:
        raise ValueError(f"position_pct must be in (0,1), got {position_pct}")
    if not sentences:
        raise ValueError("Cannot build haystack from empty sentence list")

    marker_tokens = tokenizer.count(marker)
    if target_tokens < marker_tokens * 4:
        raise ValueError(
            f"target_tokens={target_tokens} too small for marker of {marker_tokens} tokens"
        )

    pre_target = max(1, int(target_tokens * position_pct) - marker_tokens // 2)
    post_target = max(1, target_tokens - pre_target - marker_tokens)

    pre_text, n_pre = _fill_to_tokens(
        sentences, pre_target, tokenizer, sentence_separator, start_idx=0
    )
    post_text, n_post = _fill_to_tokens(
        sentences, post_target, tokenizer, sentence_separator, start_idx=n_pre
    )

    full_text = f"{pre_text}{sentence_separator}{marker}{sentence_separator}{post_text}"
    actual_tokens = tokenizer.count(full_text)
    marker_position_tokens = tokenizer.count(f"{pre_text}{sentence_separator}{marker}")

    return Haystack(
        text=full_text,
        target_tokens=target_tokens,
        actual_tokens=actual_tokens,
        marker=marker,
        position_pct=position_pct,
        marker_position_tokens=marker_position_tokens,
        n_sentences_used=n_pre + n_post,
    )
