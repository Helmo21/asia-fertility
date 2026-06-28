# CITATION.cff + README badges + repository metadata

Status: pending
Tags: `publishing`, `citation`, `readme`, `badges`, `documentation`
Depends on: #002
Blocks: #035, #037

## Scope

Publish-ready repository metadata: `CITATION.cff` so GitHub generates BibTeX automatically, a polished `README.md` with the right badges, and `.github/` issue/PR templates. No code changes.

### Files to create

- `CITATION.cff`
- `.github/ISSUE_TEMPLATE/bug.yaml`
- `.github/ISSUE_TEMPLATE/feature.yaml`
- `.github/pull_request_template.md`
- `.github/dependabot.yml`

### Files to modify

- `README.md` at repo root (the public-facing one).

### Interface and contract

`CITATION.cff`:

```yaml
cff-version: 1.2.0
title: "FertiScope: Multilingual Tokenizer Tax Analyzer for Low-Resource Asian Languages"
message: "If you use this software, please cite both the software and the paper."
type: software
authors:
  - family-names: Pedretti
    given-names: Antoine
    affiliation: "Trustia Agency"
  - family-names: Dang
    given-names: Leo
    affiliation: "Apart Research"
  - family-names: Whiticker
    given-names: Miles
    affiliation: "Apart Research"
  - family-names: Van
    given-names: Vinh
    affiliation: "Apart Research"
version: 0.3.0
date-released: 2026-09-15
license: MIT
repository-code: "https://github.com/dangpleo-ctrl/fertiscope"
url: "https://fertiscope.vercel.app"
identifiers:
  - type: url
    value: "https://github.com/dangpleo-ctrl/fertiscope"
keywords:
  - tokenizer
  - fertility
  - multilingual
  - low-resource languages
  - asian languages
  - large language models
  - global south
preferred-citation:
  type: article
  title: "FertiScope: Measuring the Multilingual Tokenizer Tax in Low-Resource Asian Languages"
  authors:
    - family-names: Pedretti
      given-names: Antoine
    - family-names: Dang
      given-names: Leo
    - family-names: Whiticker
      given-names: Miles
    - family-names: Van
      given-names: Vinh
  year: 2026
  url: "https://arxiv.org/abs/26XX.XXXXX"   # update with actual arXiv ID in #035
  conference:
    name: "Global South AI Safety Hackathon"
    city: "Da Nang"
    country: VN
  notes: "Hackathon submission, Apart Research."
```

`README.md` (full replacement):

````markdown
<div align="center">

# FertiScope 🌏

**The hidden multilingual tax in your tokenizer — measured before you deploy.**

[![PyPI](https://img.shields.io/pypi/v/fertiscope.svg?color=blue)](https://pypi.org/project/fertiscope/)
[![CI](https://github.com/dangpleo-ctrl/fertiscope/actions/workflows/ci.yml/badge.svg)](https://github.com/dangpleo-ctrl/fertiscope/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![arXiv](https://img.shields.io/badge/arXiv-26XX.XXXXX-b31b1b)](https://arxiv.org/abs/26XX.XXXXX)
[![Web](https://img.shields.io/badge/demo-fertiscope.vercel.app-black)](https://fertiscope.vercel.app)
[![HuggingFace Dataset](https://img.shields.io/badge/HF-fertiscope--results-ffd21e)](https://huggingface.co/datasets/trustia/fertiscope-results)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://github.com/dangpleo-ctrl/fertiscope)

</div>

`fertiscope` measures the **structural cost penalty** that LLM tokenizers impose on lower-resource Asian languages. The same content can cost up to **11× more tokens in Burmese than in English** on a frontier tokenizer — silent inflation of API bills, smaller usable context windows, and fewer in-context examples.

## Quickstart

```bash
pip install "fertiscope[oai]"
fertiscope reproduce                                 # offline credibility demo, no keys
```

Output (≤ 30 seconds, no network):

```
FertiScope reproduce · 18.3s · 21 rows
┌──────┬───────────────────────────┬───────────┬──────────┬──────┐
│ Lang │ Tokenizer                 │ Fertility │ Premium  │ BPT  │
├──────┼───────────────────────────┼───────────┼──────────┼──────┤
│ eng  │ openai/o200k_base         │      1.26 │       —  │ 4.32 │
│ tam  │ openai/o200k_base         │      2.49 │   1.98×  │ 2.18 │
│ tam  │ openai/cl100k_base        │     11.25 │   8.93×  │ 0.61 │
│ mya  │ openai/cl100k_base        │     14.50 │  11.20×  │ 0.50 │
│ ...  │ ...                       │       ... │     ...  │  ... │
```

## Why it matters

LLMs bill, throttle, and budget context per token. Tokenizers assign more tokens to the same meaning in some languages than others. Speakers and builders of high-fertility languages pay a structural penalty **before a model is ever invoked**.

`fertiscope` measures that penalty across:
- **16 lower-resource Asian languages** spanning Latin, Devanagari, Brahmic-derived, and Sino-Tibetan scripts.
- **11+ frontier and open tokenizers**: GPT-4o, GPT-5, GPT-3.5, Llama-3.1, Llama-4, Gemma-4, Mistral Tekken, Qwen3, DeepSeek v3, BLOOM, Aya Expanse, Claude (count-only), Gemini (count-only).
- **Multi-corpus validation** on FLORES-200 + SIB-200 (Pearson r ≈ 0.99 cross-corpus).
- **5 metrics**: fertility, premium, CPT, BPT (cross-script fair), context efficiency — all with **95% bootstrap CIs**.

It is the open measurement engine behind the **FertiScope paper** ([arXiv:26XX.XXXXX](https://arxiv.org/abs/26XX.XXXXX)) and the web demo at [fertiscope.vercel.app](https://fertiscope.vercel.app).

## Install

| Goal | Command |
|---|---|
| Bare minimum | `pip install fertiscope` |
| OpenAI tokenizers | `pip install "fertiscope[oai]"` |
| HuggingFace tokenizers (Llama, Gemma, Qwen, ...) | `pip install "fertiscope[hf]"` |
| API count-only (Claude, Gemini) | `pip install "fertiscope[api]"` |
| Multi-turn NIAH benchmark | `pip install "fertiscope[niah]"` |
| Figures + parquet | `pip install "fertiscope[viz]"` |
| All extras | `pip install "fertiscope[oai,hf,api,niah,viz]"` |

For gated HuggingFace tokenizers (Llama, Gemma), accept the license on huggingface.co and set `HF_TOKEN`.

## Common workflows

```bash
# Measure your own text
fertiscope measure --text "தமிழ் ஒரு செம்மொழி" --lang tam --tokenizer openai/o200k_base

# Cost across providers in your local currency
fertiscope cost --text "<your prompt>" --lang vie \
  --models openai/gpt-4o,openai/gpt-3.5-turbo,google/gemma-4-27b \
  --currencies USD,VND

# Run the full 16×11×2 leaderboard study
fertiscope run --config configs/study_main.yaml

# Generate paper figures
fertiscope figures --run runs/main --out runs/main/figures

# Multi-turn needle-in-haystack benchmark
fertiscope niah run --config configs/niah_main.yaml
```

## What's different from other tokenizer counters

| Tool | Languages | Tokenizers | CIs | Cost | Multi-turn |
|---|---|---|---|---|---|
| Tiktokenizer | EN-first | 3 OpenAI | — | — | — |
| HF Playground | EN-first | many | — | — | — |
| Petrov 2023 paper | 200 | 17 (one shot) | — | — | — |
| llm-language-token-tax | 50 | 5 | — | ✓ | — |
| **fertiscope** | **16 Asian** | **11+** | **✓ bootstrap** | **✓ multi-currency** | **✓** |
| afri-fertility (sister) | 23 African | 11+ | ✓ | ✓ | — |

## Honesty principle

Token economics (fertility, premium, BPT, context budget) are **deterministic and exact** — pinned by golden tests and reproducible to the byte.

Multi-turn degradation risk is the **one estimated quantity** — shown as a transparent 0–4 score because the underlying research literature finds it regime-dependent. We refuse to claim what the evidence can't support.

## Roadmap

See [`ROADMAP.md`](ROADMAP.md) and the per-phase specs in [`tasks/`](tasks/).

## Citation

```bibtex
@article{pedretti2026fertiscope,
  title   = {FertiScope: Measuring the Multilingual Tokenizer Tax in Low-Resource Asian Languages},
  author  = {Pedretti, Antoine and Dang, Leo and Whiticker, Miles and Van, Vinh},
  year    = {2026},
  journal = {arXiv preprint},
  url     = {https://arxiv.org/abs/26XX.XXXXX},
}
```

Click "Cite this repository" on GitHub for an auto-generated BibTeX block from [`CITATION.cff`](CITATION.cff).

## License

- **Code**: [MIT](LICENSE) © 2026 Antoine Pedretti and contributors.
- **FLORES-200 data**: CC-BY-SA 4.0 (Meta NLLB).
- **Bundled reference suite**: derived from FLORES-200, same license.
````

`.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: "/"
    schedule:
      interval: weekly
    groups:
      tokenizers:
        patterns: ["tiktoken", "transformers", "tokenizers"]
      dev:
        patterns: ["pytest*", "ruff", "mypy"]
  - package-ecosystem: github-actions
    directory: "/"
    schedule:
      interval: monthly
```

`.github/ISSUE_TEMPLATE/bug.yaml` and `feature.yaml`: standard GitHub issue forms with required fields (description, reproduction, expected vs actual).

### Notes

- The arXiv ID is a placeholder. Update everywhere after #035 lands the v2 paper.
- CITATION.cff version "0.3.0" matches the release tag in #035.
- Badges link to the future endpoints: PyPI, CI, arXiv, HF dataset. They appear broken until those land — acceptable for a pre-release.
- The README emphasizes **what the package does** and **how to install**, not internal architecture.
- The comparison table is a Marketing piece — keep it factual, not boastful.

## Acceptance Criteria

- [ ] `CITATION.cff` parses cleanly (validate at https://citation-file-format.github.io/cff-initializer/).
- [ ] GitHub's "Cite this repository" button generates valid BibTeX from CITATION.cff.
- [ ] `README.md` has at least 6 badges in the header.
- [ ] README contains a Quickstart section with `pip install` and `fertiscope reproduce`.
- [ ] README has an install matrix for the 6 extras.
- [ ] README references `ROADMAP.md` and `tasks/`.
- [ ] `.github/dependabot.yml` valid YAML; passes GitHub's actions linter.
- [ ] Issue templates valid YAML; appear in "New issue" dropdown on GitHub.
- [ ] PR template renders correctly.
- [ ] License section credits FLORES-200's CC-BY-SA 4.0.

## User Stories

### Story: Researcher cites the repo

1. Visits the GitHub page.
2. Clicks "Cite this repository" (right sidebar).
3. Gets BibTeX block.
4. Pastes into `.bib` file. Done.

### Story: New user lands on PyPI

1. Searches "fertiscope" on PyPI.
2. Lands on the package page.
3. Sees the README rendering: badges, quickstart, install matrix.
4. Runs `pip install fertiscope[oai]` and `fertiscope reproduce` within 2 minutes.

### Story: Dependabot bumps tiktoken

1. tiktoken 0.9 ships.
2. Dependabot opens PR with the bump.
3. CI runs golden tests → if counts drift, PR fails → maintainer reviews intentionally.

---

Blocked by: #002
