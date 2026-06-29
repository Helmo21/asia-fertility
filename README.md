# asia-fertility 🌏

**The hidden multilingual tax in your tokenizer — measured before you deploy.**

[![PyPI](https://img.shields.io/pypi/v/asia-fertility.svg?color=blue)](https://pypi.org/project/asia-fertility/)
[![CI](https://github.com/Helmo21/asia-fertility/actions/workflows/ci.yml/badge.svg)](https://github.com/Helmo21/asia-fertility/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![HF Dataset](https://img.shields.io/badge/HF-Helmo21%2Fasia--fertility-ffd21e)](https://huggingface.co/datasets/Helmo21/asia-fertility)

`asia-fertility` measures the structural cost penalty that LLM tokenizers impose on lower-resource Asian languages along **three independent dimensions**: dollar cost (per-token billing), context capacity (window exhaustion), and now in v0.3, **wall-clock latency** (UX impact). The same content can cost up to **11× more tokens in Burmese than in English** on a frontier tokenizer — silent inflation of API bills, smaller usable context windows, and fewer in-context examples.

## Quickstart

```bash
pip install "asia-fertility[oai,hf,niah,viz]"   # or: uv tool install
source .env                                      # OPENROUTER_API_KEY + HF_TOKEN

# Measure your own text
asia-fertility measure --text "தமிழ் ஒரு செம்மொழி" --lang tam --tokenizer openai/o200k_base

# Compare cost across providers (in your local currency)
asia-fertility cost --text "Xin chào" --lang vie \
  --models openai/gpt-4o,openai/gpt-3.5-turbo \
  --currencies USD,VND

# Reproduce the full 16-language × 10-tokenizer leaderboard
asia-fertility run --config configs/study_main.yaml
asia-fertility figures --run runs/main --out runs/main/figures
asia-fertility leaderboard --run runs/main --out runs/main/leaderboard.json

# NEW in v0.3 — measure wall-clock latency penalty per (model × language)
asia-fertility latency run --config configs/latency_main.yaml --yes
asia-fertility latency report --output-dir runs/latency/main
```

## Three benchmarks

| Benchmark | What it measures | Cost | Time |
|---|---|---|---|
| **A — Leaderboard** | Same-content cost ratio + bytes/token across 16 langs × 10 tokenizers on FLORES-200 | $0 (no LLM calls) | ~2 min |
| **B — NIAH multi-turn** | Script-native needle-in-haystack recall across 3 frontier models × Tamil/Hindi/Burmese/Lao at 4 k/16 k/32 k contexts | ~$2 on OpenRouter | ~2 h |
| **C — Latency** *(NEW in v0.3)* | Wall-clock penalty (TTFT + total) across 5 models × 16 langs with prefix-cache evasion | ~$0.20 | ~30 min |

## What's inside

- **16 lower-resource Asian languages**: Vietnamese, Indonesian, Malay, Filipino, Thai, Hindi, Bengali, Sinhala, Tamil, Telugu, Kannada, Malayalam, Burmese, Khmer, Lao, plus English baseline.
- **10 tokenizers measured**: OpenAI `o200k_base`/`cl100k_base`/`o200k_harmony`, Mistral Tekken, Qwen3, DeepSeek v3, BLOOM, Gemma-2, Aya Expanse, Llama-3.1. 2 more registered as count-only (Anthropic Claude, Google Gemini APIs).
- **5 metrics** with 95% bootstrap CIs: fertility, premium, same-content cost ratio, characters/token (CPT), and **bytes/token (BPT)** — the only cross-script-fair comparator.
- **NIAH benchmark** (Benchmark B): script-native marker recall across `gpt-4o-mini`, `gpt-3.5-turbo`, `llama-3.1-8b-instruct` on Tamil/Hindi/Burmese/Lao haystacks at 4 k–32 k context. 540 calls.
- **Latency benchmark** (Benchmark C, v0.3+): streaming-TTFT wall-clock timing across `gpt-4o-mini`, `llama-3.1-8b-instruct`, `gemini-2.5-flash`, `qwen-2.5-7b-instruct`, `deepseek-chat-v3-0324` × 16 languages, 3 warmup + 10 trials per cell, distinct FLORES prompts to defeat provider-side prefix caching. 1 240 measured calls.

## Key findings

### v0.2 — cost + recall

- Same content costs **7–12× more tokens** on cl100k_base for Brahmic-derived scripts (Tamil 7.61×, Burmese 11.66×).
- Switching to `o200k_base` cuts the penalty 3–6× (Tamil → 1.98×, Burmese → 3.18×).
- **Gemma-2 is the best open-weight tokenizer for South Asian** workloads (Tamil 2.58×, Burmese 4.80×).
- **NIAH recall collapses to 0–7%** on Hindi/Tamil/Burmese/Lao with script-native markers, *even at 4 k context* — across all three frontier models tested. See paper §4.4.

### v0.3 — latency (new)

- **Cost is NOT a reliable proxy for UX impact**: Pearson r between cost ratio and latency ratio = **0.314** across 75 (model, lang) cells. Burmese costs 11.66× more in tokens but takes only ~1.65× longer to respond.
- The relationship is **a property of the provider's serving stack**, not of the language. Per-model Pearson r: llama-3.1-8b +0.74, gemini-2.5-flash +0.52, gpt-4o-mini +0.43, deepseek-v3 +0.05, qwen-2.5-7b −0.19.
- Modern continuous-batching inference (visible in Gemini-Flash and DeepSeek) absorbs most input-side fertility penalty before reaching wall-clock time.
- Contradicts the r ≈ 0.94 finding reported by [afri-fertility](https://github.com/CipherSenseAI/afri-fertility) (Somide 2026). See paper §4.5.

## Paper

The full writeup is at [`paper/paper.pdf`](paper/paper.pdf) (12 pages, v0.3). Cite as:

```bibtex
@misc{pedretti2026asianlanguagetax,
  title  = {The Asian Language Tax: Quantifying the Cost, Context, and Recall Penalty of Tokenizing Lower-Resource Asian Languages in Frontier LLMs},
  author = {Pedretti, Antoine},
  year   = {2026},
  url    = {https://github.com/Helmo21/asia-fertility},
}
```

## Data

All three benchmarks are published as a HuggingFace dataset with separate configs:

```python
from datasets import load_dataset

# Benchmark A — main leaderboard (1 row per language × tokenizer × corpus)
ds   = load_dataset("Helmo21/asia-fertility", "leaderboard")

# Benchmark B — NIAH multi-turn recall (1 row per model × lang × fill × position × trial)
niah = load_dataset("Helmo21/asia-fertility", "niah")

# Benchmark C — wall-clock latency (1 row per model × lang × trial)
lat  = load_dataset("Helmo21/asia-fertility", "latency")
```

Each version (`v0.2.0/`, `v0.3.0/`, …) is preserved so older paper figures stay reproducible.

## License

MIT © 2026 Antoine Pedretti. Bundled FLORES-200 data: CC-BY-SA 4.0 (Meta NLLB).
