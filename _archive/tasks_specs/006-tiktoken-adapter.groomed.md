# tiktoken adapter (cl100k, o200k, o200k_harmony) + golden tests

Status: pending
Tags: `tokenizers`, `tiktoken`, `openai`, `golden-tests`
Depends on: #005
Blocks: #009, #015, #019

## Scope

Wire the three OpenAI tiktoken encodings into the registry and pin their outputs with golden tests. After this task, `get_tokenizer("openai/o200k_base").count("hello world")` returns the canonical integer count and CI catches any future drift.

### Files to create

- `src/fertiscope/tokenizers/tiktoken_adapter.py`
- `tests/unit/test_tiktoken_adapter.py`
- `tests/golden/golden_counts_tiktoken.json`
- `tests/golden/test_golden_counts_tiktoken.py`

### Files to modify

- `src/fertiscope/tokenizers/__init__.py` — import the adapter at module load so registration runs.

### Interface and contract

`tiktoken_adapter.py`:

```python
from __future__ import annotations
from .base import TokenizerInfo, Tokenizer
from .registry import register

_TIKTOKEN_ENCODINGS = {
    "openai/o200k_base": ("o200k_base", TokenizerInfo(
        id="openai/o200k_base", family="openai", backend="tiktoken",
        gated=False, extra="oai",
        notes="GPT-4o, GPT-4.1, o-series, GPT-5",
    )),
    "openai/o200k_harmony": ("o200k_harmony", TokenizerInfo(
        id="openai/o200k_harmony", family="openai", backend="tiktoken",
        gated=False, extra="oai",
        notes="gpt-oss open-weight family",
    )),
    "openai/cl100k_base": ("cl100k_base", TokenizerInfo(
        id="openai/cl100k_base", family="openai", backend="tiktoken",
        gated=False, extra="oai",
        notes="GPT-3.5, GPT-4 (legacy)",
    )),
}


class TiktokenTokenizer:
    def __init__(self, info: TokenizerInfo, encoding_name: str) -> None:
        import tiktoken                       # imported here, not at module top
        self.info = info
        self._enc = tiktoken.get_encoding(encoding_name)

    def encode(self, text: str) -> list[int]:
        return self._enc.encode(text)

    def count(self, text: str) -> int:
        return len(self._enc.encode(text))


def _make_loader(info: TokenizerInfo, encoding_name: str):
    def _load() -> Tokenizer:
        return TiktokenTokenizer(info, encoding_name)
    return _load


def register_all() -> None:
    for _, (enc_name, info) in _TIKTOKEN_ENCODINGS.items():
        register(info, _make_loader(info, enc_name))


register_all()
```

`__init__.py` adds:

```python
from . import tiktoken_adapter as _tiktoken_adapter   # noqa: F401  — side effect: registration
```

(Wrap in try/except ImportError if tiktoken is not installed — the adapter file itself defers `import tiktoken` until loader call, so the file imports clean. But if a future maintainer adds a top-level `import tiktoken`, the try/except prevents `import fertiscope.tokenizers` from crashing.)

`tests/golden/golden_counts_tiktoken.json` — pinned counts for a known matrix. Use these exact strings:

```json
{
  "schema_version": "1.0",
  "tiktoken_version": "0.8.0",
  "snapshots": [
    {"id": "openai/o200k_base",   "text": "hello world",                                "count": 2},
    {"id": "openai/o200k_base",   "text": "Xin chào, thế giới",                         "count": 6},
    {"id": "openai/o200k_base",   "text": "வணக்கம், உலகம்",                            "count": 8},
    {"id": "openai/o200k_base",   "text": "မင်္ဂလာပါ ကမ္ဘာ",                            "count": 12},
    {"id": "openai/cl100k_base",  "text": "hello world",                                "count": 2},
    {"id": "openai/cl100k_base",  "text": "Xin chào, thế giới",                         "count": 9},
    {"id": "openai/cl100k_base",  "text": "வணக்கம், உலகம்",                            "count": 24},
    {"id": "openai/cl100k_base",  "text": "မင်္ဂလာပါ ကမ္ဘာ",                            "count": 36},
    {"id": "openai/o200k_harmony","text": "hello world",                                "count": 2}
  ]
}
```

> **Author's note**: the exact integer counts above are illustrative. The implementer MUST re-run them with the actual pinned tiktoken version and write the real outputs back. The values must be reproducible from tiktoken-0.8.0; if the implementer pins a newer version, update both the version field and any count that drifted.

`tests/golden/test_golden_counts_tiktoken.py`:

```python
import json, pathlib
import pytest
from fertiscope.tokenizers import get_tokenizer

GOLDEN = json.loads(pathlib.Path(__file__).parent.joinpath("golden_counts_tiktoken.json").read_text("utf-8"))

@pytest.mark.parametrize("snap", GOLDEN["snapshots"], ids=lambda s: f'{s["id"]}::{s["text"][:20]}')
def test_count_matches_golden(snap: dict) -> None:
    tok = get_tokenizer(snap["id"])
    actual = tok.count(snap["text"])
    assert actual == snap["count"], (
        f"\nTokenizer:  {snap['id']}\nText:       {snap['text']!r}"
        f"\nExpected:   {snap['count']}\nActual:     {actual}"
        "\nIf intentional (tiktoken upgrade), update golden_counts_tiktoken.json + tiktoken_version field."
    )
```

`tests/unit/test_tiktoken_adapter.py` covers:

- All 3 IDs appear in `list_tokenizers()`.
- Each ID has `backend == "tiktoken"`, `family == "openai"`, `gated == False`, `extra == "oai"`.
- `get_tokenizer("openai/o200k_base").encode("a")` returns a list of one int.
- `count("")` returns `0`.

### Notes

- The `import tiktoken` happens **inside the loader factory**, not at module top — this is what lets `import fertiscope` work when `tiktoken` is not installed (the registration still runs; `get_tokenizer` only fails when actually called).
- Golden tests run on the same matrix that the paper's leaderboard relies on. If they fail, the leaderboard would also drift — so the test failure is the canary.
- The `mar` (Burmese) string `မင်္ဂလာပါ ကမ္ဘာ` contains a virama and stacked consonant — known stress case for cl100k. Keep it in the golden set.
- `o200k_harmony` is the encoding used by OpenAI's open-weight `gpt-oss` family. Test coverage is lighter because the Asian-language tax matters less when the same vocab covers both.
- DO NOT add `tiktoken` to base `[project] dependencies` — it stays in `[oai]` extra.

## Acceptance Criteria

- [ ] `from fertiscope.tokenizers import list_tokenizers; len([t for t in list_tokenizers() if t.backend == "tiktoken"]) == 3`.
- [ ] `get_tokenizer("openai/o200k_base").count("hello world") == 2`.
- [ ] `golden_counts_tiktoken.json` exists with ≥ 9 snapshots covering ≥ 3 scripts (Latin, Tamil, Burmese).
- [ ] All golden tests pass on a freshly-installed `[oai]` extra.
- [ ] Tests in `test_tiktoken_adapter.py` pass.
- [ ] On a `pip install fertiscope` without `[oai]`: `from fertiscope.tokenizers import list_tokenizers` still works; `list_tokenizers()` still shows the 3 tiktoken rows; `get_tokenizer("openai/o200k_base")` raises `TokenizerUnavailable`.
- [ ] `pinned tiktoken version` field in `golden_counts_tiktoken.json` matches `tiktoken.__version__` of the installed package.
- [ ] `mypy --strict src/fertiscope/tokenizers/tiktoken_adapter.py` passes.

## User Stories

### Story: Researcher reproduces the paper's English baseline

1. Researcher runs `python -c "from fertiscope.tokenizers import get_tokenizer; print(get_tokenizer('openai/o200k_base').count('The cat sat on the mat.'))"`.
2. Gets exact integer, matches paper's English baseline calculation.
3. Confirms the implementation.

### Story: tiktoken 1.0 ships and breaks one count

1. `tiktoken==1.0.0` changes the o200k_base treatment of a specific Burmese cluster.
2. CI runs golden tests, `test_count_matches_golden[openai/o200k_base::မင်္ဂလာပါ ကမ္ဘာ]` fails with a clear diff message.
3. Maintainer investigates, decides this is intentional upstream, regenerates the golden JSON, bumps the version field, commits.

### Story: User without optional extras

1. `import fertiscope.tokenizers` works.
2. `list_tokenizers()` shows tiktoken rows.
3. `get_tokenizer("openai/o200k_base")` → `TokenizerUnavailable("openai/o200k_base", "missing extra 'oai': No module named 'tiktoken'")`.

---

Blocked by: #005
