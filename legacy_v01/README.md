# FertiScope v0.1

Tokenizer fertility + cost multiplier + context budget for multilingual LLM deployments.

**v0.1 scope:** English <-> Vietnamese only. 4 tokenizers (cl100k, o200k, Llama-3.1, SEA-LION v3). Local-first.

## What it does

For a given (English corpus, Vietnamese corpus) pair and a tokenizer, computes:

- **Fertility** = tokens per word, separately for EN and VI
- **Fertility ratio** = VI fertility / EN fertility (the headline number — "Vietnamese costs Nx English under this tokenizer")
- **Cost multiplier** at OpenAI / Bedrock / Together pricing
- **Context budget**: how many in-context examples fit in 4096 / 8192 windows, % consumed per turn

**No LLM API calls.** All analysis is local. tiktoken and HuggingFace tokenizer files are small, free, offline.

## Quick start

```bash
cd /home/antoine/Documents/WORK/CODE/LABS/fertiscope
source .venv/bin/activate
pip install -e .
fertiscope demo
```

First run downloads the Llama-3.1 + SEA-LION tokenizer files (~10MB total via HuggingFace Hub). Subsequent runs are fully offline.

## CLI

```bash
fertiscope demo                                    # run the bundled FLORES-200 sample on all tokenizers
fertiscope demo --tokenizers cl100k o200k          # subset
fertiscope analyze --en my_en.txt --vi my_vi.txt --tokenizer llama-3.1
fertiscope list-tokenizers
```

## How the math works

1. **Word count**: `segmenters.count_words(text, lang)` — English uses regex word boundaries, Vietnamese uses `underthesea.word_tokenize` so multi-syllable words like "Việt Nam" count as 1 word, not 2.
2. **Token count**: `tokenizers.get_tokenize_fn(tokenizer_id)` returns a callable. tiktoken-native for OpenAI; HuggingFace `tokenizers` lib for Llama / SEA-LION.
3. **Fertility**: `tokens / words`. Per-language.
4. **Ratio**: `vi.fertility / en.fertility`. The 2.5x-15x headline number.
5. **Cost multiplier**: equals fertility ratio (price is per-token; using N x tokens means paying N x).
6. **Context budget**: `int(context_window / avg_tokens_per_example_vi)` and `tokens_per_turn * N / context_window` for the utilization curve.

## What v0.1 deliberately does NOT do

- **No predicted quality degradation curve.** That's speculative without per-model benchmarks. We ship the honest "% context consumed per turn" instead.
- **No multi-language support beyond EN <-> VI.** Each language needs its own segmenter (underthesea for VI, pythainlp for TH, Indic NLP for IN, etc.). v0.2 plan.
- **No paste-your-own-corpus web UI.** CLI only for v0.1. `fertiscope serve` is v0.2.
- **No paid tier.** OSS for v0.1.

## File layout

```
fertiscope/
├── __init__.py
├── data/flores_sample.py     # 10 EN<->VI FLORES-style sentence pairs
├── segmenters.py             # EN regex + VI underthesea word boundaries
├── tokenizers.py             # tiktoken + HF tokenizer wrappers, 4 launch tokenizers
├── cost.py                   # static USD/1M-token price table
├── context.py                # context-window budget math
├── fertility.py              # the math + FertilityReport dataclass
└── cli.py                    # argparse CLI: demo / analyze / list-tokenizers
```

## License

MIT.
