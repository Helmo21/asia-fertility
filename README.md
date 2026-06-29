# asia-fertility 🌏

**The hidden multilingual tax in your tokenizer — measured before you deploy.**

[![PyPI](https://img.shields.io/pypi/v/asia-fertility.svg?color=blue)](https://pypi.org/project/asia-fertility/)
[![CI](https://github.com/Helmo21/asia-fertility/actions/workflows/ci.yml/badge.svg)](https://github.com/Helmo21/asia-fertility/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![HF Dataset](https://img.shields.io/badge/HF-Helmo21%2Fasia--fertility-ffd21e)](https://huggingface.co/datasets/Helmo21/asia-fertility)

`asia-fertility` measures the structural cost penalty that LLM tokenizers impose on lower-resource Asian languages. The same content can cost up to **11× more tokens in Burmese than in English** on a frontier tokenizer — silent inflation of API bills, smaller usable context windows, and fewer in-context examples.

## Quickstart

```bash
pip install "asia-fertility[oai]"

# Measure your own text
asia-fertility measure --text "தமிழ் ஒரு செம்மொழி" --lang tam --tokenizer openai/o200k_base

# Compare cost across providers (in your local currency)
asia-fertility cost --text "Xin chào" --lang vie \
  --models openai/gpt-4o,openai/gpt-3.5-turbo \
  --currencies USD,VND

# Reproduce the full 16-language × 9-tokenizer leaderboard
asia-fertility run --config configs/study_main.yaml
asia-fertility figures --run runs/main --out runs/main/figures
asia-fertility leaderboard --run runs/main --out runs/main/leaderboard.json
```

## What's inside

- **16 lower-resource Asian languages**: Vietnamese, Indonesian, Malay, Filipino, Thai, Hindi, Bengali, Sinhala, Tamil, Telugu, Kannada, Malayalam, Burmese, Khmer, Lao, plus English baseline.
- **9 tokenizers measured**: OpenAI `o200k_base`/`cl100k_base`/`o200k_harmony`, Mistral Tekken, Qwen3, DeepSeek v3, BLOOM, Gemma-2, Aya Expanse. 3 more registered behind license walls (Llama-3.1, etc.).
- **5 metrics** with 95% bootstrap CIs: fertility, premium, same-content cost ratio, characters/token (CPT), and **bytes/token (BPT)** — the only cross-script-fair comparator.
- **NIAH benchmark**: script-native needle-in-haystack across gpt-4o-mini, gpt-3.5-turbo, llama-3.1-8b-instruct on Tamil/Hindi/Burmese/Lao haystacks.

## Key findings (v0.2.0)

- Same content costs **7–12× more tokens** on cl100k_base for Brahmic-derived scripts (Tamil 7.61×, Burmese 11.66×).
- Switching to `o200k_base` cuts the penalty 3–6× (Tamil → 1.98×, Burmese → 3.18×).
- **Gemma-2 is the best open-weight tokenizer for South Asian** workloads (Tamil 2.58×, Burmese 4.80×).
- **NIAH recall collapses to 0–7%** on Hindi/Tamil/Burmese/Lao with script-native markers, *even at 4k context* — across all three frontier models tested. See paper §4.4.

## Paper

The full writeup is at [`paper/paper.pdf`](paper/paper.pdf) (11 pages). Cite as:

```bibtex
@misc{pedretti2026asianlanguagetax,
  title  = {The Asian Language Tax: Quantifying the Cost, Context, and Recall Penalty of Tokenizing Lower-Resource Asian Languages in Frontier LLMs},
  author = {Pedretti, Antoine},
  year   = {2026},
  url    = {https://github.com/Helmo21/asia-fertility},
}
```

## Data

The full results leaderboard + NIAH benchmark are published as a HuggingFace dataset:

```python
from datasets import load_dataset

ds   = load_dataset("Helmo21/asia-fertility", "leaderboard")  # 144 (lang × tokenizer) rows
niah = load_dataset("Helmo21/asia-fertility", "niah")          # 536 NIAH cells
```

## License

MIT © 2026 Antoine Pedretti. Bundled FLORES-200 data: CC-BY-SA 4.0 (Meta NLLB).
