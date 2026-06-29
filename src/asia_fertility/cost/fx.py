"""FX rate YAML + loader."""

from __future__ import annotations

import hashlib
from datetime import date
from importlib.resources import files
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

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
            raise FXNotFound(
                f"Currency '{target_currency}' not in FX snapshot. Available: {sorted(self.rates)}"
            )
        return amount_usd * self.rates[target_currency]


def _bundled_default_path() -> Path:
    return Path(str(files("asia_fertility._defaults").joinpath("fx_2026-06.yaml")))


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
