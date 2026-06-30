"""Guards against model-ID drift across configs, run CSVs, and paper.

If a model ID appears in a benchmark config, a benchmark CSV, or the paper
without being registered in `models_<snapshot>.yaml`, we fail loudly so the
fragmentation we paid down in v0.4 doesn't sneak back in.

To register a new model: add it to `src/asia_fertility/_defaults/models_2026-06.yaml`.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest
import yaml

from asia_fertility.registry import load_registry

REPO = Path(__file__).resolve().parents[2]
REG = load_registry()


def _known_ids() -> set[str]:
    return set(REG.models.keys())


def test_benchmark_config_ids_are_registered():
    """Every model id in configs/*.yaml must be in the registry (or aliased)."""
    missing: list[tuple[str, str]] = []
    for cfg_path in (REPO / "configs").glob("*.yaml"):
        cfg = yaml.safe_load(cfg_path.read_text())
        for mid in cfg.get("models", []) or []:
            if mid not in _known_ids():
                missing.append((cfg_path.name, mid))
    assert not missing, (
        "Unregistered model IDs found in configs:\n"
        + "\n".join(f"  - {f}: {m}" for f, m in missing)
        + "\n\nAdd these to src/asia_fertility/_defaults/models_2026-06.yaml "
        "(or change the config to use a canonical ID)."
    )


@pytest.mark.parametrize(
    "csv_path",
    [
        REPO / "runs/niah/v03/results.csv",
        REPO / "runs/latency/main/results.csv",
    ],
)
def test_benchmark_csv_models_are_registered(csv_path: Path):
    """Every model column value in run CSVs must be in the registry."""
    if not csv_path.exists():
        pytest.skip(f"{csv_path} not present in this checkout")
    seen: set[str] = set()
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            m = row.get("model", "")
            # Only canonical-looking entries (CSV-quoting artifacts in long response
            # fields can break parsing; those rows have no '/' in the model column).
            if "/" in m:
                seen.add(m)
    missing = sorted(m for m in seen if m not in _known_ids())
    assert not missing, (
        f"Unregistered model IDs found in {csv_path.relative_to(REPO)}:\n"
        + "\n".join(f"  - {m}" for m in missing)
    )


def test_bundled_niah_summary_models_are_registered():
    """Every model in _defaults/niah_recall_*.json must be in the registry."""
    import json

    summary = json.loads(
        (REPO / "src/asia_fertility/_defaults/niah_recall_2026-06.json").read_text()
    )
    missing = sorted(m for m in summary["per_model_overall"] if m not in _known_ids())
    assert not missing, "Unregistered model IDs in bundled niah_recall summary:\n" + "\n".join(
        f"  - {m}" for m in missing
    )


def test_every_benchmarked_model_has_pricing():
    """Models flagged as benchmarked must have non-zero pricing."""
    bad = [
        r.id
        for r in REG.benchmarked()
        if r.input_price_per_1m <= 0.0 or r.output_price_per_1m <= 0.0
    ]
    assert not bad, (
        "These benchmarked models have zero/missing pricing in the registry: " + ", ".join(bad)
    )


def test_paper_model_ids_are_registered_or_excluded():
    """Model-id strings in paper.tex must either be in the registry, the tokenizer
    registry, or appear on the documented exclusion list (tokenizer-only IDs,
    abbreviated/legacy refs).
    """
    paper = (REPO / "paper/paper.tex").read_text()
    # Capture vendor/<name> tokens that look like model or tokenizer IDs.
    # (?:...) is non-capturing so findall returns the full match, not just the family.
    pattern = re.compile(
        r"\b(?:openai|google|meta|meta-llama|qwen|deepseek|anthropic|cohere|mistral|bigscience)"
        r"/[\w.\-]+"
    )
    raw = {m.replace("\\_", "_").rstrip(",.;:)'\"}") for m in pattern.findall(paper)}

    # Known tokenizer-only IDs (these live in the tokenizer registry, not models)
    tokenizer_only = {
        "openai/cl100k_base",
        "openai/o200k_base",
        "openai/o200k_harmony",
        "mistral/tekken",
        "qwen/qwen3",
        "deepseek/v3",
        "bigscience/bloom",
        "google/gemma-2",
        "cohere/aya-expanse",
        "meta/llama-3.1",
        "anthropic/claude",
        "google/gemini",
    }
    # Abbreviated / legacy / structural references in the paper that are not full IDs
    structural = {
        "openai/cl100k",  # short ref to cl100k_base
        "openai/o200k",  # short ref to o200k_base
        "deepseek/v3",  # tokenizer ref (also tokenizer-only above)
    }

    unknown = sorted(raw - _known_ids() - tokenizer_only - structural)
    assert not unknown, (
        "Model IDs in paper.tex are neither in the model registry nor in the "
        "approved tokenizer/structural lists:\n  " + "\n  ".join(unknown)
    )


def test_aliases_resolve_to_canonical():
    """Every alias_of pointer must target a canonical entry."""
    for rec in REG.models.values():
        if rec.alias_of:
            assert rec.alias_of in REG.models, (
                f"Alias '{rec.id}' points to non-existent '{rec.alias_of}'"
            )


def test_registry_loads_without_errors():
    assert REG.schema_version
    assert REG.snapshot_date is not None
    assert len(REG.models) >= 5
