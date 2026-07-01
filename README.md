# asia-fertility 🌏

**The hidden multilingual tax in your tokenizer — measured before you deploy.**

[![PyPI](https://img.shields.io/pypi/v/asia-fertility.svg?color=blue)](https://pypi.org/project/asia-fertility/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21069313.svg)](https://doi.org/10.5281/zenodo.21069313)
[![CI](https://github.com/Helmo21/asia-fertility/actions/workflows/ci.yml/badge.svg)](https://github.com/Helmo21/asia-fertility/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![HF Dataset](https://img.shields.io/badge/HF-Helmo21%2Fasia--fertility-ffd21e)](https://huggingface.co/datasets/Helmo21/asia-fertility)
[![Website](https://img.shields.io/badge/Website-fertiscope.vercel.app-orange)](https://fertiscope.vercel.app)

`asia-fertility` measures the structural penalty that LLM tokenizers impose on lower-resource Asian languages. The same content can cost up to **11.7× more tokens in Burmese than in English** on a frontier tokenizer — silent inflation of API bills, smaller usable context windows, and — as we show via a 4 000-cell needle-in-haystack benchmark — measurably worse retrieval on script-native content.

```
$ asia-fertility reproduce --tokenizers openai/o200k_base

  asia-fertility reproduce · openai/o200k_base
  (offline reference suite, 10 sents × 16 langs)
  ─────────────────────────────────────────────
  Lang   Fertility   Premium × eng
  lao       38.167          28.90×
  tha       11.490           8.70×
  khm       11.047           8.37×
  mya        7.319           5.54×
  sin        3.447           2.61×
  tam        3.360           2.54×
  ...
  eng        1.321           1.00×
```

No network, no API keys. The full leaderboard adds bootstrap CIs, BPT, cost ratios, NIAH recall, and wall-clock latency.

---

## Install

```bash
pip install asia-fertility                          # core: registry + offline lookup
pip install "asia-fertility[oai]"                   # + tiktoken (OpenAI vocabs)
pip install "asia-fertility[hf]"                    # + HuggingFace tokenizers + corpora
pip install "asia-fertility[api]"                   # + Anthropic/Gemini count-only adapters
pip install "asia-fertility[niah]"                  # + httpx + tenacity for NIAH benchmark
pip install "asia-fertility[viz]"                   # + matplotlib / pandas / pyarrow
pip install "asia-fertility[dev]"                   # + test toolchain
pip install "asia-fertility[oai,hf,niah,viz]"       # the everything-but-API combo
```

Requires Python 3.11+. CPU only. For HF-gated tokenizers (Llama, Gemma, Aya), export `HF_TOKEN`. For NIAH / latency, export `OPENROUTER_API_KEY`.

---

## Quickstart

```bash
# 1. Sanity check (offline; no keys; 5 seconds)
asia-fertility reproduce

# 2. Measure your own text
asia-fertility measure --text "தமிழ் ஒரு செம்மொழி" --lang tam --tokenizer openai/o200k_base

# 3. Compare cost across providers
asia-fertility cost --text "Xin chào" --lang vie \
  --models openai/gpt-4o-mini,google/gemini-2.5-flash,deepseek/deepseek-chat-v3-0324 \
  --currencies USD,VND

# 4. Pick a model for a deployment scenario (joins NIAH recall + price)
asia-fertility niah lookup --lang tam --context 32768 --with-cost
```

The `niah lookup --with-cost` output (the package's killer surface):

```
NIAH recall · lang=tam · context≤32768 (nearest fill = 32768)
Model                              Recall      Errors  In $/1M  Out $/1M  Approx cost (this prompt)
google/gemini-2.5-flash            90% (9/10)  0       $0.30    $2.50     $0.010080
deepseek/deepseek-chat-v3-0324      0% (0/10)  0       $0.27    $1.10     $0.008957
meta-llama/llama-3.1-8b-instruct    0% (0/10)  0       $0.06    $0.06     $0.001972
openai/gpt-4o-mini                  0% (0/10)  0       $0.15    $0.60     $0.004975
qwen/qwen-2.5-7b-instruct           0% (0/10)  10      $0.06    $0.18     $0.001984
```

At 32 k tokens of Tamil, only `gemini-2.5-flash` retrieves a script-native marker. The other four models cost less per token — and score 0/10. **The cheaper option isn't cheaper if the model can't use the context.**

---

## CLI reference

| Command | What it does |
|---|---|
| `asia-fertility measure` | Token count + fertility + premium + CPT + BPT with bootstrap 95% CIs |
| `asia-fertility cost` | Cost per (model, language) for a representative input; multi-currency |
| `asia-fertility run` | Full leaderboard study from a YAML config |
| `asia-fertility figures` | Regenerate the 8 paper figures from a study run |
| `asia-fertility leaderboard` | Emit schema-versioned leaderboard JSON |
| `asia-fertility reproduce` | Offline 10×16 reference suite — zero network |
| `asia-fertility tokenizers list` | Registry of all 12 tokenizers + availability |
| `asia-fertility corpora list` | Registered corpus loaders |
| `asia-fertility languages list` | All 16 study languages with ISO codes + scripts |
| `asia-fertility models list` | Canonical model registry — pricing + benchmark coverage |
| `asia-fertility models show <id>` | Full per-model card (pricing, tokenizer, routes, notes) |
| `asia-fertility niah run / report / lookup` | 4 000-cell needle-in-haystack benchmark + bundled offline lookup |
| `asia-fertility latency run / report` | 800-trial wall-clock streaming latency benchmark |

Long-form reference: [`docs/usage.md`](docs/usage.md). Adding a new tokenizer: [`docs/adding_a_tokenizer.md`](docs/adding_a_tokenizer.md).

---

## Python API

```python
from asia_fertility import __version__
from asia_fertility.tokenizers import get_tokenizer, list_tokenizers, is_available
from asia_fertility.cost import cost_of
from asia_fertility.registry import load_registry
from asia_fertility.study.reproduce import reproduce_suite
from asia_fertility.study.runner import run_study
from asia_fertility.config import StudyConfig

# Token-count a single string
tok = get_tokenizer("openai/o200k_base")
n = tok.count("தமிழ் ஒரு செம்மொழி")

# Cost on multiple models for the same text
rows = cost_of("Xin chào", models=["openai/gpt-4o-mini", "google/gemini-2.5-flash"])

# Canonical model registry — offline
reg = load_registry()
rec = reg.get("google/gemini-2.5-flash")
print(rec.input_price_per_1m, rec.context_window, rec.benchmarked_in)

# Run the offline reference suite (no network)
rows = reproduce_suite(tokenizer_ids=["openai/o200k_base", "bigscience/bloom"])

# Full leaderboard study from YAML
cfg = StudyConfig.from_yaml("configs/study_main.yaml")
result = run_study(cfg)
```

---

## Metrics

All metrics are computed on **parallel corpora** (same meaning, different languages) so the language effect is isolated from content. Aggregation is **sum-then-divide** over sentences (not mean-of-ratios) — Jensen's inequality matters here. Bootstrap 95% CIs over sentences. Baseline: English. Normalization: NFC.

| Metric | Formula | Meaning |
|---|---|---|
| **Fertility** `F(L,T)` | `Σ tokens / Σ words` | Tokens per word. Lower = more efficient. |
| **Premium** `P(L,T)` | `F(L,T) / F(eng,T)` | How many times more tokens L uses vs English on the same tokenizer. |
| **Same-content cost ratio** | `Σ t_iˡ / Σ t_iᵉⁿᵍ` | Segmenter-independent bill ratio. Governs the API cost at constant per-token pricing. |
| **CPT** | `Σ chars / Σ tokens` | Characters packed per token. |
| **BPT** | `Σ utf8_bytes / Σ tokens` | Bytes per token — the only cross-script-fair comparator (UTF-8 charges proportionally to codepoint width). |

---

## Supported tokenizers

| Tokenizer ID | Backend | Notes |
|---|---|---|
| `openai/o200k_base` | tiktoken | GPT-4o / GPT-4.1 / o-series / GPT-5 |
| `openai/o200k_harmony` | tiktoken | OpenAI open-weight (gpt-oss family) |
| `openai/cl100k_base` | tiktoken | GPT-3.5 / GPT-4 (legacy) |
| `meta/llama-3.1` | HF (gated) | Llama 3 family + SEA-LION v3 |
| `mistral/tekken` | HF | Mistral Tekken |
| `qwen/qwen3` | HF | Qwen 3 |
| `deepseek/v3` | HF | DeepSeek V3 |
| `bigscience/bloom` | HF | Multilingual baseline (BLOOM) |
| `google/gemma-2` | HF (gated) | Gemma 2 |
| `cohere/aya-expanse` | HF (gated) | Multilingual-optimized baseline |
| `anthropic/claude` | API count-only | Needs `ANTHROPIC_API_KEY`; sizing for cost falls back to `o200k_base` |
| `google/gemini` | API count-only | Needs `GEMINI_API_KEY`; sizing for cost falls back to `o200k_base` |

Unavailable tokenizers are skipped with a `skip_reason` row rather than crashing a study. See [`docs/adding_a_tokenizer.md`](docs/adding_a_tokenizer.md).

---

## Supported languages

16 languages across 6 scripts and 5 language families:

| Tier | Languages |
|---|---|
| **Baseline** | English (`eng`, Latin) |
| **Latin-script Asian** | Vietnamese (`vie`), Indonesian (`ind`), Malay (`zsm`), Filipino (`tgl`) |
| **Brahmic — Indic** | Hindi (`hin`, Devanagari), Bengali (`ben`), Sinhala (`sin`), Tamil (`tam`), Telugu (`tel`), Kannada (`kan`), Malayalam (`mal`) |
| **Brahmic — Mainland Southeast Asia** | Thai (`tha`), Burmese (`mya`), Khmer (`khm`), Lao (`lao`) |

```bash
asia-fertility languages list
```

---

## Project structure

```
asia-fertility/
├── src/asia_fertility/
│   ├── core/             # segmentation · metrics · bootstrap CIs · NFC normalize
│   ├── tokenizers/       # tiktoken + HF + API adapters + lazy registry
│   ├── corpora/          # FLORES-200 + custom JSONL/CSV
│   ├── cost/             # cost model · pinned price + FX snapshots
│   ├── study/            # study runner + manifest + writers + offline reproduce
│   ├── report/           # 8 paper figures + leaderboard JSON
│   ├── niah/             # 4 000-cell needle-in-haystack benchmark
│   ├── latency/          # streaming wall-clock latency benchmark
│   ├── registry.py       # canonical model registry (single source of truth)
│   ├── languages.py      # 16-language definitions
│   ├── config.py         # pydantic StudyConfig
│   └── cli.py            # typer CLI (11 top-level commands)
├── src/asia_fertility/_defaults/
│   ├── prices_2026-06.yaml         # pinned per-model pricing snapshot
│   ├── fx_2026-06.yaml             # pinned FX rates for multi-currency cost
│   ├── models_2026-06.yaml         # canonical model registry data
│   ├── niah_recall_2026-06.json    # bundled NIAH summary (queryable via `niah lookup`)
│   └── reference_suite/            # 10×16 offline suite for `reproduce`
├── configs/              # locked study + niah + latency configs
├── data/                 # 16-language registry · reference suite seed
├── docs/                 # usage · adding_a_tokenizer
├── paper/                # LaTeX source + compiled PDF (14 pp) + figures
├── runs/                 # checked-in results: main / niah/v03 / latency/main
└── tests/                # unit + golden + integration
```

---

## Three benchmarks

| Benchmark | Grid | Size | Output |
|---|---|---|---|
| **Leaderboard** | 16 langs × 10 tokenizers × FLORES-200 dev | 160 rows | `runs/main/results.{csv,json,parquet}` + leaderboard JSON |
| **NIAH** (multi-turn recall) | 16 langs × 5 models × 5 fills (4k→131k) × 5 positions × 2 trials | **4 000 cells** | `runs/niah/v03/results.csv` + `niah_report.json` |
| **Latency** (wall-clock streaming) | 16 langs × 5 models × 10 trials (+ 3 warmup) | **800 measured** (1 040 total HTTP) | `runs/latency/main/results.csv` |

---

## Key findings (paper §4)

- Same content costs **7–12× more tokens** on `cl100k_base` for Brahmic-derived scripts (Tamil 7.61×, Burmese 11.66×). Switching to `o200k_base` cuts the penalty 3–6×.
- **Gemma-2 is the best open-weight tokenizer for South-Asian** workloads (Tamil 2.58×, Burmese 4.80×). **BLOOM** dominates Indic scripts (Tamil 1.29×).
- **NIAH recall is script-driven, not depth-driven**, on 4 of 5 frontier models tested (gpt-4o-mini, llama-3.1-8b, qwen-2.5-7b, deepseek-v3): non-Latin recall collapses to 0–2/10 already at 4 k context. The exception is **gemini-2.5-flash, which holds 76–96% recall across all 16 languages and all 5 fills (4k → 131k)** — so the collapse is a vendor-level training choice, not a fundamental limit. Pooled recall across the 4 000 cells: 36.2%. See paper §4.4.
- **"Effective context window" is language-dependent**: deepseek-v3's nominal 128 k window recalls cleanly at 131 k on Latin scripts but errors with HTTP 400 on 100% of high-fertility Brahmic-script haystacks at the same notional size (Brahmic fertility blows the prompt past the model's window).
- **Cost is NOT a reliable proxy for UX impact**: Pearson r between cost ratio and latency ratio = **0.314** pooled across 75 (model, lang) cells; per-model r ranges from −0.19 (qwen) to +0.74 (llama). The relationship is a property of the provider's serving stack (continuous batching, prefill parallelism), not of the language. See paper §4.5.

---

## Reproducing the paper numbers

```bash
git clone https://github.com/Helmo21/asia-fertility
cd asia-fertility
pip install -e ".[oai,hf,niah,viz,dev]"

# Offline sanity check (no keys, ~5 sec)
asia-fertility reproduce

# Full leaderboard (needs HF_TOKEN for gated tokenizers)
export HF_TOKEN=hf_...
asia-fertility run --config configs/study_main.yaml
asia-fertility figures --run runs/main --out runs/main/figures \
  --niah-run runs/niah/v03 --latency-run runs/latency/main
asia-fertility leaderboard --run runs/main --out runs/main/leaderboard.json

# NIAH + Latency (needs OPENROUTER_API_KEY; ~$30, ~30 min)
export OPENROUTER_API_KEY=sk-or-...
asia-fertility niah run --config configs/niah_v03.yaml --yes
asia-fertility latency run --config configs/latency_main.yaml --yes
```

All tokenizer versions, price snapshot date, FX rates, and config hash are recorded in each `runs/*/manifest.json`. The drift gate (`tests/unit/test_model_id_sync.py`) ensures every model ID in a benchmark config / run CSV / paper / bundled summary stays registered.

---

## Paper

Preprint on Zenodo: **[10.5281/zenodo.21069313](https://doi.org/10.5281/zenodo.21069313)** — full writeup at [`paper/paper.pdf`](paper/paper.pdf) (15 pp). Cite as:

```bibtex
@article{pedretti2026asianlanguagetax,
  title  = {The Asian Language Tax: Quantifying the Cost, Context, and Recall Penalty of Tokenizing Lower-Resource Asian Languages in Frontier LLMs},
  author = {Pedretti, Antoine},
  year   = {2026},
  doi    = {10.5281/zenodo.21069313},
  url    = {https://doi.org/10.5281/zenodo.21069313},
}
```

A machine-readable [`CITATION.cff`](CITATION.cff) is included; GitHub renders a "Cite this repository" button.

---

## Data

All three benchmarks are published as a HuggingFace dataset with separate configs:

```python
from datasets import load_dataset

ds   = load_dataset("Helmo21/asia-fertility", "leaderboard")  # cost + BPT leaderboard
niah = load_dataset("Helmo21/asia-fertility", "niah")          # 4 000 recall cells
lat  = load_dataset("Helmo21/asia-fertility", "latency")       # 800 wall-clock measurements
```

The bundled defaults (`_defaults/{prices,fx,models,niah_recall,reference_suite}`) ship inside the wheel — so `asia-fertility reproduce`, `niah lookup`, and `models list/show` all work without network.

---

## License

MIT © 2026 Antoine Pedretti. Bundled FLORES-200 data: CC-BY-SA 4.0 (Meta NLLB).
