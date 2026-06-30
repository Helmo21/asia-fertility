"""Offline reference suite — one-command credibility demo.

Runs every available tokenizer against the bundled 160-sentence parallel
reference suite (10 sentences × 16 languages from FLORES-200) and prints a
small leaderboard. No network, no API keys required: the suite is shipped
inside the wheel under `_defaults/reference_suite/reference.jsonl`.

The goal is a sanity check, not a full study — for that, run:
    asia-fertility run --config configs/study_main.yaml
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from asia_fertility.tokenizers import get_tokenizer, is_available, list_tokenizers
from asia_fertility.tokenizers.exceptions import TokenizerUnavailable


@dataclass(frozen=True)
class ReproduceRow:
    tokenizer: str
    lang: str
    n_sentences: int
    n_tokens_total: int
    n_chars_total: int
    fertility: float | None
    cpt: float


def _bundled_path() -> Path:
    return Path(str(files("asia_fertility._defaults").joinpath("reference_suite/reference.jsonl")))


def load_reference(path: str | Path | None = None) -> list[dict]:
    """Load the bundled offline reference suite (id, lang, text rows)."""
    actual = Path(path) if path else _bundled_path()
    rows: list[dict] = []
    with actual.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def reproduce_suite(
    tokenizer_ids: list[str] | None = None,
    path: str | Path | None = None,
    baseline_lang: str = "eng",
) -> list[ReproduceRow]:
    """Run available tokenizers against the parallel suite, return per-(tok, lang) rows."""
    sentences = load_reference(path)
    if tokenizer_ids is None:
        tokenizer_ids = [t.id for t in list_tokenizers() if is_available(t.id)]

    # Bucket sentences by language
    by_lang: dict[str, list[str]] = defaultdict(list)
    for s in sentences:
        by_lang[s["lang"]].append(s["text"])

    rows: list[ReproduceRow] = []
    for tid in tokenizer_ids:
        try:
            tok = get_tokenizer(tid)
        except TokenizerUnavailable:
            continue
        # Compute per-language totals; sum-then-divide for fertility.
        for lang, texts in by_lang.items():
            tokens_total = sum(tok.count(t) for t in texts)
            # Use whitespace split as a rough word count for spaced-script langs;
            # for spaceless scripts CPT is the more honest signal.
            words_total = sum(len(t.split()) for t in texts) or None
            chars_total = sum(len(t) for t in texts)
            fertility = tokens_total / words_total if words_total else None
            cpt = chars_total / tokens_total if tokens_total else 0.0
            rows.append(
                ReproduceRow(
                    tokenizer=tid,
                    lang=lang,
                    n_sentences=len(texts),
                    n_tokens_total=tokens_total,
                    n_chars_total=chars_total,
                    fertility=fertility,
                    cpt=cpt,
                )
            )
    return rows


def fertility_premiums(
    rows: list[ReproduceRow], baseline_lang: str = "eng"
) -> list[tuple[str, str, float | None, float | None]]:
    """Return (tokenizer, lang, fertility, premium-vs-baseline) tuples."""
    by_tok: dict[str, dict[str, float | None]] = defaultdict(dict)
    for r in rows:
        by_tok[r.tokenizer][r.lang] = r.fertility
    out: list[tuple[str, str, float | None, float | None]] = []
    for tok, langs in by_tok.items():
        base = langs.get(baseline_lang)
        for lang, fert in langs.items():
            premium = (fert / base) if (base and fert) else None
            out.append((tok, lang, fert, premium))
    return out
