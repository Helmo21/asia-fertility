"""Per-sentence metrics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from asia_fertility.corpora.base import Sentence
from asia_fertility.tokenizers.base import Tokenizer

from .normalize import nfc


@dataclass(frozen=True)
class PerSentenceMetrics:
    sentence_id: str
    lang: str
    tokenizer_id: str
    tokens: int
    words: int
    chars: int
    bytes_: int


def per_sentence(
    sentence: Sentence,
    tokenizer: Tokenizer,
    *,
    segmenter: Callable[[str, str], int] | None = None,
) -> PerSentenceMetrics:
    """Compute per-sentence metrics. NFC-normalizes the text first.

    If `segmenter` is None, falls back to whitespace word count.
    """
    normalized = nfc(sentence.text)
    tokens = tokenizer.count(normalized)

    if segmenter is None:
        words = max(1, len(normalized.split()))
    else:
        words = max(1, segmenter(normalized, sentence.lang))

    return PerSentenceMetrics(
        sentence_id=sentence.id,
        lang=sentence.lang,
        tokenizer_id=tokenizer.info.id,
        tokens=tokens,
        words=words,
        chars=len(normalized),
        bytes_=len(normalized.encode("utf-8")),
    )
