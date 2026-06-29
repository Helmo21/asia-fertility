# mkdocs-material documentation site + GitHub Pages

Status: pending
Tags: `docs`, `mkdocs`, `mkdocs-material`, `github-pages`, `mkdocstrings`
Depends on: #034
Blocks: None

## Scope

Stand up a documentation site at `https://dangpleo-ctrl.github.io/fertiscope/` using mkdocs-material with mkdocstrings for API docs extracted from docstrings. Includes installation, usage tutorial, methodology, contribution guides, and adding-a-tokenizer / adding-a-corpus playbooks.

### Files to create

- `mkdocs.yml`
- `docs/index.md`
- `docs/install.md`
- `docs/usage.md`
- `docs/methodology.md`
- `docs/cli_reference.md`
- `docs/api_reference.md`
- `docs/adding_a_tokenizer.md`
- `docs/adding_a_corpus.md`
- `docs/adding_a_language.md`
- `docs/figures.md`
- `docs/leaderboard_schema.md` (created in #033, copy into docs/ if not already)
- `docs/updating_prices.md`
- `docs/changelog.md`
- `docs/contributing.md`
- `docs/code_of_conduct.md`
- `.github/workflows/docs.yml`

### Files to modify

- `pyproject.toml` — add `[docs]` optional-extras with `mkdocs-material`, `mkdocstrings[python]`.

### Interface and contract

`pyproject.toml` addition:

```toml
[project.optional-dependencies]
docs = [
    "mkdocs-material>=9.5",
    "mkdocstrings[python]>=0.26",
    "pymdown-extensions>=10",
]
```

`mkdocs.yml`:

```yaml
site_name: FertiScope
site_url: https://dangpleo-ctrl.github.io/fertiscope/
site_description: Tokenizer fertility, cost, and multi-turn context-budget analyzer for low-resource Asian languages.
repo_url: https://github.com/dangpleo-ctrl/fertiscope
repo_name: dangpleo-ctrl/fertiscope
edit_uri: edit/main/docs/
copyright: "© 2026 Antoine Pedretti and contributors. MIT license."

theme:
  name: material
  features:
    - navigation.instant
    - navigation.tabs
    - navigation.sections
    - navigation.expand
    - navigation.top
    - search.highlight
    - search.suggest
    - content.code.copy
    - content.code.annotate
    - content.tabs.link
    - toc.follow
  palette:
    - media: "(prefers-color-scheme: light)"
      scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/weather-night
        name: Switch to dark mode
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/weather-sunny
        name: Switch to light mode
  icon:
    repo: fontawesome/brands/github

nav:
  - Home: index.md
  - Install: install.md
  - Usage:
      - Quickstart: usage.md
      - CLI reference: cli_reference.md
      - API reference: api_reference.md
  - Methodology:
      - Overview: methodology.md
      - Figures: figures.md
      - Leaderboard schema: leaderboard_schema.md
      - Updating prices: updating_prices.md
  - Extend:
      - Adding a tokenizer: adding_a_tokenizer.md
      - Adding a corpus: adding_a_corpus.md
      - Adding a language: adding_a_language.md
  - Contributing: contributing.md
  - Changelog: changelog.md

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          paths: [src]
          options:
            show_source: false
            show_root_heading: true
            show_signature_annotations: true
            members_order: source
            docstring_style: google

markdown_extensions:
  - admonition
  - attr_list
  - md_in_html
  - tables
  - footnotes
  - pymdownx.highlight:
      anchor_linenums: true
      line_spans: __span
      pygments_lang_class: true
  - pymdownx.inlinehilite
  - pymdownx.snippets
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
  - pymdownx.tabbed:
      alternate_style: true
  - pymdownx.details
  - toc:
      permalink: true

extra:
  social:
    - icon: fontawesome/brands/github
      link: https://github.com/dangpleo-ctrl/fertiscope
    - icon: fontawesome/brands/python
      link: https://pypi.org/project/fertiscope/
```

`docs/index.md` (landing):

```markdown
# FertiScope

**The hidden multilingual tax in your tokenizer — measured before you deploy.**

FertiScope is a Python package and web tool that measures the structural cost penalty LLM tokenizers impose on lower-resource Asian languages. The same content can cost up to **11× more tokens in Burmese than English** on a frontier tokenizer.

## Quickstart

```bash
pip install "fertiscope[oai]"
fertiscope reproduce
```

→ See the [Install guide](install.md) for HuggingFace and API extras.

## What it measures

- **Fertility**, **premium**, **CPT**, **BPT** (bytes per token, cross-script-fair).
- **Same-content cost ratio** across 16 Asian languages × 11+ tokenizers.
- **Bootstrap 95% CIs** at the sentence level.
- **Multi-turn NIAH recall** with script-native markers.

## What's different

- 16 lower-resource Asian languages (vs 23 African in [afri-fertility](https://github.com/CipherSenseAI/afri-fertility)).
- Multi-turn dimension (not in afri-fertility).
- Pinned, dated prices + FX snapshots — fully reproducible.
- Web demo at [fertiscope.vercel.app](https://fertiscope.vercel.app).

## Citation

```bibtex
{{ load citation from CITATION.cff }}
```

See [arXiv:26XX.XXXXX](https://arxiv.org/abs/26XX.XXXXX) for the paper.
```

`docs/usage.md`:

```markdown
# Usage

## Measure your own text

```bash
fertiscope measure --text "தமிழ் ஒரு செம்மொழி" --lang tam --tokenizer openai/o200k_base
```

Output:

```
FertiScope measure · lang=tam · tokenizer=openai/o200k_base · n=1
┌──────────────────────────────┬──────────┬──────────────────────┐
│ Metric                       │  Point   │      95% CI          │
├──────────────────────────────┼──────────┼──────────────────────┤
│ Fertility (tokens/word)      │   3.000  │ [3.000, 3.000]       │
│ Premium (vs baseline)        │     —    │ —                    │
│ Cost ratio (same content)    │     —    │ —                    │
│ CPT (chars/token)            │   3.667  │ [3.667, 3.667]       │
│ BPT (bytes/token)            │   2.500  │ [2.500, 2.500]       │
└──────────────────────────────┴──────────┴──────────────────────┘
```

## Run the full study

```bash
fertiscope run --config configs/study_main.yaml
```

Writes `results.parquet`, `results.csv`, `results.json`, `leaderboard.json`, `manifest.json` to `runs/main/`.

## Cost calculator

```bash
fertiscope cost --text "Xin chào" --lang vie \
  --models openai/gpt-4o,openai/gpt-3.5-turbo \
  --currencies USD,VND
```

## NIAH benchmark

```bash
fertiscope niah run --config configs/niah_main.yaml --yes
fertiscope niah report --output-dir runs/niah/main
```

## Generate figures

```bash
fertiscope figures --run runs/main --out runs/main/figures
```
```

`docs/methodology.md`:

```markdown
# Methodology

## Word segmentation

- **Non-spaceless scripts** (Latin, Devanagari, Bengali, Sinhala, Tamil, Telugu, Kannada, Malayalam): ICU `BreakIterator` (Python `pyicu`). Falls back to Unicode-aware regex if pyicu unavailable.
- **Spaceless scripts**: Thai via `pythainlp`, Khmer via `khmer-nltk`, Burmese via regex syllable (no robust library available), Lao via `laonlp` or regex.

Each segmenter's identity is recorded in `manifest.json[tokenizer_versions]`.

## Aggregation

**Sum-then-divide**, not mean-of-ratios. Fertility = sum(tokens) / sum(words) across all sentences. Mean-of-ratios is biased by Jensen's inequality at variable sentence lengths.

## Confidence intervals

1000-resample bootstrap at the sentence level with fixed RNG seed (default 42). Reported as `(point, low, high)` where low/high are 2.5%/97.5% quantiles.

## Cross-script fairness

**BPT (bytes per token)** is the only fully cross-script-fair metric — UTF-8 charges proportionally for codepoint width (Latin 1B, Devanagari 3B, Brahmic 3-4B). A tokenizer producing X bytes per token does roughly the same compression work regardless of script.

Fertility (tokens/word) varies systematically with words-per-sentence across languages. Use BPT for cross-script comparisons.

## Bootstrap details

- We resample SENTENCES with replacement (sentence-level i.i.d. assumption — appropriate for FLORES-200).
- One-sample bootstrap: target language is resampled; baseline is held at its point estimate. Two-sample (resample both) yields ~5% wider CIs without changing rankings.
```

`docs/adding_a_tokenizer.md`, `adding_a_corpus.md`, `adding_a_language.md` are step-by-step playbooks. Each ~50 lines.

`.github/workflows/docs.yml`:

```yaml
name: Docs

on:
  push:
    branches: [main]
    paths:
      - 'docs/**'
      - 'mkdocs.yml'
      - 'src/fertiscope/**'
      - '.github/workflows/docs.yml'

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: docs
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: uv sync --extra docs
      - run: uv run mkdocs build --strict --site-dir _site
      - uses: actions/upload-pages-artifact@v3
        with:
          path: _site

  deploy:
    needs: build
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

### Notes

- `mkdocstrings` auto-generates API docs from package docstrings — no duplication.
- `--strict` flag catches broken cross-references.
- GitHub Pages deploys to `https://dangpleo-ctrl.github.io/fertiscope/`. Enable Pages from `gh-pages`-style workflow under repo Settings → Pages → Source: GitHub Actions.
- The `concurrency` group prevents multiple parallel deploys.
- mkdocs-material's `instant` navigation makes the site feel like a SPA.

## Acceptance Criteria

- [ ] `mkdocs.yml` valid YAML.
- [ ] All nav items resolve to existing markdown files.
- [ ] `uv sync --extra docs && uv run mkdocs build --strict` succeeds with zero warnings.
- [ ] Local serve (`mkdocs serve`) renders the home page.
- [ ] CI workflow `docs.yml` runs on push to main.
- [ ] After first deploy: `https://dangpleo-ctrl.github.io/fertiscope/` returns 200.
- [ ] API reference page shows extracted docstrings (e.g. `aggregate.fertility_point` has signature and docstring).
- [ ] Dark mode toggle works.
- [ ] Code blocks have copy buttons.
- [ ] Search box returns results for "fertility", "tokenizer", "BPT".

## User Stories

### Story: New user reads the docs

1. Lands on the index page.
2. Sees quickstart.
3. Clicks "Install" → reads install matrix.
4. Clicks "Usage" → tries `fertiscope measure`.

### Story: Adapter author extends the package

1. Reads "Adding a tokenizer" playbook.
2. Sees the protocol, registry pattern, golden-test convention.
3. Implements an adapter for a new tokenizer in 30 minutes.

### Story: API discovery

1. Reader on "API reference" page.
2. Sees mkdocstrings-generated docs for every public function.
3. Code examples render inline.

---

Blocked by: #034
