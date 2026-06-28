# FertiScope task specs

41 mono-task specs for converting FertiScope into a publishable Python package with the same dimensions as `CipherSenseAI/afri-fertility` (arXiv 2606.24460), plus distinctive moats they don't have.

Each spec follows the same shape: **Scope → Files → Interface/contract → Notes → Acceptance Criteria → User Stories**. Read in dependency order; each one explicitly lists what it depends on and what it unblocks.

## Dependency graph (high level)

```
001 archive v0.1
 └─→ 002 pyproject.toml
      └─→ 003 CLI scaffolding (typer stubs)
           ├─→ 004 CI + pre-commit + Makefile
           │    └─→ 005 Tokenizer Protocol + registry
           │         ├─→ 006 tiktoken adapter
           │         ├─→ 007 HuggingFace adapter
           │         ├─→ 008 API count-only adapter
           │         └─→ 009 `tokenizers list` CLI
           │              └─→ 010 Corpus Protocol + Sentence
           │                   ├─→ 011 Languages YAML + CLI
           │                   │    └─→ 012 FLORES loader
           │                   │         └─→ 013 SIB-200 + MAFAND loaders
           │                   │              └─→ 014 Custom + reference suite
           │                   └─→ 015 Per-sentence metrics + NFC
           │                        ├─→ 016 Word seg (whitespace + ICU)
           │                        │    └─→ 017 Spaceless seg (Thai/Khm/Mya/Lao)
           │                        ├─→ 018 Sum-then-divide aggregation
           │                        └─→ 019 Bootstrap CIs + `measure` CLI
           │
           ├─→ 020 Prices YAML + loader
           │    └─→ 021 FX YAML + loader
           │         └─→ 022 CostCalculator + `cost` CLI
           │
           └─→ 023 StudyConfig + 3 YAMLs
                └─→ 024 Study runner orchestrator
                     └─→ 025 Manifest + output writers
                          └─→ 026 `run` + `reproduce` CLI
                          └─→ 031 Palette + Figures 1-3
                               └─→ 032 Figures 4-6
                                    └─→ 033 Leaderboard JSON
                          └─→ 027 Script-native markers
                               └─→ 028 Haystack builder
                                    └─→ 029 OpenRouter async provider
                                         └─→ 030 NIAH runner + CLI
                          └─→ 034 CITATION.cff + README
                               └─→ 035 PyPI Trusted Publishers
                                    └─→ 036 HF dataset publish
                                         └─→ 037 mkdocs site

Optional moats (v0.4+):
 ├─→ 038 STRR + Rényi efficiency
 ├─→ 039 Real latency runner
 ├─→ 040 Indic tokenizers (sarvam)
 └─→ 041 FastAPI + Next.js wiring
```

## "Do these first" (2-week minimum-viable path)

For maximum credibility-per-hour:

1. **#001 #002 #003 #004** — package skeleton + CI (3 days).
2. **#005 #006** — tokenizer registry + tiktoken adapter only (1 day).
3. **#015 #018 #019** — metrics + bootstrap CIs + measure CLI (3 days).
4. **#020 #021 #022** — cost calculator with pinned snapshots (2 days).
5. **#023 #024 #025 #026** — study runner with manifest + reproduce (3 days).

That's ~12 working days and closes the top reviewer objections: 11+ tokenizers (start with 3 in v0.2, add 8 more in v0.3 via #007/#008), BPT + CIs, dated price snapshots, reproducible manifest, offline credibility demo.

Everything else (NIAH, figures, publishing, mkdocs, moats) ships incrementally as v0.3 / v0.4.

## Phase → task mapping

| Phase | Tasks | Result |
|---|---|---|
| 0 — Scaffold | 001–004 | Empty-but-correct repo, green CI |
| 1 — Tokenizers | 005–009 | 11+ tokenizer adapters, golden tests |
| 2 — Corpora | 010–014 | 4 corpus loaders + offline reference suite |
| 3 — Metrics | 015–019 | BPT + CIs + measure CLI |
| 4 — Cost | 020–022 | Pinned prices + FX + multi-currency cost |
| 5 — Study runner | 023–026 | run + reproduce CLI with manifest |
| 6 — NIAH | 027–030 | Script-native multi-turn benchmark |
| 7 — Figures | 031–033 | 6 paper figures + leaderboard JSON |
| 8 — Publishing | 034–037 | PyPI, HF dataset, mkdocs site |
| 9 — Moats | 038–041 | STRR, latency, Indic, web wiring |

## Gap-to-task map (vs afri-fertility)

| Gap closed | Tasks |
|---|---|
| 3 → 11+ tokenizers | 005, 006, 007, 008 |
| 1 → 4 corpora + cross-corpus validation | 010, 012, 013, 014 |
| No BPT, no CIs | 015, 018, 019 |
| Editable in-app prices → pinned YAML | 020, 021 |
| No manifest.json, no reproduce | 024, 025, 026 |
| No PyPI package | 002, 034, 035 |
| Multi-turn NIAH (our edge — retained) | 027, 028, 029, 030 |
| No HF dataset, no docs site | 036, 037 |
| Beyond parity: STRR + Rényi | 038 |
| Beyond parity: real latency | 039 |
| Beyond parity: Indic tokenizers | 040 |
| Beyond parity: web ↔ package wiring | 041 |

## How to use these specs

Each spec is self-contained and Claude-Code-friendly.

```bash
# Pick a task
cat tasks/001-archive-v01-and-create-skeleton.groomed.md

# Hand to an agent (or do it yourself)
# The agent reads the Scope, files, interface, AC, and stories.
# Implements; verifies acceptance criteria.

# Run tests
make test && make lint
```

The Acceptance Criteria checklist at the bottom of each spec is the contract — flip a box when done, push when all are flipped.

## File map

```
tasks/
├── README.md                                              ← you are here
├── 001-archive-v01-and-create-skeleton.groomed.md
├── 002-wire-pyproject-toml.groomed.md
├── 003-cli-scaffolding-with-typer-stubs.groomed.md
├── 004-ci-precommit-and-makefile.groomed.md
├── 005-tokenizer-protocol-and-registry.groomed.md
├── 006-tiktoken-adapter.groomed.md
├── 007-huggingface-adapter.groomed.md
├── 008-api-count-only-adapter.groomed.md
├── 009-tokenizers-list-cli.groomed.md
├── 010-corpus-protocol-and-sentence.groomed.md
├── 011-languages-yaml-and-cli.groomed.md
├── 012-flores-loader.groomed.md
├── 013-sib200-and-mafand-loaders.groomed.md
├── 014-custom-loader-and-reference-suite.groomed.md
├── 015-per-sentence-metrics-and-nfc.groomed.md
├── 016-word-segmentation-whitespace-and-icu.groomed.md
├── 017-spaceless-segmentation.groomed.md
├── 018-sum-then-divide-aggregation.groomed.md
├── 019-bootstrap-cis-and-measure-cli.groomed.md
├── 020-prices-yaml-snapshot-and-loader.groomed.md
├── 021-fx-yaml-snapshot-and-loader.groomed.md
├── 022-cost-calculator-and-cli.groomed.md
├── 023-study-config-pydantic-and-yamls.groomed.md
├── 024-study-runner-orchestrator.groomed.md
├── 025-manifest-and-output-writers.groomed.md
├── 026-run-and-reproduce-cli.groomed.md
├── 027-script-native-markers.groomed.md
├── 028-haystack-builder.groomed.md
├── 029-openrouter-async-provider.groomed.md
├── 030-niah-runner-and-cli.groomed.md
├── 031-palette-and-figures-1-3.groomed.md
├── 032-figures-4-6.groomed.md
├── 033-leaderboard-json-emitter.groomed.md
├── 034-citation-and-readme-badges.groomed.md
├── 035-pypi-trusted-publishers.groomed.md
├── 036-hf-dataset-publish-script.groomed.md
├── 037-mkdocs-material-docs-site.groomed.md
├── 038-strr-renyi-efficiency.groomed.md         (optional moat)
├── 039-real-latency-runner.groomed.md           (optional moat)
├── 040-indic-tokenizers.groomed.md              (optional moat)
└── 041-fastapi-service-and-nextjs-wiring.groomed.md  (optional moat)
```
