"""Leaderboard JSON emitter."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

from asia_fertility import __version__
from asia_fertility.languages import get_language

from ._io import load_run


def _is_nan(x) -> bool:
    try:
        return math.isnan(float(x))
    except (TypeError, ValueError):
        return True


def emit_leaderboard(
    run_dir: str | Path, *, baseline_tokenizer: str = "openai/o200k_base"
) -> dict:
    df, manifest = load_run(run_dir)
    df = df[(df["skip_reason"].isna()) | (df["skip_reason"] == "")]

    languages: list[dict] = []
    for iso in df["iso"].unique():
        sub = df[df["iso"] == iso].copy()
        if sub.empty:
            continue
        try:
            lang_meta = get_language(iso)
        except KeyError:
            continue

        tokenizers: list[dict] = []
        for _, row in sub.iterrows():
            tokenizers.append({
                "id": row["tokenizer"],
                "family": row["tokenizer_family"],
                "backend": row["tokenizer_backend"],
                "fertility": {
                    "point": float(row["fertility"]),
                    "low": float(row["fertility_ci_low"]),
                    "high": float(row["fertility_ci_high"]),
                },
                "premium": None if _is_nan(row["premium"]) else {
                    "point": float(row["premium"]),
                    "low": float(row["premium_ci_low"]),
                    "high": float(row["premium_ci_high"]),
                },
                "cost_ratio": None if _is_nan(row["cost_ratio"]) else {
                    "point": float(row["cost_ratio"]),
                    "low": float(row["cost_ratio_ci_low"]),
                    "high": float(row["cost_ratio_ci_high"]),
                },
                "cpt": float(row["cpt"]),
                "bpt": float(row["bpt"]),
            })

        non_skip = [t for t in tokenizers if t["fertility"]["point"] > 0]
        if not non_skip:
            continue
        best = min(non_skip, key=lambda t: t["fertility"]["point"])
        worst = max(non_skip, key=lambda t: t["fertility"]["point"])

        languages.append({
            "iso": iso,
            "name": lang_meta.name,
            "script": lang_meta.script,
            "family": lang_meta.family,
            "tokenizers": tokenizers,
            "best_tokenizer": {"id": best["id"], "fertility": best["fertility"]["point"]},
            "worst_tokenizer": {"id": worst["id"], "fertility": worst["fertility"]["point"]},
        })

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package_version": __version__,
        "manifest_sha": (manifest.get("config_sha256") or "")[:12],
        "baseline_tokenizer": baseline_tokenizer,
        "languages": sorted(languages, key=lambda l: l["iso"]),
    }


def write_leaderboard(
    run_dir: str | Path,
    out_path: str | Path,
    baseline_tokenizer: str = "openai/o200k_base",
) -> Path:
    out = Path(out_path)
    lb = emit_leaderboard(run_dir, baseline_tokenizer=baseline_tokenizer)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(lb, indent=2, ensure_ascii=False), encoding="utf-8")
    return out
