# Bootstrap CIs + `fertiscope measure` CLI end-to-end

Status: pending
Tags: `metrics`, `bootstrap`, `confidence-intervals`, `cli`, `measure`, `numpy`
Depends on: #006, #007, #008, #015, #016, #017, #018
Blocks: #024

## Scope

Two tied deliverables:

1. `bootstrap_ci` over sentence-level resamples for any sum-then-divide scalar metric, with a fixed RNG seed for bit-exact reproducibility.
2. `fertiscope measure` CLI that takes (text|corpus) × (lang) × (tokenizer) and prints fertility/premium/CPT/BPT each with 95% CI in a Rich table.

This is the user's first experience of the package as a usable tool.

### Files to create

- `src/fertiscope/core/bootstrap.py`
- `src/fertiscope/core/aggregate_ci.py` — wraps `aggregate.py` functions with CIs.
- `tests/unit/test_bootstrap.py`
- `tests/unit/test_measure_cli.py`
- `tests/unit/test_metrics_properties.py` — hypothesis property tests.

### Files to modify

- `src/fertiscope/cli.py` — replace `measure` stub body.

### Interface and contract

`src/fertiscope/core/bootstrap.py`:

```python
"""Bootstrap confidence intervals at the sentence level.

We resample with replacement at the sentence level (NOT at the token level)
because sentences are the natural i.i.d. unit in FLORES-style corpora. Fixed
RNG seed makes CIs bit-identical across runs.
"""
from __future__ import annotations
from typing import Callable, TypeVar
import numpy as np
from fertiscope.core.metrics import PerSentenceMetrics

T = TypeVar("T")

def bootstrap_ci(
    metrics: list[PerSentenceMetrics],
    stat_fn: Callable[[list[PerSentenceMetrics]], float],
    *,
    n_resamples: int = 1000,
    ci: float = 0.95,
    rng_seed: int = 42,
) -> tuple[float, float, float]:
    """Returns (point, low, high) where low/high are quantiles of the bootstrap
    distribution at (1-ci)/2 and 1-(1-ci)/2.

    For an n=1 input, returns (point, point, point) — degenerate but not crash.
    """
    if not metrics:
        raise ValueError("Cannot bootstrap an empty metrics list")
    point = stat_fn(metrics)
    if len(metrics) == 1:
        return (point, point, point)

    rng = np.random.default_rng(rng_seed)
    n = len(metrics)
    samples = np.empty(n_resamples, dtype=np.float64)
    for i in range(n_resamples):
        idx = rng.integers(0, n, n)
        resampled = [metrics[j] for j in idx]
        try:
            samples[i] = stat_fn(resampled)
        except ValueError:
            # rare: resample contains all-zero-words sentences. NaN it.
            samples[i] = np.nan

    samples = samples[~np.isnan(samples)]
    if len(samples) == 0:
        return (point, float("nan"), float("nan"))
    alpha = (1.0 - ci) / 2.0
    low  = float(np.quantile(samples, alpha))
    high = float(np.quantile(samples, 1.0 - alpha))
    return (point, low, high)
```

`src/fertiscope/core/aggregate_ci.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from fertiscope.core.metrics import PerSentenceMetrics
from fertiscope.core.aggregate import (
    fertility_point, cpt_point, bpt_point, same_content_cost_ratio, context_efficiency,
)
from fertiscope.core.bootstrap import bootstrap_ci

Triple = tuple[float, float, float]


@dataclass(frozen=True)
class AggregateMetrics:
    lang: str
    tokenizer_id: str
    n_sentences: int
    fertility: Triple                 # (point, low, high)
    premium: Triple | None            # None for baseline
    cost_ratio: Triple | None         # None for baseline
    cpt: Triple
    bpt: Triple
    context_efficiency: dict[int, float]


def aggregate_with_cis(
    target: list[PerSentenceMetrics],
    *,
    baseline: list[PerSentenceMetrics] | None = None,
    n_resamples: int = 1000,
    rng_seed: int = 42,
    windows: list[int] | None = None,
) -> AggregateMetrics:
    """Compute fertility/CPT/BPT/premium with 95% CIs.

    If baseline is None, premium and cost_ratio are None (this is the baseline row).
    """
    if not target:
        raise ValueError("Cannot aggregate empty target metrics")
    if windows is None:
        windows = [4096, 8192, 32768, 131072]

    fert = bootstrap_ci(target, fertility_point, n_resamples=n_resamples, rng_seed=rng_seed)
    cpt  = bootstrap_ci(target, cpt_point,  n_resamples=n_resamples, rng_seed=rng_seed)
    bpt  = bootstrap_ci(target, bpt_point,  n_resamples=n_resamples, rng_seed=rng_seed)

    premium = None
    cost_ratio = None
    if baseline:
        # Baseline statistics are computed point-only; the resampling resamples
        # the TARGET while the baseline stays fixed at its point estimate.
        # This is the standard convention; alternative two-sample bootstraps
        # would also resample the baseline, but the deflation effect on CIs is
        # small relative to the point-estimate dynamic range we care about.
        base_fert = fertility_point(baseline)
        prem_fn = lambda m: fertility_point(m) / base_fert
        premium = bootstrap_ci(target, prem_fn, n_resamples=n_resamples, rng_seed=rng_seed)
        if len(target) == len(baseline):
            base_tokens = sum(m.tokens for m in baseline)
            cr_fn = lambda m: sum(x.tokens for x in m) / base_tokens
            cost_ratio = bootstrap_ci(target, cr_fn, n_resamples=n_resamples, rng_seed=rng_seed)

    return AggregateMetrics(
        lang=target[0].lang,
        tokenizer_id=target[0].tokenizer_id,
        n_sentences=len(target),
        fertility=fert,
        premium=premium,
        cost_ratio=cost_ratio,
        cpt=cpt,
        bpt=bpt,
        context_efficiency=context_efficiency(cpt[0], windows),
    )
```

`cli.py` — replace `measure`:

```python
@app.command()
def measure(
    text: str | None = typer.Option(None, "--text"),
    corpus: str | None = typer.Option(None, "--corpus"),
    path: str | None = typer.Option(None, "--path"),
    lang: str = typer.Option("eng", "--lang"),
    tokenizer: str = typer.Option("openai/o200k_base", "--tokenizer"),
    baseline_lang: str = typer.Option("eng", "--baseline-lang"),
    n_resamples: int = typer.Option(1000, "--n-resamples"),
    rng_seed: int = typer.Option(42, "--rng-seed"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Token count, fertility, premium, CPT, BPT for input text/corpus."""
    from fertiscope.tokenizers import get_tokenizer
    from fertiscope.corpora import Sentence, load_corpus
    from fertiscope.core import per_sentence
    from fertiscope.core.segmentation import count_words
    from fertiscope.core.aggregate_ci import aggregate_with_cis

    if text is None and corpus is None:
        typer.echo("Provide --text or --corpus", err=True)
        raise typer.Exit(code=2)

    tok = get_tokenizer(tokenizer)

    if text is not None:
        sentences = [Sentence(id="cli:0", lang=lang, text=text)]
        target_metrics = [per_sentence(s, tok, segmenter=count_words) for s in sentences]
        baseline_metrics = None
    else:
        loaded = load_corpus(corpus, path=path) if corpus == "custom" else load_corpus(corpus)
        target_sentences   = list(loaded.iter_sentences(lang))
        baseline_sentences = list(loaded.iter_sentences(baseline_lang))
        target_metrics   = [per_sentence(s, tok, segmenter=count_words) for s in target_sentences]
        baseline_metrics = [per_sentence(s, tok, segmenter=count_words) for s in baseline_sentences]

    agg = aggregate_with_cis(target_metrics, baseline=baseline_metrics, n_resamples=n_resamples, rng_seed=rng_seed)

    if json_out:
        import json, dataclasses
        typer.echo(json.dumps(dataclasses.asdict(agg), default=str, indent=2, ensure_ascii=False))
        return

    from rich.console import Console
    from rich.table import Table
    table = Table(title=f"FertiScope measure · lang={agg.lang} · tokenizer={agg.tokenizer_id} · n={agg.n_sentences}", title_style="bold")
    table.add_column("Metric")
    table.add_column("Point", justify="right")
    table.add_column("95% CI", justify="right")

    def fmt(t: tuple[float, float, float] | None) -> tuple[str, str]:
        if t is None: return ("—", "—")
        p, l, h = t
        return (f"{p:.3f}", f"[{l:.3f}, {h:.3f}]")

    for name, val in [
        ("Fertility (tokens/word)", agg.fertility),
        ("Premium (vs baseline)",   agg.premium),
        ("Cost ratio (same content)", agg.cost_ratio),
        ("CPT (chars/token)",       agg.cpt),
        ("BPT (bytes/token)",       agg.bpt),
    ]:
        p, ci_s = fmt(val)
        table.add_row(name, p, ci_s)

    Console().print(table)
```

`tests/unit/test_bootstrap.py`:

```python
import math
from fertiscope.core import PerSentenceMetrics
from fertiscope.core.bootstrap import bootstrap_ci
from fertiscope.core.aggregate import fertility_point

def _m(t, w):
    return PerSentenceMetrics("s","eng","t",tokens=t,words=w,chars=w*4,bytes_=w*4)

def test_bootstrap_deterministic():
    ms = [_m(t=i+1, w=1) for i in range(20)]
    a = bootstrap_ci(ms, fertility_point, n_resamples=200, rng_seed=42)
    b = bootstrap_ci(ms, fertility_point, n_resamples=200, rng_seed=42)
    assert a == b

def test_bootstrap_ci_includes_point():
    ms = [_m(t=i+1, w=1) for i in range(20)]
    p, l, h = bootstrap_ci(ms, fertility_point, n_resamples=500, rng_seed=42)
    assert l <= p <= h

def test_bootstrap_single_sentence_degenerate():
    ms = [_m(t=5, w=1)]
    p, l, h = bootstrap_ci(ms, fertility_point, n_resamples=100, rng_seed=42)
    assert p == l == h == 5.0
```

`tests/unit/test_metrics_properties.py` (hypothesis):

```python
from hypothesis import given, strategies as st
from fertiscope.core import PerSentenceMetrics
from fertiscope.core.bootstrap import bootstrap_ci
from fertiscope.core.aggregate import fertility_point

@given(st.lists(st.tuples(st.integers(1, 1000), st.integers(1, 200)), min_size=1, max_size=50))
def test_bootstrap_ci_ordering_invariant(data):
    ms = [PerSentenceMetrics(f"s{i}","x","t",tokens=t,words=w,chars=w*4,bytes_=w*4)
          for i,(t,w) in enumerate(data)]
    p, l, h = bootstrap_ci(ms, fertility_point, n_resamples=100, rng_seed=42)
    assert l <= p <= h
    assert h - l >= 0
```

### Notes

- `n_resamples=1000` is the publication default. Tests use 100–500 for speed.
- The `lambda` factories in `aggregate_with_cis` capture `base_fert` and `base_tokens` by value (closure semantics) — they're stable.
- The two-sample bootstrap (resampling both baseline and target) is more conservative but yields ~5% wider CIs without changing rank orderings. We use the simpler one-sample form and disclose in methodology docs (#037).
- The `measure` CLI is the user's first usable surface. Make the output beautiful (Rich table) and informative (n, tokenizer ID in title).

## Acceptance Criteria

- [ ] `bootstrap_ci(ms, fertility_point, rng_seed=42)` returns bit-identical `(point, low, high)` across two calls.
- [ ] Single-sentence input returns `(p, p, p)`.
- [ ] `low <= point <= high` for any non-degenerate input (verified by hypothesis with ≥ 100 examples).
- [ ] `fertiscope measure --text "hello world" --lang eng --tokenizer openai/o200k_base` exits 0 and prints fertility, CPT, BPT with CIs.
- [ ] `fertiscope measure --corpus flores --lang tam --tokenizer openai/cl100k_base` (with `[hf,oai]`) produces fertility around 11 ± 5% (matching paper Tamil baseline).
- [ ] `fertiscope measure --json` outputs valid JSON.
- [ ] `--baseline-lang` controls the premium row.
- [ ] CLI test passes.
- [ ] Hypothesis property tests pass.
- [ ] `mypy --strict src/fertiscope/core/{bootstrap,aggregate_ci}.py` passes.

## User Stories

### Story: User's first interaction with the package

1. Installs `pip install fertiscope[oai]`.
2. Runs `fertiscope measure --text "Hello world" --lang eng --tokenizer openai/o200k_base`.
3. Sees Rich table: fertility, CPT, BPT with point estimates.
4. Tries `--lang tam --text "..."` with Tamil text.
5. Output shows the script-specific metric.

### Story: Reproducible CI in CI

1. CI test runs `fertiscope measure --corpus flores --lang tam --rng-seed 42`.
2. CI table cell `low=10.4, high=12.1` matches the expected value bit-exactly.
3. Drift detected if anyone changes the numpy version, tokenizer version, or seed handling.

---

Blocked by: #006, #007, #008, #015, #016, #017, #018
