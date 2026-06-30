# asia-fertility 🌏

**The hidden multilingual tax in your tokenizer — measured before you deploy.**

[![PyPI](https://img.shields.io/pypi/v/asia-fertility.svg?color=blue)](https://pypi.org/project/asia-fertility/)
[![CI](https://github.com/Helmo21/asia-fertility/actions/workflows/ci.yml/badge.svg)](https://github.com/Helmo21/asia-fertility/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![HF Dataset](https://img.shields.io/badge/HF-Helmo21%2Fasia--fertility-ffd21e)](https://huggingface.co/datasets/Helmo21/asia-fertility)

`asia-fertility` measures the structural penalty that LLM tokenizers impose on lower-resource Asian languages. The same content can cost up to **11.7× more tokens in Burmese than in English** on a frontier tokenizer — silent inflation of API bills, smaller usable context windows, and fewer in-context examples.

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

# Reproduce the full leaderboard
asia-fertility run --config configs/study_main.yaml
asia-fertility figures --run runs/main --out runs/main/figures
asia-fertility leaderboard --run runs/main --out runs/main/leaderboard.json

# Multi-turn needle-in-haystack benchmark
asia-fertility niah run --config configs/niah_main.yaml --yes
asia-fertility niah report --output-dir runs/niah/main

# Wall-clock latency benchmark
asia-fertility latency run --config configs/latency_main.yaml --yes
asia-fertility latency report --output-dir runs/latency/main
```

## What's inside

- **16 lower-resource Asian languages**: Vietnamese, Indonesian, Malay, Filipino, Thai, Hindi, Bengali, Sinhala, Tamil, Telugu, Kannada, Malayalam, Burmese, Khmer, Lao, plus English baseline.
- **10 tokenizers**: OpenAI `o200k_base`/`cl100k_base`/`o200k_harmony`, Mistral Tekken, Qwen3, DeepSeek v3, BLOOM, Gemma-2, Aya Expanse, Llama-3.1. Anthropic Claude and Google Gemini registered as count-only.
- **5 metrics** with 95% bootstrap CIs: fertility, premium, same-content cost ratio, characters/token (CPT), and **bytes/token (BPT)** — the only cross-script-fair comparator.
- **Three benchmarks**:
  - **Leaderboard** — same-content cost ratio + BPT across 16 langs × 10 tokenizers on FLORES-200.
  - **NIAH multi-turn recall** — script-native needle-in-haystack across 5 frontier models × 16 languages × 5 fill levels (4k–131k) × 5 marker positions × 2 trials = **4 000 cells** on OpenRouter.
  - **Wall-clock latency** — streaming-TTFT timing across 5 models × 16 languages × 10 trials (+3 warmup) = **800 measured trials** with prefix-cache evasion.

## Key findings

- Same content costs **7–12× more tokens** on cl100k_base for Brahmic-derived scripts (Tamil 7.61×, Burmese 11.66×). Switching to `o200k_base` cuts the penalty 3–6×.
- **Gemma-2 is the best open-weight tokenizer for South Asian** workloads (Tamil 2.58×, Burmese 4.80×). **BLOOM** dominates Indic scripts (Tamil 1.29×).
- **NIAH recall is script-driven, not depth-driven**, on 4 of 5 frontier models (gpt-4o-mini, llama-3.1-8b, qwen-2.5-7b, deepseek-v3): non-Latin recall collapses to 0–2/10 already at 4 k context. The exception is **gemini-2.5-flash, which holds 76–96% recall across all 16 languages and all 5 fills (4k → 131k)** — so the collapse is a vendor-level training choice, not a fundamental limit. Pooled recall across the 4 000 cells: 36.2%. See paper §4.4.
- **"Effective context window" is language-dependent**: deepseek-v3's nominal 128k window recalls cleanly at 131k on Latin scripts but errors with HTTP 400 on 100% of high-fertility Brahmic-script haystacks at the same notional size (Brahmic fertility blows the prompt past the model's window).
- **Cost is NOT a reliable proxy for UX impact**: Pearson r between cost ratio and latency ratio = **0.314** pooled across 75 (model, lang) cells; per-model r ranges from −0.19 (qwen) to +0.74 (llama). The relationship is a property of the provider's serving stack (continuous batching, prefill parallelism), not of the language. See paper §4.5.

## Paper

Full writeup at [`paper/paper.pdf`](paper/paper.pdf). Cite as:

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

ds   = load_dataset("Helmo21/asia-fertility", "leaderboard")  # cost + BPT leaderboard
niah = load_dataset("Helmo21/asia-fertility", "niah")          # multi-turn recall cells
lat  = load_dataset("Helmo21/asia-fertility", "latency")       # wall-clock timing cells
```

## License

MIT © 2026 Antoine Pedretti. Bundled FLORES-200 data: CC-BY-SA 4.0 (Meta NLLB).
