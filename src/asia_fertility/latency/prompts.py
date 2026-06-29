"""Per-language prompt construction for the latency benchmark.

We need N + n_warmup *distinct* prompts per (lang) cell so that prefix
caching at the provider can't shortcut TTFT measurement. Each prompt
pulls a different FLORES sentence and wraps it with a fixed instruction
in English (model-agnostic; the instruction is the same across langs).
"""

from __future__ import annotations

from asia_fertility.corpora import Sentence, load_corpus

_INSTRUCTION = "Summarize the above text in one short sentence."


def build_prompts(lang: str, n_total: int, corpus_name: str = "flores") -> list[str]:
    """Return `n_total` distinct prompts in the target language.

    Uses the first `n_total` FLORES sentences for that language. Order is
    deterministic (FLORES sentence index 0, 1, 2, ...) so re-runs with
    the same config produce comparable timing input.
    """
    corpus = load_corpus(corpus_name)
    sentences: list[Sentence] = list(corpus.iter_sentences(lang, limit=n_total))
    if len(sentences) < n_total:
        raise ValueError(
            f"FLORES has only {len(sentences)} sentences for lang '{lang}', "
            f"need {n_total} for warmup+trials"
        )
    return [f"{s.text}\n\n{_INSTRUCTION}" for s in sentences]
