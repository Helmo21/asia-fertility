# FX YAML snapshot + loader

Status: pending
Tags: `cost`, `fx`, `currency`, `yaml`, `provenance`
Depends on: #020
Blocks: #022

## Scope

Mirror of #020 for foreign exchange rates. Pinned, dated, pydantic-validated. Required so the cost calculator can report VND/IDR/MYR/etc. without re-fetching live rates.

### Files to create

- `configs/fx_2026-06.yaml`
- `src/fertiscope/_defaults/fx_2026-06.yaml`
- `src/fertiscope/cost/fx.py`
- `tests/unit/test_fx.py`
- `tests/unit/fixtures/fx_minimal.yaml`

### Files to modify

- `src/fertiscope/cost/__init__.py` — export `load_fx`, `fx_sha256`, `FXTable`.

### Interface and contract

`configs/fx_2026-06.yaml`:

```yaml
schema_version: "1.0"
snapshot_date: 2026-06-28
source: "ECB reference rates + cross-rates derived from USD/EUR, fetched 2026-06-28"
base: USD
rates:
  # Target-region currencies (mandatory for the 16-language study)
  VND: 25400.0        # Vietnam dong
  IDR: 16280.0        # Indonesian rupiah
  MYR: 4.72           # Malaysian ringgit
  THB: 36.50          # Thai baht
  PHP: 58.30          # Philippine peso
  INR: 83.10          # Indian rupee
  BDT: 109.50         # Bangladeshi taka
  LKR: 295.00         # Sri Lankan rupee
  MMK: 2100.00        # Myanmar kyat
  KHR: 4100.00        # Cambodian riel
  LAK: 21500.00       # Lao kip

  # Sanity-check reserve currencies
  USD: 1.0
  EUR: 0.92
  GBP: 0.79
  JPY: 156.80
  CNY: 7.25
  KRW: 1340.00
  TWD: 31.20
  SGD: 1.35
  HKD: 7.82
```

`src/fertiscope/_defaults/fx_2026-06.yaml` — identical content (bundled).

`src/fertiscope/cost/fx.py`:

```python
from __future__ import annotations
import hashlib
from datetime import date
from pathlib import Path
from importlib.resources import files
from pydantic import BaseModel, Field, ConfigDict
import yaml

from .exceptions import FXNotFound


class FXTable(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str
    snapshot_date: date
    source: str
    base: str
    rates: dict[str, float] = Field(min_length=1)

    def convert(self, amount_usd: float, target_currency: str) -> float:
        if self.base != "USD":
            raise ValueError(f"Only USD base supported; got base={self.base}")
        if target_currency not in self.rates:
            raise FXNotFound(f"Currency '{target_currency}' not in FX snapshot {self.snapshot_date}. Available: {sorted(self.rates)}")
        return amount_usd * self.rates[target_currency]


def _bundled_default_path() -> Path:
    return Path(str(files("fertiscope._defaults").joinpath("fx_2026-06.yaml")))


def load_fx(path: str | Path | None = None) -> FXTable:
    if path is None:
        actual = _bundled_default_path()
    else:
        actual = Path(path)
        if not actual.exists():
            raise FXNotFound(f"FX file not found: {actual}. No silent fallback.")
    raw = yaml.safe_load(actual.read_text("utf-8"))
    return FXTable.model_validate(raw)


def fx_sha256(path: str | Path | None = None) -> str:
    actual = _bundled_default_path() if path is None else Path(path)
    if not actual.exists():
        raise FXNotFound(str(actual))
    return hashlib.sha256(actual.read_bytes()).hexdigest()
```

`tests/unit/test_fx.py`:

```python
import pytest
from pathlib import Path
from fertiscope.cost.fx import load_fx, fx_sha256
from fertiscope.cost.exceptions import FXNotFound

FIX = Path(__file__).parent / "fixtures" / "fx_minimal.yaml"

def test_bundled_default():
    fx = load_fx()
    assert fx.base == "USD"
    assert "VND" in fx.rates
    assert "USD" in fx.rates and fx.rates["USD"] == 1.0

def test_required_asian_currencies_present():
    fx = load_fx()
    asian = {"VND","IDR","MYR","THB","PHP","INR","BDT","LKR","MMK","KHR","LAK"}
    assert asian <= set(fx.rates)

def test_convert_usd_to_vnd():
    fx = load_fx()
    v = fx.convert(1.0, "VND")
    assert 20000 <= v <= 30000   # sanity-bracket for 2026 VND

def test_convert_unknown_currency():
    fx = load_fx()
    with pytest.raises(FXNotFound, match="not in FX snapshot"):
        fx.convert(1.0, "XYZ")

def test_explicit_path_missing_raises():
    with pytest.raises(FXNotFound, match="No silent fallback"):
        load_fx("/nonexistent.yaml")

def test_extra_field_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "schema_version: '1.0'\nsnapshot_date: 2026-01-01\nsource: x\nbase: USD\n"
        "rates: {USD: 1.0}\nweird_field: yes\n", encoding="utf-8")
    with pytest.raises(Exception):
        load_fx(bad)

def test_sha256_stable():
    a = fx_sha256(); b = fx_sha256()
    assert a == b
    assert len(a) == 64
```

`tests/unit/fixtures/fx_minimal.yaml`:

```yaml
schema_version: "1.0"
snapshot_date: 2026-06-01
source: test fixture
base: USD
rates:
  USD: 1.0
  VND: 25000.0
  EUR: 0.92
```

### Notes

- Rates are **USD-to-X**: `amount_usd * rate_X = amount_X`. So `1 USD = 25400 VND`.
- Only USD base is supported; non-USD bases require cross-rate calc — unnecessary complexity for now.
- Include `USD: 1.0` in `rates` to make USD a pass-through in `convert()`.
- The 11 Asian-region currencies are mandatory; the 9 reserve currencies are nice-to-have for sanity.
- Document the source field (ECB + cross-rate) in `docs/methodology.md` — be transparent that this is a manual snapshot, not a live API.

## Acceptance Criteria

- [ ] `load_fx()` returns an `FXTable` from bundled defaults.
- [ ] All 11 Asian-region currencies (VND, IDR, MYR, THB, PHP, INR, BDT, LKR, MMK, KHR, LAK) present.
- [ ] `fx.convert(1.0, "VND")` returns 20000–30000.
- [ ] `fx.convert(1.0, "USD")` returns `1.0`.
- [ ] Unknown currency → `FXNotFound`.
- [ ] Explicit non-existent path → `FXNotFound("No silent fallback")`.
- [ ] Extra YAML field rejected.
- [ ] `fx_sha256()` stable, 64 chars.
- [ ] Wheel includes `_defaults/fx_2026-06.yaml`.
- [ ] All 7 unit tests pass.
- [ ] `mypy --strict src/fertiscope/cost/fx.py` passes.

## User Stories

### Story: Vietnamese SaaS team sees cost in VND

1. Runs `fertiscope cost --text "..." --lang vie --currencies USD,VND`.
2. Output table: GPT-4o = $0.000027 = 0.69 VND per request → 207,000 VND/month at scale.
3. Local-currency decision-making, no manual conversion.

### Story: Reviewer pins a paper figure to a dated FX

1. Paper says "Costs computed at FX snapshot 2026-06-28, SHA `def5678`."
2. Reviewer fetches `configs/fx_2026-06.yaml`, hashes it.
3. Match. Reproducibility confirmed.

### Story: User uploads custom rates

1. User overrides with `--fx-path company_fx.yaml`.
2. Loader validates schema and uses their rates instead of the bundled default.

---

Blocked by: #020
