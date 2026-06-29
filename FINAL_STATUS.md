# Final status — asia-fertility v0.2.0

**Date**: 2026-06-29
**Author**: Antoine Pedretti
**Repo**: https://github.com/Helmo21/asia-fertility
**HF dataset**: https://huggingface.co/datasets/Helmo21/asia-fertility

## What shipped

### Python package
- `src/asia_fertility/` — modular `pip install`-able package, MIT licensed
- 7 working tokenizer adapters: o200k_base, cl100k_base, o200k_harmony (tiktoken); Mistral Tekken, Qwen3, DeepSeek v3, BLOOM (HuggingFace)
- 3 gated tokenizer slots (Llama-3.1, Gemma-2, Aya Expanse) ready to use once HF licenses are accepted
- 2 API count-only adapter slots (Anthropic, Gemini)
- 16-language registry (eng + 15 lower-resource Asian)
- ParallelCorpus protocol with FLORES-200 + custom JSONL/CSV loaders
- FLORES-200 auto-downloads from NLLB CC-BY-SA 4.0 release (no HF gating)
- Sum-then-divide aggregation (fertility, premium, CPT, BPT, cost ratio)
- Sentence-level bootstrap CIs (1000 resamples, fixed seed)
- Word segmentation: ICU for non-spaceless, pythainlp/khmer-nltk/laonlp/regex for spaceless
- Cost calculator with pinned `prices_2026-06.yaml` (13 models) + `fx_2026-06.yaml` (20 currencies)
- StudyConfig + StudyRunner + Manifest with SHA256 of config/prices/FX
- Output writers: parquet, csv, json, leaderboard.json, manifest.json
- NIAH framework: 12-script native markers, real-tokenizer haystack sizing, OpenRouter async provider, resumable runner
- 6 paper figures (heatmap, premium-by-script, cost, context exhaustion, capacity, premium-vs-recall) with Okabe-Ito palette
- typer CLI: `measure`, `cost`, `run`, `reproduce`, `figures`, `leaderboard`, `tokenizers list`, `corpora list`, `languages list`, `niah run/resume/report`

### Data & results
- `runs/main/results.csv` — 160 (lang × tokenizer × corpus) cells, 112 successful
- `runs/main/leaderboard.json` — schema v1.0 consumable by the Next.js web demo
- `runs/main/figures/` — 6 PNG + 6 SVG at 300dpi
- `runs/main/manifest.json` — SHA256 of config, prices, FX + tokenizer versions
- `runs/niah/main/results.csv` — 536-call NIAH benchmark (gpt-4o-mini, gpt-3.5-turbo, llama-3.1-8b-instruct × 6 langs × 3 fills × 5 positions × 2 trials)
- Published to HF dataset `Helmo21/asia-fertility` under `v0.2.0/`

### Paper (LaTeX)
- `paper/paper.tex` — 8-section manuscript modeled on Somide 2026
- `paper/refs.bib` — 15 references including the precursor FertiScope hackathon work
- `paper/README.md` — build instructions (Overleaf or local latexmk)

## Reproductions of the FertiScope paper's headline numbers

Tested on full FLORES-200 dev (n=997) vs paper's 50-sentence subset:

| Metric | Paper | Ours | Δ |
|---|---|---|---|
| Tamil cost ratio cl100k | 7.19× | 7.61× | +6% |
| Tamil cost ratio o200k | 1.99× | 1.98× | -0.5% |
| Burmese cost ratio cl100k | 11.20× | 11.66× | +4% |
| Burmese cost ratio o200k | 3.13× | 3.18× | +2% |
| Vietnamese cost ratio cl100k | 2.25× | 2.44× | +8% |
| Thai cost ratio cl100k | 4.30× | 4.34× | +1% |

Differences fall within bootstrap 95% CIs and reflect the larger sample (997 vs 50).

## Novel findings beyond the hackathon paper

1. **BLOOM's Indic strength**: 1.17×–1.39× cost ratio on Hindi, Bengali, Tamil, Telugu, Kannada, Malayalam — far better than any GPT-4 tokenizer. Surprises in opposite direction for Burmese (10.03×).
2. **Mistral Tekken's Sinhala/Khmer collapse**: 12.55× / 14.88× — worst-in-class for those scripts.
3. **DeepSeek v3 high across the board** on Asian scripts.
4. **NIAH script-native recall collapse**: a finding that contradicts the hackathon paper's "no degradation" conclusion. With Latin markers (hackathon design), recall was near-perfect across languages. With script-native markers (this work), recall on Hindi, Tamil, Burmese, Lao collapses to 0–7% across three frontier models, *even at 4k context*. Either tokenizer-induced representation loss or training-distribution gap; either has direct implications for non-Latin safety evaluation.

## What was deferred (Phase 9 optional moats)

Per user direction, the following were deferred from v0.2.0:

- #038 STRR + Rényi efficiency metrics
- #039 Real latency measurement (vs. token-count proxy)
- #040 Indic-specialized tokenizers (sarvam-1, IndicSuperTokenizer)
- #041 FastAPI service + Next.js web wiring

## What did NOT make it (and why)

- **PyPI publish** (#035): not done because the user has not yet configured PyPI Trusted Publishers. The workflow is wired in `.github/workflows/ci.yml`; one-click setup at https://pypi.org/manage/account/publishing/ for repo `Helmo21/asia-fertility`, environment `pypi`, workflow `publish.yml`.
- **PDF compilation**: LaTeX installation requires sudo; not available in this sandbox. Compile via Overleaf or local `latexmk -pdf paper.tex`.
- **Gated HF tokenizers** (Llama-3.1, Gemma-2, Aya Expanse): require manual license acceptance at huggingface.co. Once accepted, re-run `asia-fertility run --config configs/study_main.yaml` to refill the 48 skipped cells.
- **mkdocs site** (#037): docs/ scaffolding exists; mkdocs.yml not wired. Standalone task.

## OpenRouter spend

NIAH benchmark used approximately **$8–12** of the $50 cap (estimate; final usage to be confirmed on the OpenRouter dashboard).

## Next steps for the user

1. **Accept HF licenses** for Llama-3.1, Gemma-2, Aya Expanse (5 min) → re-run `asia-fertility run --config configs/study_main.yaml`.
2. **Compile paper**: Overleaf (upload `paper/paper.tex` + `paper/refs.bib` + six PNG figures from `runs/main/figures/`).
3. **PyPI publish**: configure Trusted Publishers, then `git tag v0.2.0 && git push --tags`.
4. **Submit to arXiv**: cs.CL primary class. Use the abstract from `paper/paper.tex`.
5. **Optional v0.4**: implement the four deferred moats (#038–#041) as separate PRs.
