"""Pinned prices YAML + loader. No silent fallback for explicit paths."""
from __future__ import annotations

import hashlib
from datetime import date
from importlib.resources import files
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .exceptions import ModelNotInPrices, PricesNotFound


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
            raise ModelNotInPrices(
                f"Model '{model_id}' not in prices snapshot {self.snapshot_date}"
            )
        return self.models[model_id]


def _bundled_default_path() -> Path:
    return Path(str(files("asia_fertility._defaults").joinpath("prices_2026-06.yaml")))


def load_prices(path: str | Path | None = None) -> PriceTable:
    if path is None:
        actual = _bundled_default_path()
    else:
        actual = Path(path)
        if not actual.exists():
            raise PricesNotFound(
                f"Prices file not found: {actual}. No silent fallback to bundled default."
            )
    raw = yaml.safe_load(actual.read_text("utf-8"))
    return PriceTable.model_validate(raw)


def prices_sha256(path: str | Path | None = None) -> str:
    actual = _bundled_default_path() if path is None else Path(path)
    if not actual.exists():
        raise PricesNotFound(str(actual))
    return hashlib.sha256(actual.read_bytes()).hexdigest()
