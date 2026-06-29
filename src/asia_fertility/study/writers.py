"""Output writers: parquet, csv, json, leaderboard, manifest."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .runner import StudyResult


def _rows_to_dicts(rows: list) -> list[dict]:
    out = []
    for r in rows:
        d = asdict(r)
        d["context_efficiency"] = {str(k): v for k, v in d["context_efficiency"].items()}
        out.append(d)
    return out


def write_csv(result: StudyResult, path: Path) -> None:
    rows = _rows_to_dicts(result.rows)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = [k for k in rows[0] if k != "context_efficiency"]
    win_keys = sorted(rows[0]["context_efficiency"].keys(), key=lambda x: int(x))
    fieldnames += [f"ctx_eff_{w}" for w in win_keys]

    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            row_out = {k: v for k, v in r.items() if k != "context_efficiency"}
            for k in win_keys:
                row_out[f"ctx_eff_{k}"] = r["context_efficiency"].get(k, "")
            w.writerow(row_out)


def write_json(result: StudyResult, path: Path) -> None:
    rows = _rows_to_dicts(result.rows)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def write_parquet(result: StudyResult, path: Path) -> None:
    try:
        import pandas as pd  # type: ignore
    except ImportError:
        import logging

        logging.getLogger(__name__).warning(
            "pyarrow/pandas not installed; skipping parquet. Install with pip install asia-fertility[viz]"
        )
        return
    rows = _rows_to_dicts(result.rows)
    if rows:
        win_keys = sorted(rows[0]["context_efficiency"].keys(), key=lambda x: int(x))
        for r in rows:
            for k in win_keys:
                r[f"ctx_eff_{k}"] = r["context_efficiency"].get(k)
            r.pop("context_efficiency", None)
    df = pd.DataFrame(rows)
    df.to_parquet(path, engine="pyarrow", index=False)


def write_manifest(manifest: dict, path: Path) -> None:
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def write_leaderboard_stub(result: StudyResult, path: Path) -> None:
    rows = _rows_to_dicts(result.rows)
    out = {"schema_version": "0.1", "languages": rows}
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
