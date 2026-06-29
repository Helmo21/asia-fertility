"""Tests for asia_fertility.latency.runner."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from asia_fertility.latency.runner import (
    LatencyConfig,
    LatencyRow,
    _load_completed,
    estimate_cost_usd,
)


def test_config_total_calls():
    cfg = LatencyConfig(
        name="t",
        languages=["eng", "tam"],
        models=["openai/gpt-4o-mini"],
        n_warmup=3,
        n_trials=10,
    )
    assert cfg.total_calls() == 2 * 1 * (3 + 10)


def test_cost_estimate_positive():
    cfg = LatencyConfig(
        name="t",
        languages=["eng"],
        models=["openai/gpt-4o-mini"],
        n_warmup=3,
        n_trials=10,
    )
    cost = estimate_cost_usd(cfg)
    assert 0 < cost < 1.0


def test_resolve_output_dir():
    cfg = LatencyConfig(name="abc", languages=["eng"], models=["m"])
    assert cfg.resolve_output_dir() == Path("runs/latency/abc")


def test_extra_field_rejected():
    with pytest.raises(ValueError):
        LatencyConfig.model_validate(
            {"name": "t", "languages": ["eng"], "models": ["m"], "weird": 1}
        )


def test_load_completed_empty(tmp_path):
    assert _load_completed(tmp_path / "noexist.csv") == set()


def test_load_completed_resumes(tmp_path):
    csv_path = tmp_path / "r.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(LatencyRow.__dataclass_fields__))
        w.writeheader()
        w.writerow(
            {
                "model": "m1",
                "iso": "eng",
                "script": "Latn",
                "trial": -1,
                "is_warmup": True,
                "prompt_chars": 100,
                "ttft_ms": 500.0,
                "total_ms": 1000.0,
                "output_chars": 50,
                "error": "",
            }
        )
        w.writerow(
            {
                "model": "m1",
                "iso": "eng",
                "script": "Latn",
                "trial": 0,
                "is_warmup": False,
                "prompt_chars": 100,
                "ttft_ms": 500.0,
                "total_ms": 1000.0,
                "output_chars": 50,
                "error": "",
            }
        )
    done = _load_completed(csv_path)
    assert ("m1", "eng", -1) in done
    assert ("m1", "eng", 0) in done
    assert len(done) == 2


def test_latency_row_frozen():
    import dataclasses as _dc

    row = LatencyRow(
        model="m",
        iso="eng",
        script="Latn",
        trial=0,
        is_warmup=False,
        prompt_chars=10,
        ttft_ms=100.0,
        total_ms=200.0,
        output_chars=5,
    )
    with pytest.raises(_dc.FrozenInstanceError):
        row.model = "other"  # type: ignore[misc]
