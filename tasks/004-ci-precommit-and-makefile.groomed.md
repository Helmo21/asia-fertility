# CI workflow, pre-commit hooks, and Makefile

Status: pending
Tags: `ci`, `github-actions`, `pre-commit`, `makefile`, `quality-gate`
Depends on: #002, #003
Blocks: #006, #015 (every later task relies on CI being green)

## Scope

Stand up the developer-experience quality gates so every later PR has a fast feedback loop. After this task lands, a draft PR with garbage code goes red and a clean PR goes green within 90 seconds.

### Files to create

- `.github/workflows/ci.yml`
- `.pre-commit-config.yaml`
- `Makefile`
- `.editorconfig`

### Files to modify

- None.

### Interface and contract

`.github/workflows/ci.yml`:

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - run: uv sync --extra dev --extra oai
      - run: uv run ruff format --check .
      - run: uv run ruff check .
      - run: uv run mypy src/fertiscope

  test:
    needs: lint
    strategy:
      fail-fast: false
      matrix:
        python: ["3.11", "3.12", "3.13"]
        os: [ubuntu-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
      - run: uv sync --extra dev --extra oai
      - run: uv run pytest -q --cov=fertiscope --cov-report=term-missing -m "not slow and not integration"

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv build
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
```

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-merge-conflict
      - id: check-added-large-files
        args: ["--maxkb=500"]
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff-format
      - id: ruff
        args: ["--fix"]
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.2
    hooks:
      - id: mypy
        additional_dependencies: ["pydantic>=2.7", "types-PyYAML"]
        files: ^src/fertiscope/
```

`Makefile`:

```makefile
.PHONY: install format format-check lint test test-fast test-slow test-integration cov build clean reproduce

install:
	uv venv
	uv sync --all-extras
	uv run pre-commit install

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

lint:
	uv run ruff check . --fix
	uv run mypy src/fertiscope

lint-check:
	uv run ruff check .
	uv run mypy src/fertiscope

test:
	uv run pytest -q -m "not slow and not integration"

test-fast:
	uv run pytest -q -m "not slow and not integration" --no-cov

test-slow:
	uv run pytest -q -m "slow"

test-integration:
	uv run pytest -q -m "integration"

cov:
	uv run pytest --cov=fertiscope --cov-report=html --cov-report=term-missing

build:
	uv build

reproduce:
	uv run fertiscope reproduce

clean:
	rm -rf .ruff_cache .mypy_cache .pytest_cache htmlcov dist build *.egg-info
	find . -type d -name __pycache__ -not -path "./legacy_v01/*" -exec rm -rf {} +
```

`.editorconfig`:

```ini
root = true

[*]
end_of_line = lf
insert_final_newline = true
charset = utf-8
trim_trailing_whitespace = true

[*.py]
indent_style = space
indent_size = 4

[*.{yml,yaml,toml,json}]
indent_style = space
indent_size = 2

[Makefile]
indent_style = tab
```

### Notes

- **Use `astral-sh/setup-uv@v3`**, not setup-python + pip. It's the fastest CI path for uv-managed projects.
- Job ordering: `lint` first (cheap, ~30s) → `test` matrix (parallel) → `build` (artifact).
- The `concurrency` block auto-cancels stale CI runs when a PR is updated.
- Slow + integration tests are excluded from the default PR check; they get their own opt-in jobs in later tasks (#012, #024).
- `check-added-large-files --maxkb=500` blocks accidentally committing FLORES dev splits or PNG figures > 500KB.
- `mypy` in pre-commit only scans `src/fertiscope/` — tests are not type-strict.

## Acceptance Criteria

- [ ] `make install` succeeds on a clean checkout (creates `.venv`, installs all extras, installs pre-commit hook).
- [ ] `make format && make lint-check && make test` exit 0 on the current main (post-#003).
- [ ] `git commit` triggers pre-commit hooks; deliberately bad whitespace or a syntax error blocks the commit.
- [ ] On a draft PR with one valid trivial change, CI completes in < 3 minutes (lint + test 3.11/3.12/3.13 + build).
- [ ] On a draft PR with a `ruff check` violation, the `lint` job fails with the exact rule code in the log.
- [ ] On a draft PR with `mypy --strict` violation in `src/fertiscope/`, lint fails.
- [ ] On a draft PR adding a 600KB binary, pre-commit blocks the commit locally; if pushed bypassing pre-commit, CI does NOT fail (pre-commit is local-only — that's expected; #008 will add a CI-side check via `actions/dependency-review`).
- [ ] The `concurrency.cancel-in-progress` correctly cancels a stale CI run when a PR is force-pushed.
- [ ] `make clean` removes all generated artifacts but does not touch `legacy_v01/` or `src/fertiscope/`.

## User Stories

### Story: Solo contributor catches a regression locally

1. Writes a function with a missing type annotation.
2. Runs `git commit` → pre-commit blocks: "Missing type annotation".
3. Fixes, recommits, pushes — CI is green.

### Story: PR review

1. PR opened, three checks appear: `lint`, `test (3.11)`, `test (3.12)`, `test (3.13)`, `build`.
2. Reviewer waits ~90 seconds, sees green.
3. Merges without local testing.

### Story: Force-push cancels stale runs

1. Author pushes commit A → CI starts.
2. Author force-pushes commit B 10s later.
3. GitHub Actions auto-cancels CI for A, runs CI for B.
4. No wasted minutes.

---

Blocked by: #002, #003
