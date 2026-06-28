# Wire pyproject.toml (hatchling, extras, uv-ready)

Status: pending
Tags: `packaging`, `pyproject`, `hatchling`, `uv`, `extras`
Depends on: #001
Blocks: #003, #004

## Scope

Drop a complete `pyproject.toml` at the repo root so `uv sync --all-extras` and `pip install -e .` both work. No code lives in `src/fertiscope/` yet beyond `__init__.py` — this task is about declaring the build, dependencies, and tooling configuration.

### Files to create

- `./pyproject.toml`
- `./src/fertiscope/__init__.py` — populate with `__version__ = "0.2.0"` and `__all__ = ["__version__"]`.

### Files to modify

- None.

### Interface and contract

`pyproject.toml` MUST contain exactly these sections (no more, no less, in this order):

```toml
[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"

[project]
name = "fertiscope"
version = "0.2.0"
description = "Tokenizer fertility, cost, and multi-turn context-budget analyzer for low-resource Asian languages."
authors = [
    { name = "Antoine Pedretti" },
    { name = "Leo Dang" },
    { name = "Miles Whiticker" },
    { name = "Vinh Van" },
]
license = { text = "MIT" }
readme = "README.md"
requires-python = ">=3.11"
keywords = ["tokenizer", "fertility", "multilingual", "llm", "low-resource", "asian-languages"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Science/Research",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]
dependencies = [
    "typer>=0.12",
    "rich>=13.7",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "pyyaml>=6.0",
    "numpy>=1.26",
]

[project.optional-dependencies]
oai  = ["tiktoken>=0.8"]
hf   = [
    "transformers>=4.44",
    "tokenizers>=0.20",
    "huggingface-hub>=0.25",
    "datasets>=2.21",
    "pythainlp>=5.0",
]
api  = ["anthropic>=0.40", "google-genai>=0.3", "httpx>=0.27"]
niah = ["httpx>=0.27", "tenacity>=8.5"]
viz  = ["matplotlib>=3.9", "pandas>=2.2", "pyarrow>=17"]
dev  = [
    "pytest>=8",
    "pytest-cov>=5",
    "pytest-asyncio>=0.23",
    "hypothesis>=6.112",
    "ruff>=0.6",
    "mypy>=1.11",
    "pre-commit>=3.8",
    "respx>=0.21",
]

[project.urls]
Homepage      = "https://fertiscope.vercel.app"
Repository    = "https://github.com/dangpleo-ctrl/fertiscope"
Documentation = "https://dangpleo-ctrl.github.io/fertiscope/"
Paper         = "https://arxiv.org/abs/26XX.XXXXX"

[project.scripts]
fertiscope = "fertiscope.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/fertiscope"]

[tool.hatch.build.targets.sdist]
include = ["src/fertiscope", "configs", "data", "tests", "README.md", "LICENSE"]

[tool.ruff]
line-length = 100
target-version = "py311"
extend-exclude = ["legacy_v01"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF", "ANN", "PT"]
ignore = ["ANN101", "ANN102"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["ANN", "S101"]

[tool.mypy]
strict = true
python_version = "3.11"
exclude = ["legacy_v01", "build", "dist"]

[[tool.mypy.overrides]]
module = ["tiktoken.*", "tokenizers.*", "pythainlp.*", "khmer_nltk.*", "icu.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: integration tests requiring network",
]
asyncio_mode = "auto"
```

### Notes

- **Use `hatchling`, not `setuptools` or `poetry-core`.** Hatchling is the modern PyPA-recommended backend, plays cleanest with `uv`.
- **`[project.optional-dependencies]` not `[dependency-groups]`.** Some tools still don't parse PEP-735 groups; optional-deps work everywhere.
- The `oai` extra installs only `tiktoken` so a minimum-dep install (just typer + tiktoken) is < 10MB.
- `pythainlp` is in `[hf]` not `[oai]` because Thai segmentation is paired with HF-tokenized study runs in practice. Document this in #017.
- `respx` is a mock for `httpx` — required by #029 NIAH tests.
- The `Paper` URL is a placeholder until arXiv v2 lands in #035.

## Acceptance Criteria

- [ ] `uv venv && uv sync --all-extras` succeeds on a clean Ubuntu and macOS box.
- [ ] `uv pip install -e .` (no extras) succeeds with only `typer`, `rich`, `pydantic`, `pydantic-settings`, `pyyaml`, `numpy` installed.
- [ ] `python -c "import fertiscope; print(fertiscope.__version__)"` prints `0.2.0`.
- [ ] `uv build` produces both `dist/fertiscope-0.2.0-py3-none-any.whl` and `dist/fertiscope-0.2.0.tar.gz`.
- [ ] The wheel contains `src/fertiscope/__init__.py` and no files from `legacy_v01/`.
- [ ] The sdist contains `configs/`, `data/`, `tests/`, `README.md`, `LICENSE`.
- [ ] `uv run ruff check .` runs (may report findings — that's fine; this task only checks config validity).
- [ ] `uv run mypy src/fertiscope` runs without configuration error.
- [ ] `pyproject.toml` validates against `pep621` (use `validate-pyproject pyproject.toml`).

## User Stories

### Story: Minimum-install contributor

1. `pip install fertiscope` (no extras).
2. Gets ~10MB of deps (typer, rich, pydantic, yaml, numpy).
3. Imports `fertiscope.__version__`.
4. Tries `fertiscope tokenizers list` → sees tiktoken tokenizers as `unavailable: missing extra 'oai'` (clean message, no crash).

### Story: Full-stack researcher

1. `pip install "fertiscope[oai,hf,api,niah,viz,dev]"`.
2. Gets everything — tiktoken, transformers, datasets, anthropic, httpx, matplotlib, pyarrow, pytest.
3. All study + NIAH paths work.

### Story: CI caches deps

1. CI uses `uv pip compile pyproject.toml --extra dev -o requirements-dev.txt` to lock.
2. Same lock file → reproducible deps across CI runs.

---

Blocked by: #001
