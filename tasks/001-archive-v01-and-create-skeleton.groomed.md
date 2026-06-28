# Archive v0.1 and create the src/ skeleton

Status: pending
Tags: `bootstrap`, `repo-layout`, `housekeeping`
Depends on: None
Blocks: #002, #003, #004

## Scope

Move the existing v0.1 Python prototype out of the way and create the empty target directory tree. No build system, no CLI, no code — just folders and placeholder files. The next task (#002) drops `pyproject.toml` into the cleaned tree.

### Files/directories to move

- `./fertiscope/` → `./legacy_v01/fertiscope/`
- `./neddle_degradation/` → `./legacy_v01/neddle_degradation/`
- `./fertiscope.egg-info/` → DELETE (regenerable build artifact).
- `./pyproject.toml` (current v0.1 one) → `./legacy_v01/pyproject.toml`
- `./README.md` (current v0.1 one) → `./legacy_v01/README.md`
- `./demo.py` → `./legacy_v01/demo.py`
- `./crawl_baochinhphu.py`, `./crawl.log`, `./crawl_output/` → `./legacy_v01/` (used later by #041 if Item E chosen).

### Files/directories to create

```
src/fertiscope/
src/fertiscope/__init__.py        # empty for now, populated in #003
tests/
tests/__init__.py
tests/unit/
tests/unit/__init__.py
tests/integration/
tests/integration/__init__.py
tests/golden/
tests/golden/__init__.py
configs/                          # populated from #004, #020, #023 onward
data/                             # populated from #011, #014 onward
data/reference_suite/             # populated in #014
docs/                             # populated from #037
.github/
.github/workflows/
```

### Files to create at repo root

- `LICENSE` — MIT, © 2026 Antoine Pedretti, Leo Dang, Miles Whiticker, Vinh Van.
- `.gitignore` — ignore `.venv/`, `dist/`, `build/`, `*.egg-info/`, `runs/`, `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/`, `__pycache__/`, `.env`, `~/.cache/fertiscope/`.
- `.python-version` — single line: `3.12`.
- `README.md` — minimal, three sections: title, "FertiScope v0.2 — under construction", link to `ROADMAP.md` + `tasks/`. The full README ships in #034.

### Notes

- DO NOT delete `legacy_v01/` later — it's the reference for paper §3 reproduction of v0.1 results.
- DO NOT touch `fertiscope-web/` (the deployed Next.js app) or `token_degradation_fertility/` (Miles' repo) — both stay as sibling directories.
- Keep `89e8286a-…-FertiScope.txt` and `.pdf` (the paper) at root.
- Keep `RELATED_WORK_BRAINSTORM.md` and `ROADMAP.md` at root.

## Acceptance Criteria

- [ ] `./legacy_v01/fertiscope/__init__.py` exists (proves v0.1 was moved, not deleted).
- [ ] `./legacy_v01/neddle_degradation/` exists with its previous contents.
- [ ] No `./fertiscope/` directory at repo root (avoid name collision with new `src/fertiscope/`).
- [ ] `./src/fertiscope/__init__.py` exists and is empty (size 0).
- [ ] `./tests/{unit,integration,golden}/__init__.py` all exist.
- [ ] `./LICENSE` contains MIT text with 2026 © line listing all four authors.
- [ ] `.python-version` is one line, `3.12`, no trailing characters.
- [ ] `git status` shows the moves as renames (`R`), not delete+add.
- [ ] `find . -name "*.egg-info" -not -path "./legacy_v01/*"` returns empty.
- [ ] `./README.md` at root is < 30 lines and references `tasks/` and `ROADMAP.md`.

## User Stories

### Story: Contributor opens the repo for the first time

1. Runs `tree -L 2 -I 'legacy_v01|fertiscope-web|token_degradation_fertility|crawl_output'`.
2. Sees the clean target structure: `src/fertiscope/`, `tests/`, `configs/`, `docs/`, `.github/`.
3. Understands the layout without reading anything else.

### Story: Reviewer reproduces v0.1 paper numbers

1. `cd legacy_v01 && pip install -e . && fertiscope demo`.
2. Gets the original v0.1 EN↔VI fertility table.
3. Confirms v0.1 is untouched and remains reproducible.

### Story: CI doesn't accidentally test legacy code

1. `pytest` finds `tests/` only.
2. `legacy_v01/` is outside the testroots and pytest never enters it.
3. No accidental coupling between v0.1 and v0.2.

---

Blocked by: (none)
