# HuggingFace adapter (8 tokenizer families)

Status: pending
Tags: `tokenizers`, `huggingface`, `transformers`, `hf-token`, `gated-models`
Depends on: #005
Blocks: #009, #015, #019

## Scope

Wire 8 HuggingFace-hosted tokenizers behind the registry. Gated repos (Llama, Gemma) require `HF_TOKEN`; ungated repos (Mistral Tekken, Qwen3, DeepSeek v3, BLOOM, Aya Expanse) work without one. Missing tokens or repo-access denials produce clean `TokenizerUnavailable` errors, never crashes.

### Files to create

- `src/fertiscope/tokenizers/hf_adapter.py`
- `tests/unit/test_hf_adapter.py`
- `tests/golden/golden_counts_hf.json` — populated by maintainer once tokenizers are downloadable; CI uses it only when `HF_TOKEN` env var is set.
- `tests/golden/test_golden_counts_hf.py`

### Files to modify

- `src/fertiscope/tokenizers/__init__.py` — import `hf_adapter` for registration side effect (wrapped in try/except ImportError so it stays optional).

### Interface and contract

`hf_adapter.py`:

```python
from __future__ import annotations
import os
from .base import TokenizerInfo, Tokenizer
from .registry import register
from .exceptions import TokenizerUnavailable

_HF_TOKENIZERS = {
    "meta/llama-3.1":      ("meta-llama/Llama-3.1-8B",          "meta",       True,  "Same tokenizer as SEA-LION v3"),
    "meta/llama-4":        ("meta-llama/Llama-4-Scout-17B-16E", "meta",       True,  ""),
    "google/gemma-4":      ("google/gemma-4-27b",               "google",     True,  ""),
    "mistral/tekken":      ("mistralai/Mistral-Nemo-Base-2407", "mistral",    False, "Tekken tokenizer"),
    "qwen/qwen3":          ("Qwen/Qwen3-8B",                    "qwen",       False, ""),
    "deepseek/v3":         ("deepseek-ai/DeepSeek-V3",          "deepseek",   False, ""),
    "bigscience/bloom":    ("bigscience/bloom",                 "bigscience", False, "Multilingual baseline"),
    "cohere/aya-expanse":  ("CohereForAI/aya-expanse-8b",       "cohere",     False, "Multilingual-optimized baseline"),
}


class HuggingFaceTokenizer:
    def __init__(self, info: TokenizerInfo, repo_id: str) -> None:
        from transformers import AutoTokenizer            # type: ignore
        token = os.environ.get("HF_TOKEN")
        try:
            self._tok = AutoTokenizer.from_pretrained(
                repo_id, token=token, trust_remote_code=False, use_fast=True,
            )
        except OSError as e:
            # Distinguish gated-access denial from network failure
            msg = str(e).lower()
            if "401" in msg or "gated" in msg or "access" in msg:
                raise TokenizerUnavailable(info.id, "gated repo, HF_TOKEN missing or lacks license access") from e
            raise TokenizerUnavailable(info.id, f"failed to download tokenizer: {e}") from e
        self.info = info

    def encode(self, text: str) -> list[int]:
        return self._tok.encode(text, add_special_tokens=False)

    def count(self, text: str) -> int:
        return len(self.encode(text))


def _make_loader(info: TokenizerInfo, repo_id: str):
    def _load() -> Tokenizer:
        return HuggingFaceTokenizer(info, repo_id)
    return _load


def register_all() -> None:
    for tid, (repo_id, family, gated, notes) in _HF_TOKENIZERS.items():
        info = TokenizerInfo(
            id=tid,
            family=family,                       # type: ignore[arg-type]
            backend="hf",
            gated=gated,
            extra="hf",
            notes=notes,
        )
        register(info, _make_loader(info, repo_id))


register_all()
```

`__init__.py` change:

```python
try:
    from . import hf_adapter as _hf_adapter   # noqa: F401
except ImportError:
    # transformers not installed; HF tokenizers will appear in list_tokenizers() with unavailable status only
    # after they are explicitly registered. To allow listing without the extra, register stub infos here.
    from .base import TokenizerInfo
    from .registry import register
    for tid, _ in [
        ("meta/llama-3.1", None), ("meta/llama-4", None), ("google/gemma-4", None),
        ("mistral/tekken", None), ("qwen/qwen3", None), ("deepseek/v3", None),
        ("bigscience/bloom", None), ("cohere/aya-expanse", None),
    ]:
        # Register a placeholder loader that always fails with TokenizerUnavailable
        ...   # left as exercise: see Notes
```

> **Implementation note**: a cleaner pattern is to **always register** the `TokenizerInfo` rows in a separate module that has no heavy imports, then the loaders live in `hf_adapter.py` which is imported lazily. That way `list_tokenizers()` returns the full list even without `transformers` installed. Implementer chooses whichever is cleaner; the AC is "list shows all 8 even without `[hf]` extra".

`tests/unit/test_hf_adapter.py` covers:

- All 8 IDs appear in `list_tokenizers()`.
- Each has `backend == "hf"`, correct `family`, `extra == "hf"`.
- `meta/llama-3.1`, `meta/llama-4`, `google/gemma-4` have `gated == True`.
- The other 5 have `gated == False`.
- With `HF_TOKEN` unset and trying to load Llama-3.1: raises `TokenizerUnavailable` with reason mentioning "gated".
- With `transformers` uninstalled (simulated via `monkeypatch`): `list_tokenizers()` still returns 8 HF rows; `get_tokenizer("meta/llama-3.1")` raises `TokenizerUnavailable` with reason mentioning extras.
- Use `respx` or `pytest-httpx` mock to avoid actually hitting HF on test runs.

`tests/golden/test_golden_counts_hf.py`:

- `@pytest.mark.skipif(not os.environ.get("HF_TOKEN"), reason="needs HF_TOKEN")` on gated tokenizers.
- For ungated (Mistral, Qwen, DeepSeek, BLOOM, Aya): pin counts on the canonical fixture strings.
- Marked `@pytest.mark.slow` because the first run downloads ~50MB per tokenizer.

`tests/golden/golden_counts_hf.json` — initial content:

```json
{
  "schema_version": "1.0",
  "snapshots": [
    {"id": "mistral/tekken",    "text": "hello world", "count": null, "comment": "fill on first real run"},
    {"id": "qwen/qwen3",        "text": "hello world", "count": null},
    {"id": "bigscience/bloom",  "text": "hello world", "count": null}
  ]
}
```

> Implementer fills `null` counts on first real run, commits the numbers.

### Notes

- **HuggingFace caches downloaded tokenizers at `~/.cache/huggingface/hub/`**. Document this in README; users on small disks should know.
- The Llama-3.1 tokenizer is **identical** to SEA-LION v3's (the paper relies on this) — record in the `notes` field. Do NOT register a separate `seallm/v3` entry; users explicitly call `meta/llama-3.1` and the leaderboard column is labeled "Llama-3.1 / SEA-LION v3".
- Llama-4 and Gemma-4 require accepting their licenses on huggingface.co. Document the workflow in `docs/methodology.md` (#037).
- DeepSeek v3 may use a custom tokenizer class — verify `use_fast=True` works; if not, fall back to slow tokenizer.
- Aya Expanse repo is `CohereForAI/aya-expanse-8b`. Cohere has multiple variants; pick the 8B for consistency.

## Acceptance Criteria

- [ ] `list_tokenizers()` includes all 8 HF tokenizer rows even when `transformers` is not installed.
- [ ] With `[hf]` extra installed but no `HF_TOKEN`: `get_tokenizer("meta/llama-3.1")` raises `TokenizerUnavailable` whose `.reason` contains "gated".
- [ ] With `[hf]` extra installed, `get_tokenizer("mistral/tekken")` succeeds (downloads + caches on first call).
- [ ] `get_tokenizer("mistral/tekken").count("hello world") > 0`.
- [ ] Without `[hf]` extra: `get_tokenizer("mistral/tekken")` raises `TokenizerUnavailable` mentioning extra `'hf'`.
- [ ] Gated tokenizers (`meta/llama-3.1`, `meta/llama-4`, `google/gemma-4`) all have `gated == True`.
- [ ] All HF golden tests pass with `HF_TOKEN` set and after license acceptance.
- [ ] HF golden tests are skipped (not failed) when `HF_TOKEN` is missing.
- [ ] `mypy --strict src/fertiscope/tokenizers/hf_adapter.py` passes.

## User Stories

### Story: Researcher with full access runs the leaderboard

1. Accepts Llama-4 + Gemma-4 licenses on huggingface.co.
2. Exports `HF_TOKEN`.
3. `pip install "fertiscope[hf,oai]"`.
4. `fertiscope tokenizers list --available-only` shows 11 tokenizers (3 tiktoken + 8 HF).
5. Runs the study with all 11.

### Story: Lightweight CI

1. CI has no `HF_TOKEN` and no `[hf]` extra.
2. `fertiscope tokenizers list` shows all 11 with HF rows marked `unavailable`.
3. CI test only exercises tiktoken paths.
4. Lightweight + fast.

### Story: Drift detection on Mistral Tekken

1. Mistral ships a new Tekken vocabulary in `Mistral-Nemo-Base-2410`.
2. Implementer points `mistral/tekken` to the new repo.
3. Golden test fails on `hello world` count.
4. Implementer decides to keep the old repo for stability; reverts pointer.

---

Blocked by: #005
