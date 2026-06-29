# Roadmap: from FertiScope-web to a publishable Python package + AI-engineering foundations

**Goal**: ship `fertiscope` on PyPI with **equal or wider coverage than afri-fertility** (arXiv 2606.24460), while learning the AI-engineering primitives behind each phase.

**Total estimate**: 8–10 weeks part-time (≈10 h/week).

Each phase has: *what you ship*, *what you learn*, *which gap it closes*.

---

## Context: the gap we're closing

| Dimension | FertiScope (current) | afri-fertility (target) |
|---|---|---|
| Languages | 15 Asian + EN (16) | 23 African + EN/FR (25) |
| Scripts | Latin, Devanagari, Brahmic-derived | Latin, Ge'ez/Ethiopic, N'Ko, Ajami |
| Tokenizers | 3 families (cl100k, o200k, Llama-3.1) | 11 families — adds Llama-4, **Gemma-4**, Mistral Tekken, Qwen3, DeepSeek v3, BLOOM, Aya Expanse, Claude/Gemini |
| Corpora | FLORES-200, 50 sentences | FLORES-200+ **and** SIB-200 **and** MAFAND-MT, cross-validated (Pearson r=0.9998) |
| Metrics | fertility, cost ratio, capacity, context budget, 0–4 risk estimate | fertility, premium, **CPT, BPT**, context efficiency, **bootstrap 95% CIs**, sum-then-divide |
| Cost | USD only, in-app editable | Pinned USD + FX YAML, config hash in manifest |
| Distribution | Web app (Next.js, browser-only) | PyPI package + CLI + Python API |
| Reproducibility | `precompute.mjs` | Locked `study_main.yaml`, golden tests, CI, `reproduce` one-command demo |
| Open data | leaderboard.json in repo | HuggingFace dataset + parquet/csv/json |
| Latency | not framed | Explicit latency multiplier |
| Multi-turn / NIAH | **540-call pilot** (your edge) | not addressed |
| Honesty framing | explicit exact-vs-estimate | attempts accuracy linkage |

---

## Phase 0 — Scaffold a real Python package (week 1)

**Ship**: empty-but-correct `fertiscope` package, runnable CLI, green CI.

- Convert the discarded `fertiscope/` v0.1 into a `src/fertiscope/` layout.
- `pyproject.toml` with `hatchling` build backend; optional-deps groups `[hf]`, `[api]`, `[viz]`, `[dev]`.
- Adopt **`uv`** for dependency management (fast, deterministic lockfile).
- CLI with **`typer`** — subcommands `measure`, `cost`, `run`, `reproduce`, `tokenizers list`, `languages list`.
- `pre-commit` with `ruff` + `mypy --strict`; `pytest` with one trivial test.
- GitHub Actions: matrix `python: ["3.11", "3.12", "3.13"]`, lint + test on PR.

**Learn**: src-layout vs flat, why `pyproject.toml` killed `setup.py`, what `uv lock` actually pins, how CI matrix testing prevents "works on my machine."

**Gap closed**: distribution model (web app → `pip install`).

---

## Phase 1 — Tokenizer plurality (weeks 1.5–3)

**Ship**: 11+ tokenizers behind a registry, all callable identically.

- `tokenizers/base.py`: `class Tokenizer(Protocol): encode(text) -> list[int]`.
- **tiktoken adapter** — `cl100k_base`, `o200k_base`, `o200k_harmony` (gpt-oss).
- **HuggingFace adapter** via `transformers.AutoTokenizer` — Llama-3.1, **Llama-4**, **Gemma-4**, **Mistral Tekken**, **Qwen3**, **DeepSeek v3**, **BLOOM**, **Aya Expanse**. Gated models read `HF_TOKEN`.
- **API count-only adapter** — Anthropic `count_tokens` endpoint, Google Gemini `countTokens`. Gracefully degrade if no key.
- Registry pattern: `get_tokenizer("openai/o200k_base")` → instance. Skip-with-warning if unavailable, never crash.

**Learn**: what BPE actually does (subword merges), why byte-level (GPT-4o) beats UTF-8 fallback (cl100k) on Brahmic scripts, HF gating workflow, why `count_tokens` exists for closed models.

**Gap closed**: 3 → 11 tokenizer families (the single biggest reviewer objection).

---

## Phase 2 — Corpus loaders (week 3.5)

**Ship**: 4 loaders behind a common interface.

- `corpora/flores.py` — FLORES-200+ via `datasets.load_dataset("facebook/flores")`, streaming.
- `corpora/sib200.py` — SIB-200 (topic-classified parallel data).
- `corpora/mafand.py` — MAFAND-MT (extra languages, MT-quality).
- `corpora/custom.py` — JSONL/CSV with `{lang, text}` schema for user's own corpus.
- Common interface: `ParallelCorpus.iter_sentences(lang) -> Iterator[str]`.

**Learn**: HuggingFace `datasets` (Arrow under the hood, streaming vs map-style), parallel-corpus design (same meaning, different languages = language effect isolated).

**Gap closed**: 1 corpus → 4; enables cross-corpus validation (their r=0.9998 trick).

---

## Phase 3 — Metrics rigor (week 4) ← **highest leverage**

**Ship**: `core/metrics.py` with 5 metrics + CIs.

- `fertility` = tokens/words, `premium` = lang/EN.
- **`CPT`** = chars/token, **`BPT`** = utf8_bytes/token ← cross-script-fair, the metric you lack.
- `context_efficiency` = window × CPT.
- **Sum-then-divide aggregation** (sum tokens across all sentences, then divide by sum of words — not mean of per-sentence ratios). Document why.
- **Bootstrap 95% CIs** over sentences using `numpy.random.default_rng` (1000 resamples). Report as `(point, low, high)`.
- Word segmentation: `Intl.Segmenter` → Python equivalent. Use `pyicu` or `icu-tokenizer`. For spaceless scripts: `pythainlp` (Thai), `khmer-nltk` (Khmer), Burmese via `myanmar-tools` or a simple syllable segmenter.
- Unicode normalization: NFC by default, document the choice.

**Learn**: why mean-of-ratios is biased (Jensen's inequality), bootstrap as a non-parametric CI estimator, why bytes-per-token is the only fair cross-script metric.

**Gap closed**: 50-sentence point estimates → full FLORES with CIs; adds BPT; spaceless-script segmentation reproducibility.

---

## Phase 4 — Cost + FX (week 5, ~3 days)

**Ship**: pinned snapshots, local-currency support.

- `configs/prices_2026-07.yaml` — every model's input/output $/1M tokens, dated.
- `configs/fx_2026-07.yaml` — USD→VND, IDR, MYR, THB, INR, BDT, TWD, KRW, PHP. Snapshot date in file.
- `cost/model.py` — `cost_of(text, lang, models, currencies)` returns table.
- `cost/prices.py` loads pinned YAML and refuses silent fallback to defaults.

**Learn**: data provenance, why "editable in app" is a reproducibility anti-pattern for papers, FX snapshot hygiene.

**Gap closed**: in-app editable prices → dated YAML, multi-currency.

---

## Phase 5 — Study runner + manifest (week 6)

**Ship**: `afri-fertility run`-equivalent.

- `study/runner.py` — orchestrator over (language × tokenizer × corpus) grid.
- `config.py` — `StudyConfig` as a `pydantic.BaseModel` loaded from YAML.
- Output: `runs/main/results.{parquet,csv,json}` + `leaderboard.json` + `manifest.json`.
- **`manifest.json`** records: tokenizer versions, corpus hashes, config SHA256, package version, run date, host OS.
- **`fertiscope reproduce`** — offline reference suite, 10 sentences × 7 languages × tiktoken tokenizers only, **no network, no keys**. One-command credibility demo.
- **Golden tests**: lock token counts for a fixed (text, tokenizer) tuple. CI fails if tiktoken version changes output.

**Learn**: pre-registered studies, why a manifest hash is the difference between "trust me" and "trust the artifact," parquet vs CSV (columnar, typed, smaller).

**Gap closed**: ad-hoc precompute → reproducible study runner with manifest.

---

## Phase 6 — Multi-turn NIAH, properly (weeks 6.5–8)

**Ship**: production-grade port of Miles' sweep.

- Port `sweep_contexts.py` into `fertiscope/niah/`.
- **OpenRouter adapter** with `httpx.AsyncClient` for batched calls.
- Per-language NIAH with **script-native markers** (Tamil marker in Tamil text, etc.) — fixes the Latin-marker caveat the paper flagged.
- Sweep all 16 languages × 3 models × {4k, 16k, 64k, 128k} fill levels.
- Throttle and retry with `tenacity`; persist results incrementally.
- Output to `runs/niah/results.csv`, re-runnable.

**Learn**: async API batching, exponential backoff, NIAH design (position, depth, distractor saturation), why script-native markers matter for retrieval bias.

**Gap closed**: pilot → full benchmark; you keep this advantage over afri-fertility (they have no multi-turn dimension).

---

## Phase 7 — Figures + leaderboard (week 8.5, ~4 days)

**Ship**: regenerable paper figures.

- `report/figures.py` — 6 figures (heatmap, premium-by-script, cost, context, in-domain vs general, premium-vs-accuracy if you do linkage). PNG + SVG.
- `report/leaderboard.py` — JSON the web app can consume.
- Wire the Next.js app to consume `leaderboard.json` from PyPI release artifact (or HF dataset).

**Learn**: matplotlib for publication-quality figures, vector graphics, colorblind-safe palettes.

**Gap closed**: figures regeneration parity with afri-fertility.

---

## Phase 8 — Publishing (week 9)

**Ship**: PyPI + HF dataset + arXiv v2.

- `pypi publish` via Trusted Publishers (no API tokens in CI).
- Publish results to `huggingface.co/datasets/yourorg/fertiscope-results` (parquet split per study).
- Docs: `mkdocs-material`, deployed to GitHub Pages.
- `CITATION.cff` so GitHub auto-generates BibTeX.
- arXiv v2 of your paper with: bigger language set, CIs, BPT, full NIAH, multi-tokenizer.
- **Reach out to Somide** — joint Asia+Africa leaderboard or cross-citation.

**Learn**: Trusted Publishers (OIDC, no secrets), HF Hub dataset structure, citation metadata.

**Gap closed**: hackathon repo → citable open-source release.

---

## Phase 9 — Beyond afri-fertility (week 10+, optional moats)

These are where you *overtake* them:

- **STRR + Rényi efficiency** (Nayeem 2025) — fertility-alone-is-incomplete.
- **Real latency measurement** — actually time generation, don't just claim "tokens ≈ latency."
- **Indic-specialized tokenizers** — IndicSuperTokenizer, sarvam-1 tokenizer.
- **Web tool ↔ package wiring** — Next.js calls `fertiscope` via a Vercel Python function or a thin FastAPI on a Vercel/Modal endpoint.
- **Live-data adapter** — `crawl_baochinhphu.py` becomes `corpora/custom_crawl.py` for domain-specific Vietnamese fertility.

---

## AI-engineering primitives you'll have learned by the end

| Concept | Phase | Why it matters beyond this project |
|---|---|---|
| BPE / byte-level tokenization | 1 | Every LLM eval starts here |
| HuggingFace `transformers` + `datasets` | 1, 2 | The standard ML data stack |
| Pre-registered studies, manifests, hashes | 5 | Difference between research code and a paper artifact |
| Bootstrap CIs, sum-then-divide | 3 | Stats hygiene for any benchmark |
| Async batched API calls | 6 | How every eval harness scales |
| Closed-weight count-only APIs | 1 | How to benchmark models you can't run |
| Parquet, HF Hub datasets, CITATION.cff | 8 | The open-research distribution loop |
| NIAH design (position × depth × distractor) | 6 | The core long-context evaluation method |
| `pyproject.toml`, src layout, uv, Trusted Publishers | 0, 8 | Modern Python packaging end-to-end |

---

## "Do these first" if you have only 2 weeks

If timeline collapses, the order that closes the most reviewer objections per hour is:

1. **Phase 0** (scaffold) — non-negotiable foundation.
2. **Phase 1** — add Gemma-4, Qwen3, Llama-4 (the three tokenizers most likely to change your leaderboard).
3. **Phase 3** — BPT + bootstrap CIs on the *existing* 50 sentences (don't even need the corpus expansion yet).
4. **Phase 5** — `manifest.json` + `reproduce` command.

That alone gets you 70% of the way to credibility parity. Everything else can ship as v0.3 / v0.4.

---

## Target final package structure

```
fertiscope/
├── src/fertiscope/
│   ├── core/                 # segmentation, metrics, aggregation (pure functions)
│   ├── tokenizers/           # tiktoken + HF + API adapters + registry
│   ├── corpora/              # FLORES-200, SIB-200, MAFAND-MT, custom JSONL/CSV
│   ├── cost/                 # cost model, price/FX snapshots
│   ├── study/                # orchestrator, accuracy linkage
│   ├── niah/                 # multi-turn needle-in-haystack runner
│   ├── report/               # tables, figures, leaderboard JSON
│   ├── cli.py                # typer CLI
│   └── config.py             # pydantic StudyConfig
├── configs/                  # locked study config + pinned price/FX snapshots
├── data/
│   ├── languages.yaml        # Asian-language registry
│   └── reference_suite/      # offline reproduce dataset
├── tests/                    # unit · golden · integration
├── docs/                     # mkdocs-material
├── .github/workflows/        # CI + PyPI publish
├── pyproject.toml
├── CITATION.cff
└── README.md
```

---

## Reference: afri-fertility's exact file layout (the target to match)

```
src/afri_fertility/
├── core/{aggregate.py, metrics.py, segmentation.py}
├── tokenizers/{base.py, tiktoken_adapter.py, hf_adapter.py, api_adapter.py}
├── corpora/{base.py, flores.py, sib200.py, mafand.py, custom.py}
├── cost/{model.py, prices.py, fx.py}
├── study/{runner.py, linkage.py}
├── report/{figures.py, tables.py, leaderboard.py}
├── cli.py, config.py, cache.py, languages.py
```

If you mirror this structure, code review against their paper becomes trivial and reviewers stop asking why your layout is "different."
