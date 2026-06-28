"""Load run results + manifest."""
from __future__ import annotations

import json
from pathlib import Path


def load_run(run_dir: str | Path):
    """Returns (df, manifest)."""
    import pandas as pd

    run = Path(run_dir)
    parquet = run / "results.parquet"
    csv = run / "results.csv"
    if parquet.exists():
        df = pd.read_parquet(parquet)
    elif csv.exists():
        df = pd.read_csv(csv)
    else:
        raise FileNotFoundError(f"No results file in {run}")

    manifest_path = run / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text("utf-8"))
    else:
        manifest = {}
    return df, manifest
