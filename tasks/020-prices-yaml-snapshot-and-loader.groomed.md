# Prices YAML snapshot + loader (no silent fallback)

Status: pending
Tags: `cost`, `prices`, `yaml`, `pydantic`, `provenance`
Depends on: #004
Blocks: #022, #023

## Scope

Ship dated vendor pricing as a YAML snapshot that the cost calculator and study runner consume by path. The loader validates with pydantic, refuses to silently fall back when an explicit path doesn't exist, and computes a SHA256 hash for the manifest.

### Files to create

- `configs/prices_2026-06.yaml` — repo-root config used by `fertiscope run --config …`.
- `src/fertiscope/_defaults/prices_2026-06.yaml` — **bundled with the wheel** so a `pip install fertiscope` user can still compute costs out of the box.
- `src/fertiscope/cost/__init__.py`
- `src/fertiscope/cost/prices.py`
- `src/fertiscope/cost/exceptions.py`
- `tests/unit/test_prices.py`
- `tests/unit/fixtures/prices_minimal.yaml`

### Files to modify

- `pyproject.toml` — confirm `_defaults/` is included in the wheel.

### Interface and contract

`configs/prices_2026-06.yaml`:

```yaml
schema_version: "1.0"
snapshot_date: 2026-06-28
source_notes: "Vendor pricing pages, fetched 2026-06-28. Manual record; see docs/updating_prices.md."
currency: USD
unit: per_1M_tokens
models:
  openai/gpt-5:
    tokenizer: openai/o200k_base
    input: 1.25
    output: 10.00
    context_window: 200000
    hosted: openai
  openai/gpt-4o:
    tokenizer: openai/o200k_base
    input: 2.50
    output: 10.00
    context_window: 128000
    hosted: openai
  openai/gpt-4o-mini:
    tokenizer: openai/o200k_base
    input: 0.15
    output: 0.60
    context_window: 128000
    hosted: openai
  openai/gpt-4-turbo:
    tokenizer: openai/cl100k_base
    input: 10.00
    output: 30.00
    context_window: 128000
    hosted: openai
  openai/gpt-3.5-turbo:
    tokenizer: openai/cl100k_base
    input: 0.50
    output: 1.50
    context_window: 16385
    hosted: openai
  anthropic/claude-opus-4-7:
    tokenizer: anthropic/claude
    input: 15.00
    output: 75.00
    context_window: 200000
    hosted: anthropic
  anthropic/claude-sonnet-4-6:
    tokenizer: anthropic/claude
    input: 3.00
    output: 15.00
    context_window: 200000
    hosted: anthropic
  anthropic/claude-haiku-4-5:
    tokenizer: anthropic/claude
    input: 0.80
    output: 4.00
    context_window: 200000
    hosted: anthropic
  google/gemini-2.5-pro:
    tokenizer: google/gemini
    input: 1.25
    output: 5.00
    context_window: 2000000
    hosted: google
  meta/llama-3.1-8b-instruct:
    tokenizer: meta/llama-3.1
    input: 0.20
    output: 0.20
    context_window: 131072
    hosted: openrouter
  meta/llama-4-scout-17b:
    tokenizer: meta/llama-4
    input: 0.50
    output: 1.50
    context_window: 256000
    hosted: openrouter
  google/gemma-4-27b:
    tokenizer: google/gemma-4
    input: 0.40
    output: 0.40
    context_window: 128000
    hosted: openrouter
  qwen/qwen3-72b-instruct:
    tokenizer: qwen/qwen3
    input: 0.60
    output: 1.20
    context_window: 131072
    hosted: openrouter
  deepseek/deepseek-v3:
    tokenizer: deepseek/v3
    input: 0.30
    output: 1.20
    context_window: 131072
    hosted: openrouter
  mistral/mistral-large:
    tokenizer: mistral/tekken
    input: 2.00
    output: 6.00
    context_window: 131072
    hosted: openrouter
  cohere/aya-expanse-8b:
    tokenizer: cohere/aya-expanse
    input: 0.30
    output: 0.30
    context_window: 32768
    hosted: openrouter
```

`src/fertiscope/_defaults/prices_2026-06.yaml` — identical content (or a symlink in dev, real copy in the built wheel via hatchling's file inclusion). Document the policy: only the most recent snapshot ships in `_defaults/`; older snapshots live only in `configs/`.

`src/fertiscope/cost/exceptions.py`:

```python
class CostError(Exception): ...
class PricesNotFound(CostError): ...
class FXNotFound(CostError): ...
class ModelNotInPrices(CostError): ...
```

`src/fertiscope/cost/prices.py`:

```python
from __future__ import annotations
import hashlib
from datetime import date
from pathlib import Path
from importlib.resources import files
from pydantic import BaseModel, Field, ConfigDict
import yaml

from .exceptions import PricesNotFound, ModelNotInPrices


class ModelPricing(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tokenizer: str
    input: float = Field(ge=0)
    output: float = Field(ge=0)
    context_window: int = Field(gt=0)
    hosted: str


class PriceTable(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str
    snapshot_date: date
    source_notes: str
    currency: str = "USD"
    unit: str = "per_1M_tokens"
    models: dict[str, ModelPricing]

    def get(self, model_id: str) -> ModelPricing:
        if model_id not in self.models:
            raise ModelNotInPrices(f"Model '{model_id}' not in prices snapshot {self.snapshot_date}")
        return self.models[model_id]


def _bundled_default_path() -> Path:
    """The single bundled price snapshot (most recent)."""
    return Path(str(files("fertiscope._defaults").joinpath("prices_2026-06.yaml")))


def load_prices(path: str | Path | None = None) -> PriceTable:
    """Load prices.

    - path=None → bundled default. Logs which date is in use.
    - path=str  → exact path. Raises PricesNotFound if missing. NO fallback.
    """
    if path is None:
        actual = _bundled_default_path()
    else:
        actual = Path(path)
        if not actual.exists():
            raise PricesNotFound(f"Prices file not found: {actual}. No silent fallback to bundled default.")
    raw = yaml.safe_load(actual.read_text("utf-8"))
    return PriceTable.model_validate(raw)


def prices_sha256(path: str | Path | None = None) -> str:
    if path is None:
        actual = _bundled_default_path()
    else:
        actual = Path(path)
        if not actual.exists():
            raise PricesNotFound(str(actual))
    return hashlib.sha256(actual.read_bytes()).hexdigest()
```

`src/fertiscope/cost/__init__.py`:

```python
from .prices  import load_prices, prices_sha256, PriceTable, ModelPricing
from .exceptions import CostError, PricesNotFound, FXNotFound, ModelNotInPrices

__all__ = [
    "load_prices", "prices_sha256", "PriceTable", "ModelPricing",
    "CostError", "PricesNotFound", "FXNotFound", "ModelNotInPrices",
]
```

`tests/unit/test_prices.py`:

```python
import pytest
from pathlib import Path
from fertiscope.cost import load_prices, prices_sha256, PricesNotFound, ModelNotInPrices

FIX = Path(__file__).parent / "fixtures" / "prices_minimal.yaml"

def test_load_bundled_default():
    table = load_prices()
    assert table.schema_version == "1.0"
    assert table.currency == "USD"
    assert "openai/gpt-4o" in table.models

def test_load_explicit_path():
    table = load_prices(FIX)
    assert "test/model" in table.models

def test_explicit_path_missing_raises():
    with pytest.raises(PricesNotFound, match="No silent fallback"):
        load_prices("/nonexistent/path/prices.yaml")

def test_extra_field_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "schema_version: '1.0'\n"
        "snapshot_date: 2026-01-01\n"
        "source_notes: x\n"
        "models:\n"
        "  a/b: {tokenizer: x, input: 1, output: 2, context_window: 100, hosted: openai, weird_field: yes}\n",
        encoding="utf-8",
    )
    with pytest.raises(Exception):    # pydantic ValidationError
        load_prices(bad)

def test_get_model_pricing():
    table = load_prices()
    p = table.get("openai/gpt-4o")
    assert p.input > 0 and p.output > 0
    assert p.context_window == 128000

def test_get_unknown_model_raises():
    table = load_prices()
    with pytest.raises(ModelNotInPrices):
        table.get("not/a/real/model")

def test_sha256_stable():
    h1 = prices_sha256()
    h2 = prices_sha256()
    assert h1 == h2
    assert len(h1) == 64
```

`tests/unit/fixtures/prices_minimal.yaml`:

```yaml
schema_version: "1.0"
snapshot_date: 2026-06-01
source_notes: test fixture
currency: USD
unit: per_1M_tokens
models:
  test/model:
    tokenizer: openai/o200k_base
    input: 1.0
    output: 2.0
    context_window: 8192
    hosted: test
```

### Notes

- **Use `pydantic.ConfigDict(extra="forbid")`** so a typo in a new YAML field fails loud at load time.
- Prices are floats per 1M tokens. Document this unit in the schema_version comment so future readers don't double-divide.
- The `_defaults/` copy is what the bundled wheel ships. When prices_2026-12.yaml is added in v0.3, replace the `_defaults/` copy and bump version. Old `configs/prices_2026-06.yaml` lives on for historical reproduction.
- DO NOT add a `--use-default-on-missing` flag. The whole point is no silent fallback.
- `prices_sha256` is consumed by the manifest builder (#025).

## Acceptance Criteria

- [ ] `load_prices()` returns a `PriceTable` from the bundled `_defaults/prices_2026-06.yaml`.
- [ ] `load_prices()` table contains ≥ 15 models covering ≥ 6 model families.
- [ ] `load_prices("/nonexistent")` raises `PricesNotFound` with "No silent fallback" in message.
- [ ] An unknown YAML field raises pydantic ValidationError.
- [ ] `table.get("openai/gpt-4o").input > 0`.
- [ ] `table.get("not/real")` raises `ModelNotInPrices`.
- [ ] `prices_sha256()` returns a stable 64-char hex.
- [ ] The wheel built by #002 contains `_defaults/prices_2026-06.yaml` (verify with `unzip -l dist/*.whl`).
- [ ] All 7 unit tests pass.
- [ ] `mypy --strict src/fertiscope/cost/` passes.

## User Stories

### Story: User computes cost with bundled defaults

1. `pip install fertiscope[oai]`.
2. `fertiscope cost --text "..." --lang vie --models openai/gpt-4o`.
3. Cost computed using the bundled `_defaults/prices_2026-06.yaml`.
4. CLI prints "Using prices snapshot 2026-06-28" so user knows what's in play.

### Story: Reviewer reproduces a paper figure

1. Paper figure caption: "Computed against `configs/prices_2026-06.yaml`, SHA `abc1234`."
2. Reviewer fetches that exact file, computes `prices_sha256()` locally.
3. Hash matches → reproducibility confirmed.

### Story: v0.3 ships with refreshed prices

1. Maintainer adds `configs/prices_2026-12.yaml` and `_defaults/prices_2026-12.yaml`.
2. v0.3 release notes call out the snapshot date bump.
3. v0.2 results are still reproducible by pinning v0.2 + the old config.

---

Blocked by: #004
