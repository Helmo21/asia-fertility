# Study runner orchestrator (grid iteration + skip-rows)

Status: pending
Tags: `study`, `runner`, `orchestrator`, `parquet`
Depends on: #012, #013, #014, #019, #023
Blocks: #025, #026

## Scope

The orchestrator that walks the (corpus × language × tokenizer) grid, calls `aggregate_with_cis` for each cell, and produces a list of rows. Unavailable tokenizers and uncovered languages produce **skip rows** (not exceptions). Output writers (parquet/csv/json/leaderboard.json/manifest.json) ship in #025.

### Files to create

- `src/fertiscope/study/__init__.py`
- `src/fertiscope/study/runner.py`
- `src/fertiscope/study/row.py` — `Row` dataclass + schema doc.
- `tests/unit/test_study_runner.py`
- `tests/integration/test_study_runner_smoke.py`

### Files to modify

- None.

### Interface and contract

`src/fertiscope/study/row.py`:

```python
"""The wide-table row schema for study results.

One row per (corpus, language, tokenizer) cell.
Skip rows have tokenizer_unavailable=True and metric fields = NaN.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math


@dataclass(frozen=True)
class Row:
    # --- identity
    corpus: str
    lang: str
    iso: str
    script: str
    family: str
    tokenizer: str
    tokenizer_family: str
    tokenizer_backend: str

    # --- aggregates (NaN for skip rows)
    n_sentences: int                = 0
    tokens_sum: int                 = 0
    words_sum: int                  = 0
    chars_sum: int                  = 0
    bytes_sum: int                  = 0

    fertility: float                = float("nan")
    fertility_ci_low: float         = float("nan")
    fertility_ci_high: float        = float("nan")

    premium: float                  = float("nan")
    premium_ci_low: float           = float("nan")
    premium_ci_high: float          = float("nan")

    cost_ratio: float               = float("nan")
    cost_ratio_ci_low: float        = float("nan")
    cost_ratio_ci_high: float       = float("nan")

    cpt: float                      = float("nan")
    cpt_ci_low: float               = float("nan")
    cpt_ci_high: float              = float("nan")

    bpt: float                      = float("nan")
    bpt_ci_low: float               = float("nan")
    bpt_ci_high: float              = float("nan")

    context_efficiency: dict[int, float] = field(default_factory=dict)

    # --- provenance
    segmenter_used: str             = ""
    tokenizer_unavailable: bool     = False
    skip_reason: str | None         = None

    def is_baseline(self, baseline_lang: str) -> bool:
        return self.iso == baseline_lang
```

`src/fertiscope/study/runner.py`:

```python
from __future__ import annotations
import logging
from dataclasses import dataclass, replace
from pathlib import Path
from fertiscope.config import StudyConfig
from fertiscope.tokenizers import get_tokenizer, TokenizerUnavailable, TokenizerNotFound
from fertiscope.corpora import load_corpus, LanguageNotInCorpus, CorpusUnavailable
from fertiscope.languages import get_language
from fertiscope.core import per_sentence, PerSentenceMetrics
from fertiscope.core.segmentation import count_words
from fertiscope.core.spaceless import segmenter_in_use
from fertiscope.core.aggregate_ci import aggregate_with_cis, AggregateMetrics
from .row import Row

_log = logging.getLogger(__name__)


@dataclass
class StudyResult:
    config: StudyConfig
    rows: list[Row]
    # Output writers (parquet, csv, json, manifest, leaderboard) live in #025.
    # `to_parquet`, `to_csv`, etc., are added there as methods or top-level functions.


def _measure_cell(
    cfg: StudyConfig,
    corpus_name: str,
    lang: str,
    tokenizer_id: str,
    *,
    baseline_metrics: dict[str, list[PerSentenceMetrics]] | None,
) -> Row:
    """Run one cell. Returns a Row with metrics OR a skip Row."""
    language = get_language(lang)
    base_row = Row(
        corpus=corpus_name, lang=language.name, iso=lang,
        script=language.script, family=language.family,
        tokenizer=tokenizer_id,
        tokenizer_family="", tokenizer_backend="",
        segmenter_used=(segmenter_in_use(lang) if language.spaceless else "icu_or_regex"),
    )

    # 1. Resolve tokenizer
    try:
        tok = get_tokenizer(tokenizer_id)
    except (TokenizerUnavailable, TokenizerNotFound) as e:
        return replace(base_row, tokenizer_unavailable=True, skip_reason=str(e))

    base_row = replace(base_row,
                       tokenizer_family=tok.info.family,
                       tokenizer_backend=tok.info.backend)

    # 2. Resolve corpus
    try:
        if corpus_name == "custom" and cfg.name == "reproduce":
            # Reproduce study uses the bundled reference suite
            from importlib.resources import files
            ref_path = files("fertiscope.data.reference_suite").joinpath("reference.jsonl")
            corpus = load_corpus("custom", path=str(ref_path))
        else:
            corpus = load_corpus(corpus_name)
    except CorpusUnavailable as e:
        return replace(base_row, tokenizer_unavailable=False, skip_reason=str(e))

    # 3. Load sentences
    try:
        sentences = list(corpus.iter_sentences(lang, limit=cfg.n_sentences))
    except LanguageNotInCorpus as e:
        return replace(base_row, skip_reason=str(e))

    if not sentences:
        return replace(base_row, skip_reason="0 sentences for this language in this corpus")

    # 4. Per-sentence metrics
    target_metrics = [per_sentence(s, tok, segmenter=count_words) for s in sentences]
    cell_baseline = None
    if baseline_metrics is not None and lang != cfg.baseline_language:
        cell_baseline = baseline_metrics.get(f"{corpus_name}:{tokenizer_id}")

    agg: AggregateMetrics = aggregate_with_cis(
        target_metrics,
        baseline=cell_baseline,
        n_resamples=cfg.n_bootstrap,
        rng_seed=cfg.rng_seed,
        windows=cfg.windows,
    )

    return replace(base_row,
        n_sentences=agg.n_sentences,
        tokens_sum=sum(m.tokens for m in target_metrics),
        words_sum=sum(m.words for m in target_metrics),
        chars_sum=sum(m.chars for m in target_metrics),
        bytes_sum=sum(m.bytes_ for m in target_metrics),
        fertility=agg.fertility[0], fertility_ci_low=agg.fertility[1], fertility_ci_high=agg.fertility[2],
        premium=agg.premium[0] if agg.premium else float("nan"),
        premium_ci_low=agg.premium[1] if agg.premium else float("nan"),
        premium_ci_high=agg.premium[2] if agg.premium else float("nan"),
        cost_ratio=agg.cost_ratio[0] if agg.cost_ratio else float("nan"),
        cost_ratio_ci_low=agg.cost_ratio[1] if agg.cost_ratio else float("nan"),
        cost_ratio_ci_high=agg.cost_ratio[2] if agg.cost_ratio else float("nan"),
        cpt=agg.cpt[0], cpt_ci_low=agg.cpt[1], cpt_ci_high=agg.cpt[2],
        bpt=agg.bpt[0], bpt_ci_low=agg.bpt[1], bpt_ci_high=agg.bpt[2],
        context_efficiency=agg.context_efficiency,
    )


def run_study(cfg: StudyConfig) -> StudyResult:
    """Walk the (corpus × language × tokenizer) grid, return all rows."""
    rows: list[Row] = []

    # Two-pass: first pass builds baseline metrics per (corpus, tokenizer); second pass measures target.
    baseline_metrics_cache: dict[str, list[PerSentenceMetrics]] = {}

    for corpus_name in cfg.corpora:
        for tokenizer_id in cfg.tokenizers:
            try:
                tok = get_tokenizer(tokenizer_id)
            except (TokenizerUnavailable, TokenizerNotFound):
                continue            # baseline metrics not loadable; skip rows will be produced later
            try:
                if corpus_name == "custom" and cfg.name == "reproduce":
                    from importlib.resources import files
                    ref_path = files("fertiscope.data.reference_suite").joinpath("reference.jsonl")
                    corpus = load_corpus("custom", path=str(ref_path))
                else:
                    corpus = load_corpus(corpus_name)
                base_sents = list(corpus.iter_sentences(cfg.baseline_language, limit=cfg.n_sentences))
                if not base_sents:
                    continue
                base_pm = [per_sentence(s, tok, segmenter=count_words) for s in base_sents]
                baseline_metrics_cache[f"{corpus_name}:{tokenizer_id}"] = base_pm
            except (CorpusUnavailable, LanguageNotInCorpus):
                continue

    for corpus_name in cfg.corpora:
        for lang in cfg.languages:
            for tokenizer_id in cfg.tokenizers:
                row = _measure_cell(cfg, corpus_name, lang, tokenizer_id, baseline_metrics=baseline_metrics_cache)
                rows.append(row)
                _log.info(f"row: {corpus_name} {lang} {tokenizer_id} "
                          f"fert={row.fertility:.2f} skip={row.skip_reason or '-'}")

    return StudyResult(config=cfg, rows=rows)
```

`tests/unit/test_study_runner.py`:

```python
import pytest
from fertiscope.config import StudyConfig
from fertiscope.study.runner import run_study

def test_runner_produces_expected_row_count():
    # 1 corpus × 2 langs × 2 tokenizers = 4 rows. Use the reproduce bundled corpus.
    cfg = StudyConfig(
        name="reproduce",       # triggers bundled custom-corpus path
        languages=["eng","vie"], tokenizers=["openai/o200k_base","openai/cl100k_base"],
        corpora=["custom"], baseline_language="eng",
        n_sentences=5, n_bootstrap=50, rng_seed=42,
    )
    result = run_study(cfg)
    assert len(result.rows) == 4
    for r in result.rows:
        if r.skip_reason is None:
            assert r.n_sentences > 0
            assert r.tokens_sum > 0

def test_runner_skip_unavailable_tokenizer():
    cfg = StudyConfig(
        name="reproduce",
        languages=["eng"], tokenizers=["openai/o200k_base","nonexistent/tokenizer"],
        corpora=["custom"], baseline_language="eng",
        n_sentences=3, n_bootstrap=50, rng_seed=42,
    )
    result = run_study(cfg)
    rows = result.rows
    assert any(r.tokenizer == "nonexistent/tokenizer" and r.tokenizer_unavailable for r in rows)
    assert any(r.tokenizer == "openai/o200k_base" and not r.tokenizer_unavailable for r in rows)

def test_baseline_premium_is_nan_for_baseline_row():
    cfg = StudyConfig(
        name="reproduce",
        languages=["eng","vie"], tokenizers=["openai/o200k_base"],
        corpora=["custom"], baseline_language="eng",
        n_sentences=5, n_bootstrap=50, rng_seed=42,
    )
    rows = run_study(cfg).rows
    eng = [r for r in rows if r.iso == "eng"][0]
    vie = [r for r in rows if r.iso == "vie"][0]
    import math
    assert math.isnan(eng.premium)            # baseline has no premium
    assert not math.isnan(vie.premium)
    assert vie.premium > 0
```

`tests/integration/test_study_runner_smoke.py`:

```python
import pytest
from fertiscope.config import StudyConfig
from fertiscope.study.runner import run_study
from pathlib import Path

pytestmark = [pytest.mark.slow, pytest.mark.integration]

def test_study_test_yaml_end_to_end():
    cfg = StudyConfig.from_yaml(Path("configs/study_test.yaml"))
    result = run_study(cfg)
    # 1 corpus × 3 langs × 2 tokenizers = 6 rows expected
    assert len(result.rows) == 6
    # At least one tokenizer should be available and produce non-NaN fertility
    valid_rows = [r for r in result.rows if r.skip_reason is None]
    assert len(valid_rows) >= 4
```

### Notes

- **Two-pass design**: pass 1 caches baseline metrics per (corpus, tokenizer); pass 2 measures target languages reusing the cache. This avoids re-tokenizing baseline N times.
- The `reproduce` study `name` triggers special-case corpus path (bundled reference suite). This keeps the `custom` corpus loader generic.
- Skip-rows are LOAD-BEARING — the leaderboard renderer (#033) needs to know "this cell was attempted, here's why it failed". Don't drop them.
- The order of rows in `StudyResult.rows` is deterministic: `corpus × language × tokenizer` nested loops with fixed YAML ordering. Reviewers can grep specific cells.
- Output writers (parquet, JSON, manifest) live in #025. This task ends with rows-in-memory.

## Acceptance Criteria

- [ ] `run_study(cfg_test)` produces exactly `len(corpora) × len(languages) × len(tokenizers)` rows.
- [ ] Unavailable tokenizer produces a `Row(tokenizer_unavailable=True, skip_reason=...)` instead of crashing.
- [ ] Language not in corpus produces a skip row with reason.
- [ ] Baseline language row has `premium`, `cost_ratio` = NaN.
- [ ] Non-baseline rows have non-NaN `premium` when tokenizer is available.
- [ ] `Row.context_efficiency` populated with keys matching `cfg.windows`.
- [ ] `Row.segmenter_used` is non-empty for spaceless languages.
- [ ] All 3 unit tests pass.
- [ ] Integration test (with `[hf,oai]`, FLORES network access) runs `study_test.yaml` end-to-end in < 60s.
- [ ] `mypy --strict src/fertiscope/study/` passes.

## User Stories

### Story: Researcher kicks off the main study

1. `fertiscope run --config configs/study_main.yaml`.
2. Runner logs each cell as it completes (`row: flores tam openai/o200k_base fert=2.00 skip=-`).
3. After ~15 minutes, 352 rows in memory, ready for #025's output writers.

### Story: User without HF_TOKEN runs partial study

1. Cfg includes Llama-3.1 + Gemma-4 (gated).
2. Runner produces skip rows for those with `skip_reason="...gated repo..."`.
3. Other tokenizers complete normally.
4. Leaderboard shows partial coverage instead of failing.

### Story: Reviewer audits per-cell results

1. Reads `runs/main/results.csv`.
2. Filters `iso==tam, tokenizer==openai/cl100k_base`.
3. Sees `fertility=11.25, cost_ratio=7.19, bpt=2.05`.
4. Numbers match paper Table 1.

---

Blocked by: #012, #013, #014, #019, #023
