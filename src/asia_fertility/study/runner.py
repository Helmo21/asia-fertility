"""Study runner orchestrator."""
from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from importlib.resources import files
from pathlib import Path

from asia_fertility.config import StudyConfig
from asia_fertility.core import per_sentence
from asia_fertility.core.aggregate_ci import aggregate_with_cis
from asia_fertility.core.metrics import PerSentenceMetrics
from asia_fertility.core.segmentation import count_words
from asia_fertility.core.spaceless import segmenter_in_use
from asia_fertility.corpora import (
    CorpusUnavailable,
    LanguageNotInCorpus,
    load_corpus,
)
from asia_fertility.languages import get_language
from asia_fertility.tokenizers import (
    TokenizerNotFound,
    TokenizerUnavailable,
    get_tokenizer,
)

from .row import Row

_log = logging.getLogger(__name__)


@dataclass
class StudyResult:
    config: StudyConfig
    rows: list[Row]
    manifest: dict | None = None

    def write_all(self, output_dir: Path | None = None) -> Path:
        from .manifest import build_manifest
        from .writers import (
            write_csv,
            write_json,
            write_leaderboard_stub,
            write_manifest,
            write_parquet,
        )

        out = Path(output_dir) if output_dir else self.config.resolve_output_dir()
        out.mkdir(parents=True, exist_ok=True)

        if self.manifest is None:
            self.manifest = build_manifest(self.config, n_rows=len(self.rows))

        write_csv(self, out / "results.csv")
        write_json(self, out / "results.json")
        write_parquet(self, out / "results.parquet")
        write_leaderboard_stub(self, out / "leaderboard.json")
        write_manifest(self.manifest, out / "manifest.json")
        return out


def _resolve_corpus(cfg: StudyConfig, corpus_name: str):
    """Resolve a corpus; special-case `reproduce` to the bundled reference suite."""
    if corpus_name == "custom" and cfg.name == "reproduce":
        ref_path = files("asia_fertility.data.reference_suite").joinpath("reference.jsonl")
        return load_corpus("custom", path=str(ref_path))
    return load_corpus(corpus_name)


def _measure_cell(
    cfg: StudyConfig,
    corpus_name: str,
    lang: str,
    tokenizer_id: str,
    *,
    baseline_metrics: dict[str, list[PerSentenceMetrics]] | None,
) -> Row:
    language = get_language(lang)
    base_row = Row(
        corpus=corpus_name,
        lang=language.name,
        iso=lang,
        script=language.script,
        family=language.family,
        tokenizer=tokenizer_id,
        tokenizer_family="",
        tokenizer_backend="",
        segmenter_used=(segmenter_in_use(lang) if language.spaceless else "icu_or_regex"),
    )

    try:
        tok = get_tokenizer(tokenizer_id)
    except (TokenizerUnavailable, TokenizerNotFound) as e:
        return replace(base_row, tokenizer_unavailable=True, skip_reason=str(e))

    base_row = replace(
        base_row,
        tokenizer_family=tok.info.family,
        tokenizer_backend=tok.info.backend,
    )

    try:
        corpus = _resolve_corpus(cfg, corpus_name)
    except CorpusUnavailable as e:
        return replace(base_row, skip_reason=str(e))

    try:
        sentences = list(corpus.iter_sentences(lang, limit=cfg.n_sentences))
    except (LanguageNotInCorpus, NotImplementedError) as e:
        return replace(base_row, skip_reason=str(e))

    if not sentences:
        return replace(base_row, skip_reason="0 sentences for this language")

    try:
        target_metrics = [
            per_sentence(s, tok, segmenter=count_words) for s in sentences
        ]
    except NotImplementedError as e:
        # API count-only tokenizers raise on .encode() if invoked.
        return replace(base_row, skip_reason=f"tokenizer cannot encode: {e}")

    cell_baseline = None
    if baseline_metrics is not None and lang != cfg.baseline_language:
        cell_baseline = baseline_metrics.get(f"{corpus_name}:{tokenizer_id}")

    agg = aggregate_with_cis(
        target_metrics,
        baseline=cell_baseline,
        n_resamples=cfg.n_bootstrap,
        rng_seed=cfg.rng_seed,
        windows=cfg.windows,
    )

    return replace(
        base_row,
        n_sentences=agg.n_sentences,
        tokens_sum=sum(m.tokens for m in target_metrics),
        words_sum=sum(m.words for m in target_metrics),
        chars_sum=sum(m.chars for m in target_metrics),
        bytes_sum=sum(m.bytes_ for m in target_metrics),
        fertility=agg.fertility[0],
        fertility_ci_low=agg.fertility[1],
        fertility_ci_high=agg.fertility[2],
        premium=agg.premium[0] if agg.premium else float("nan"),
        premium_ci_low=agg.premium[1] if agg.premium else float("nan"),
        premium_ci_high=agg.premium[2] if agg.premium else float("nan"),
        cost_ratio=agg.cost_ratio[0] if agg.cost_ratio else float("nan"),
        cost_ratio_ci_low=agg.cost_ratio[1] if agg.cost_ratio else float("nan"),
        cost_ratio_ci_high=agg.cost_ratio[2] if agg.cost_ratio else float("nan"),
        cpt=agg.cpt[0],
        cpt_ci_low=agg.cpt[1],
        cpt_ci_high=agg.cpt[2],
        bpt=agg.bpt[0],
        bpt_ci_low=agg.bpt[1],
        bpt_ci_high=agg.bpt[2],
        context_efficiency=agg.context_efficiency,
    )


def run_study(cfg: StudyConfig) -> StudyResult:
    """Walk the (corpus × language × tokenizer) grid; return all rows."""
    rows: list[Row] = []
    baseline_cache: dict[str, list[PerSentenceMetrics]] = {}

    # Pass 1: cache baseline metrics per (corpus, tokenizer)
    for corpus_name in cfg.corpora:
        for tokenizer_id in cfg.tokenizers:
            try:
                tok = get_tokenizer(tokenizer_id)
            except (TokenizerUnavailable, TokenizerNotFound):
                continue
            try:
                corpus = _resolve_corpus(cfg, corpus_name)
                base_sents = list(
                    corpus.iter_sentences(cfg.baseline_language, limit=cfg.n_sentences)
                )
                if not base_sents:
                    continue
                base_pm = [
                    per_sentence(s, tok, segmenter=count_words) for s in base_sents
                ]
                baseline_cache[f"{corpus_name}:{tokenizer_id}"] = base_pm
            except (CorpusUnavailable, LanguageNotInCorpus, NotImplementedError):
                continue

    # Pass 2: measure target × all langs
    total = len(cfg.corpora) * len(cfg.languages) * len(cfg.tokenizers)
    completed = 0
    for corpus_name in cfg.corpora:
        for lang in cfg.languages:
            for tokenizer_id in cfg.tokenizers:
                row = _measure_cell(
                    cfg, corpus_name, lang, tokenizer_id,
                    baseline_metrics=baseline_cache,
                )
                rows.append(row)
                completed += 1
                status = (
                    f"fert={row.fertility:.2f}"
                    if row.skip_reason is None
                    else f"skip={row.skip_reason[:60]}"
                )
                _log.info(
                    f"[{completed:4d}/{total}] {corpus_name} {lang} {tokenizer_id} {status}"
                )

    return StudyResult(config=cfg, rows=rows)
