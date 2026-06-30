# asia-fertility — Usage

> Tokenizer fertility, cost, recall and latency analyzer for 16 lower-resource Asian languages.

This document is the long-form CLI + Python reference. The README has the elevator pitch and the headline findings; everything below is operational.

## Install

```bash
pip install asia-fertility                          # core: tiktoken + HF + lookup
pip install "asia-fertility[oai]"                   # + tiktoken backend (default)
pip install "asia-fertility[hf]"                    # + Hugging Face tokenizers + corpus loaders
pip install "asia-fertility[api]"                   # + Claude / Gemini count-only adapters
pip install "asia-fertility[niah]"                  # + httpx + tenacity for the NIAH benchmark
pip install "asia-fertility[viz]"                   # + matplotlib / pandas / pyarrow for figures
pip install "asia-fertility[dev]"                   # + pytest, ruff, mypy, hypothesis
pip install "asia-fertility[oai,hf,niah,viz]"       # the everything-but-API combo
```

Python `>=3.11`. CPU only.

## Three things you can do offline (no API keys)

```bash
# 1. Sanity-check tokenizer behaviour on the bundled 10×16 parallel suite
asia-fertility reproduce

# 2. Look up NIAH recall + cost for a deployment decision
asia-fertility niah lookup --lang tam --context 32768 --with-cost

# 3. Measure your own text
asia-fertility measure --text "தமிழ் ஒரு செம்மொழி" --lang tam --tokenizer openai/o200k_base
```

## Three things that need keys

```bash
# Re-run the full leaderboard (FLORES-200 download from HF; gated for some tokenizers)
asia-fertility run --config configs/study_main.yaml --hf-token "$HF_TOKEN"

# Re-run the 4000-cell NIAH benchmark (OpenRouter)
asia-fertility niah run --config configs/niah_v03.yaml --yes

# Re-run the 800-trial latency benchmark (OpenRouter)
asia-fertility latency run --config configs/latency_main.yaml --yes
```

## CLI reference

### `measure`

Compute fertility / premium / CPT / BPT for arbitrary text or a corpus slice, with bootstrap 95% CIs.

```bash
asia-fertility measure --text "Xin chào" --lang vie --tokenizer openai/o200k_base
asia-fertility measure --corpus flores --lang tam --tokenizer openai/cl100k_base --n-sentences 100
asia-fertility measure --path my.jsonl --corpus custom --lang khm --tokenizer mistral/tekken --json
```

Flags: `--text`, `--corpus`, `--path`, `--lang`, `--tokenizer`, `--baseline-lang`, `--n-sentences`, `--n-resamples`, `--rng-seed`, `--json`.

### `cost`

Per-model cost estimate (input + output) for representative content. Uses the bundled `prices_2026-06.yaml` snapshot.

```bash
asia-fertility cost \
  --text "Àwọn ará Nàìjíríà" --lang yor \
  --models openai/gpt-4o-mini,google/gemini-2.5-flash,deepseek/deepseek-chat-v3-0324 \
  --currencies USD
```

Unknown model IDs get close-match suggestions (difflib) instead of a stack trace.

### `run`

Full leaderboard study from a YAML config. Writes `results.{csv,json,parquet}`, `leaderboard.json`, `manifest.json` to `runs/<name>/`.

```bash
asia-fertility run --config configs/study_main.yaml
asia-fertility run --config configs/study_test.yaml --output-dir /tmp/smoke
```

### `figures`

Regenerate the 8 paper figures from a run.

```bash
asia-fertility figures \
  --run runs/main \
  --out runs/main/figures \
  --niah-run runs/niah/v03 \
  --latency-run runs/latency/main
```

### `leaderboard`

Emit the schema-versioned leaderboard JSON (consumed by [fertiscope.vercel.app](https://fertiscope.vercel.app)).

```bash
asia-fertility leaderboard --run runs/main --out runs/main/leaderboard.json
```

### `reproduce`

Run all locally-installed tokenizers against the bundled 160-sentence parallel suite. Zero network.

```bash
asia-fertility reproduce
asia-fertility reproduce --tokenizers openai/o200k_base,bigscience/bloom
asia-fertility reproduce --json
```

### `tokenizers list`

```bash
asia-fertility tokenizers list
asia-fertility tokenizers list --available-only --json
asia-fertility tokenizers list --family openai
```

### `corpora list` / `languages list`

```bash
asia-fertility corpora list
asia-fertility languages list
```

### `models`

Canonical model registry — pricing, native + sizing tokenizer, OpenRouter route, benchmark coverage. Single source of truth.

```bash
asia-fertility models list                       # everything
asia-fertility models list --benchmarked-only    # only the 5 in NIAH/latency
asia-fertility models list --family google
asia-fertility models list --json
asia-fertility models show google/gemini-2.5-flash
```

### `niah`

Multi-turn needle-in-haystack benchmark with script-native markers.

```bash
asia-fertility niah run --config configs/niah_v03.yaml --yes
asia-fertility niah report --output-dir runs/niah/v03
asia-fertility niah lookup --lang tam --context 32768                # offline lookup
asia-fertility niah lookup --lang mya --context 131072 --with-cost   # join with prices
```

### `latency`

Wall-clock streaming latency benchmark with prefix-cache evasion.

```bash
asia-fertility latency run --config configs/latency_main.yaml --yes
asia-fertility latency report --output-dir runs/latency/main
```

## Python API

```python
from asia_fertility import __version__
from asia_fertility.tokenizers import get_tokenizer, list_tokenizers, is_available
from asia_fertility.corpora import load_corpus
from asia_fertility.core import per_sentence
from asia_fertility.core.aggregate_ci import aggregate_with_cis
from asia_fertility.cost import cost_of
from asia_fertility.registry import load_registry
from asia_fertility.study.reproduce import reproduce_suite
from asia_fertility.config import StudyConfig
from asia_fertility.study.runner import run_study

# Quick measurement
tok = get_tokenizer("openai/o200k_base")
n = tok.count("தமிழ் ஒரு செம்மொழி")  # 7

# Cost for one text on multiple models
rows = cost_of("Xin chào", models=["openai/gpt-4o-mini", "google/gemini-2.5-flash"])

# Registry lookups (offline)
reg = load_registry()
rec = reg.get("google/gemini-2.5-flash")
print(rec.input_price_per_1m, rec.context_window, rec.benchmarked_in)

# Offline reference suite
suite = reproduce_suite(tokenizer_ids=["openai/o200k_base"])

# Full study from YAML
cfg = StudyConfig.from_yaml("configs/study_main.yaml")
result = run_study(cfg)
```

## Benchmarks — input and output schemas

### Leaderboard run (`runs/<name>/results.csv`)
One row per `(lang, tokenizer, corpus)`. Columns: `iso, lang, script, family, tokenizer, n_sentences, fertility, fertility_ci_low, fertility_ci_high, premium, premium_ci_low, premium_ci_high, cost_ratio, cost_ratio_ci_low, cost_ratio_ci_high, cpt, cpt_ci_low, cpt_ci_high, bpt, bpt_ci_low, bpt_ci_high, skip_reason`.

### NIAH run (`runs/niah/<name>/results.csv`)
One row per `(model, lang, fill_tokens, position_pct, trial)`. Columns: `model, lang, iso, script, fill_tokens, position_pct, trial, marker, actual_tokens, marker_position_tokens, response, recalled, error, elapsed_seconds`.

Resume key: `(model, iso, fill_tokens, position_pct, trial)` — interrupted runs continue without re-billing OpenRouter.

### Latency run (`runs/latency/<name>/results.csv`)
One row per `(model, lang, trial, is_warmup)`. Columns: `model, iso, script, trial, is_warmup, prompt_chars, ttft_ms, total_ms, output_chars, error`.

Drop `is_warmup == True` before analysis.

## Where the data lives

- **HuggingFace**: [Helmo21/asia-fertility](https://huggingface.co/datasets/Helmo21/asia-fertility) — three configs (`leaderboard`, `niah`, `latency`).
- **Bundled in the wheel** (`_defaults/`): `prices_2026-06.yaml`, `fx_2026-06.yaml`, `niah_recall_2026-06.json`, `models_2026-06.yaml`, `reference_suite/reference.jsonl`. The CLI works offline using these defaults.

## Adding your own

- New tokenizer → see [`adding_a_tokenizer.md`](adding_a_tokenizer.md).
- New corpus → subclass `asia_fertility.corpora.base.Corpus`, register via `asia_fertility.corpora.registry.register()`.
- New language → append to `src/asia_fertility/data/languages.yaml`.
- New model in cost / registry → edit `src/asia_fertility/_defaults/models_2026-06.yaml` and re-run `tests/unit/test_model_id_sync.py`.
