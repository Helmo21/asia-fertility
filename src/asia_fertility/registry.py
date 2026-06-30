"""Canonical model registry — single source of truth.

Loads `_defaults/models_<snapshot>.yaml` and exposes lookup, alias resolution,
benchmark-coverage flags, and close-match suggestions. The cost subsystem's
`prices_*.yaml` is a strict subset of the fields here; future versions should
derive `prices_*.yaml` from this file via a build step.

Schema:
  models:
    <model_id>:
      family: str
      pricing: {input: float, output: float}
      context_window: int
      sizing_tokenizer: str   # tokenizer to use for portable token counting
      native_tokenizer: str   # tokenizer the provider actually uses
      routes:
        openrouter: str | null
        native: str | null
      benchmarked_in: list[str]   # benchmark names, e.g. ["niah_v03", "latency_main"]
      alias_of: str | null        # canonical id this entry duplicates
      notes: str | null
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_FILE = "models_2026-06.yaml"


@dataclass(frozen=True)
class ModelRecord:
    id: str
    family: str
    input_price_per_1m: float
    output_price_per_1m: float
    context_window: int
    sizing_tokenizer: str
    native_tokenizer: str
    openrouter_route: str | None
    native_route: str | None
    benchmarked_in: tuple[str, ...]
    alias_of: str | None
    notes: str | None


@dataclass(frozen=True)
class ModelRegistry:
    schema_version: str
    snapshot_date: date
    source_notes: str
    currency: str
    unit: str
    models: dict[str, ModelRecord]

    def get(self, model_id: str) -> ModelRecord:
        """Return the canonical record for `model_id`, resolving aliases."""
        if model_id not in self.models:
            raise KeyError(model_id)
        rec = self.models[model_id]
        if rec.alias_of and rec.alias_of in self.models:
            return self.models[rec.alias_of]
        return rec

    def has(self, model_id: str) -> bool:
        return model_id in self.models

    def suggest(self, model_id: str, n: int = 3) -> list[str]:
        """Return up to `n` close-match suggestions, ranked by similarity."""
        return difflib.get_close_matches(model_id, list(self.models.keys()), n=n, cutoff=0.4)

    def benchmarked(self, benchmark_name: str | None = None) -> list[ModelRecord]:
        """Return records benchmarked in `benchmark_name`, or any benchmark if None."""
        out = []
        for rec in self.models.values():
            if rec.alias_of:
                continue
            if benchmark_name is None:
                if rec.benchmarked_in:
                    out.append(rec)
            elif benchmark_name in rec.benchmarked_in:
                out.append(rec)
        return out

    def all(self, include_aliases: bool = False) -> list[ModelRecord]:
        return [r for r in self.models.values() if include_aliases or not r.alias_of]


def _coerce_record(model_id: str, raw: dict[str, Any]) -> ModelRecord:
    pricing = raw.get("pricing", {})
    routes = raw.get("routes", {}) or {}
    return ModelRecord(
        id=model_id,
        family=raw.get("family", ""),
        input_price_per_1m=float(pricing.get("input", 0.0)),
        output_price_per_1m=float(pricing.get("output", 0.0)),
        context_window=int(raw.get("context_window", 0)),
        sizing_tokenizer=raw.get("sizing_tokenizer", ""),
        native_tokenizer=raw.get("native_tokenizer", ""),
        openrouter_route=routes.get("openrouter"),
        native_route=routes.get("native"),
        benchmarked_in=tuple(raw.get("benchmarked_in") or []),
        alias_of=raw.get("alias_of"),
        notes=raw.get("notes"),
    )


def _bundled_default_path() -> Path:
    return Path(str(files("asia_fertility._defaults").joinpath(_DEFAULT_FILE)))


def load_registry(path: str | Path | None = None) -> ModelRegistry:
    """Load the model registry. `None` uses the bundled default."""
    actual = Path(path) if path else _bundled_default_path()
    if not actual.exists():
        raise FileNotFoundError(f"Model registry not found: {actual}")
    raw = yaml.safe_load(actual.read_text(encoding="utf-8"))
    records = {mid: _coerce_record(mid, body) for mid, body in (raw.get("models") or {}).items()}
    return ModelRegistry(
        schema_version=str(raw.get("schema_version", "")),
        snapshot_date=raw.get("snapshot_date"),
        source_notes=raw.get("source_notes", ""),
        currency=raw.get("currency", "USD"),
        unit=raw.get("unit", "per_1M_tokens"),
        models=records,
    )
