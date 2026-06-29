# Manifest builder + output writers (parquet/csv/json/leaderboard)

Status: pending
Tags: `study`, `manifest`, `reproducibility`, `parquet`, `output`
Depends on: #020, #021, #023, #024
Blocks: #026, #033

## Scope

Turn an in-memory `StudyResult` into the five canonical artifacts on disk:

1. `results.parquet` — columnar typed table.
2. `results.csv` — same content, human-readable.
3. `results.json` — for ad-hoc consumption.
4. `leaderboard.json` — schema consumed by the Next.js app (#033 finalizes schema).
5. `manifest.json` — SHA256s of every input + tokenizer versions + run metadata.

### Files to create

- `src/fertiscope/study/manifest.py`
- `src/fertiscope/study/writers.py`
- `tests/unit/test_manifest.py`
- `tests/unit/test_writers.py`

### Files to modify

- `src/fertiscope/study/runner.py` — add `StudyResult.write_all(output_dir: Path) -> Path`.

### Interface and contract

`src/fertiscope/study/manifest.py`:

```python
from __future__ import annotations
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from fertiscope import __version__
from fertiscope.cost.prices import prices_sha256
from fertiscope.cost.fx     import fx_sha256

if TYPE_CHECKING:
    from fertiscope.config import StudyConfig


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tokenizer_versions(tokenizer_ids: list[str]) -> dict[str, str]:
    """Best-effort version capture per tokenizer. Records library versions, not vocab hashes."""
    out: dict[str, str] = {}
    for tid in tokenizer_ids:
        if tid.startswith("openai/"):
            try:
                import tiktoken            # type: ignore
                out[tid] = f"tiktoken=={tiktoken.__version__}"
            except ImportError:
                out[tid] = "tiktoken=missing"
        elif "/" in tid and not tid.startswith(("anthropic/", "google/")):
            try:
                import transformers         # type: ignore
                out[tid] = f"transformers=={transformers.__version__}"
            except ImportError:
                out[tid] = "transformers=missing"
        elif tid.startswith("anthropic/"):
            try:
                import anthropic           # type: ignore
                out[tid] = f"anthropic=={anthropic.__version__}"
            except ImportError:
                out[tid] = "anthropic=missing"
    return out


def build_manifest(cfg: "StudyConfig", *, n_rows: int) -> dict:
    cfg_json = cfg.model_dump_json()
    return {
        "schema_version": "1.0",
        "package_version": __version__,
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "config_sha256": _sha256_text(cfg_json),
        "config": json.loads(cfg_json),
        "prices_sha256": prices_sha256(cfg.prices_snapshot if Path(cfg.prices_snapshot).exists() else None),
        "fx_sha256":     fx_sha256(cfg.fx_snapshot         if Path(cfg.fx_snapshot).exists()     else None),
        "tokenizer_versions": _tokenizer_versions(cfg.tokenizers),
        "n_rows": n_rows,
        "host": {
            "os": platform.system(),
            "os_release": platform.release(),
            "python": sys.version.split()[0],
            "machine": platform.machine(),
        },
    }
```

`src/fertiscope/study/writers.py`:

```python
from __future__ import annotations
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
        # context_efficiency is dict[int, float] — JSON requires str keys
        d["context_efficiency"] = {str(k): v for k, v in d["context_efficiency"].items()}
        out.append(d)
    return out


def write_csv(result: "StudyResult", path: Path) -> None:
    import csv
    rows = _rows_to_dicts(result.rows)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    # Flatten context_efficiency into named columns
    fieldnames = [k for k in rows[0] if k != "context_efficiency"]
    win_keys = sorted(rows[0]["context_efficiency"].keys(), key=int)
    fieldnames += [f"ctx_eff_{w}" for w in win_keys]

    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            row_out = {k: v for k, v in r.items() if k != "context_efficiency"}
            for k in win_keys:
                row_out[f"ctx_eff_{k}"] = r["context_efficiency"].get(k, "")
            w.writerow(row_out)


def write_json(result: "StudyResult", path: Path) -> None:
    rows = _rows_to_dicts(result.rows)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def write_parquet(result: "StudyResult", path: Path) -> None:
    try:
        import pandas as pd, pyarrow as pa, pyarrow.parquet as pq     # type: ignore
    except ImportError:
        # Soft-degrade: parquet writer requires [viz] extra; log + skip.
        import logging
        logging.getLogger(__name__).warning("pyarrow not installed; skipping parquet write. Install with: pip install fertiscope[viz]")
        return
    rows = _rows_to_dicts(result.rows)
    # Move context_efficiency to flat columns for parquet typing
    if rows:
        win_keys = sorted(rows[0]["context_efficiency"].keys(), key=int)
        for r in rows:
            for k in win_keys:
                r[f"ctx_eff_{k}"] = r["context_efficiency"].get(k)
            r.pop("context_efficiency", None)
    df = pd.DataFrame(rows)
    df.to_parquet(path, engine="pyarrow", index=False)


def write_manifest(manifest: dict, path: Path) -> None:
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def write_leaderboard_stub(result: "StudyResult", path: Path) -> None:
    """Minimal leaderboard schema. #033 enriches with CIs and best/worst pointers."""
    rows = _rows_to_dicts(result.rows)
    out = {
        "schema_version": "0.1",            # bumped to 1.0 in #033
        "languages": rows,
    }
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
```

Update `runner.py`:

```python
@dataclass
class StudyResult:
    config: StudyConfig
    rows: list[Row]
    manifest: dict | None = None

    def write_all(self, output_dir: Path | None = None) -> Path:
        from .writers import write_csv, write_json, write_parquet, write_manifest, write_leaderboard_stub
        from .manifest import build_manifest

        out = Path(output_dir) if output_dir else self.config.resolve_output_dir()
        out.mkdir(parents=True, exist_ok=True)

        if self.manifest is None:
            self.manifest = build_manifest(self.config, n_rows=len(self.rows))

        write_csv(self,          out / "results.csv")
        write_json(self,         out / "results.json")
        write_parquet(self,      out / "results.parquet")
        write_leaderboard_stub(self, out / "leaderboard.json")
        write_manifest(self.manifest, out / "manifest.json")
        return out
```

`tests/unit/test_manifest.py`:

```python
import json
from fertiscope.config import StudyConfig
from fertiscope.study.manifest import build_manifest

def test_manifest_has_required_fields():
    cfg = StudyConfig(
        name="x", languages=["eng"], tokenizers=["openai/o200k_base"],
        corpora=["custom"], baseline_language="eng",
    )
    m = build_manifest(cfg, n_rows=1)
    for key in ["schema_version","package_version","run_started_at","config_sha256",
                "config","prices_sha256","fx_sha256","tokenizer_versions","n_rows","host"]:
        assert key in m
    assert len(m["config_sha256"]) == 64
    assert len(m["prices_sha256"]) == 64
    assert len(m["fx_sha256"])     == 64

def test_config_sha_stable():
    cfg = StudyConfig(name="x", languages=["eng"], tokenizers=["t"],
                      corpora=["custom"], baseline_language="eng")
    m1 = build_manifest(cfg, n_rows=0)
    m2 = build_manifest(cfg, n_rows=0)
    assert m1["config_sha256"] == m2["config_sha256"]

def test_run_started_at_changes():
    cfg = StudyConfig(name="x", languages=["eng"], tokenizers=["t"],
                      corpora=["custom"], baseline_language="eng")
    m1 = build_manifest(cfg, n_rows=0)
    import time; time.sleep(0.01)
    m2 = build_manifest(cfg, n_rows=0)
    assert m1["run_started_at"] != m2["run_started_at"]
```

`tests/unit/test_writers.py`:

```python
import json
from pathlib import Path
from fertiscope.config import StudyConfig
from fertiscope.study.runner import run_study

def test_write_all_produces_5_files(tmp_path):
    cfg = StudyConfig(
        name="reproduce", languages=["eng","vie"], tokenizers=["openai/o200k_base"],
        corpora=["custom"], baseline_language="eng",
        n_sentences=3, n_bootstrap=50, rng_seed=42,
    )
    result = run_study(cfg)
    out = result.write_all(tmp_path)
    for fn in ["results.csv","results.json","leaderboard.json","manifest.json"]:
        assert (out / fn).exists()
    # parquet may skip if pyarrow missing; assert csv + json baseline.
    rows = json.loads((out / "results.json").read_text("utf-8"))
    assert len(rows) == 2

def test_results_csv_has_ci_columns(tmp_path):
    cfg = StudyConfig(
        name="reproduce", languages=["eng"], tokenizers=["openai/o200k_base"],
        corpora=["custom"], baseline_language="eng",
        n_sentences=3, n_bootstrap=50, rng_seed=42,
    )
    out = run_study(cfg).write_all(tmp_path)
    text = (out / "results.csv").read_text("utf-8")
    header = text.splitlines()[0]
    for col in ["fertility","fertility_ci_low","fertility_ci_high","cpt","bpt","ctx_eff_4096"]:
        assert col in header
```

### Notes

- Parquet writes use `pyarrow` engine; gracefully degrade with a warning if not installed. The `[viz]` extra is the documented install.
- `manifest.json` ALSO contains the full `config` body, so reproducers don't need to re-fetch the YAML.
- `prices_sha256` and `fx_sha256` re-hash whatever the loader uses — even the bundled `_defaults/` files.
- The `leaderboard.json` schema here is a stub (v0.1). #033 bumps it to v1.0 with per-language/per-tokenizer nested structure.
- Sort keys in `manifest.json` for byte-stable output → reviewers can diff manifests across runs.

## Acceptance Criteria

- [ ] `result.write_all(tmp_path)` produces `results.csv`, `results.json`, `leaderboard.json`, `manifest.json` (and `results.parquet` if pyarrow installed).
- [ ] `manifest.json` contains `config_sha256` (64-char hex), `prices_sha256`, `fx_sha256`, `tokenizer_versions`, `host`, `n_rows`.
- [ ] Re-running same config produces identical `config_sha256` but different `run_started_at`.
- [ ] `results.csv` header includes `fertility_ci_low`, `fertility_ci_high`, `cpt`, `bpt`, `ctx_eff_4096`, etc.
- [ ] `results.json` is valid JSON parsable by `json.loads`.
- [ ] All 5 unit tests pass.
- [ ] Without `[viz]` extra: parquet write logs a warning and skips, but other outputs still write.
- [ ] `mypy --strict src/fertiscope/study/` passes.

## User Stories

### Story: Reproducer verifies a result

1. Reviewer downloads `runs/main/manifest.json` from the v0.3 release.
2. Computes `prices_sha256("configs/prices_2026-06.yaml")` locally.
3. Hash matches manifest → reproducibility confirmed.

### Story: Data scientist loads results

1. `pd.read_parquet("runs/main/results.parquet")` returns a typed DataFrame.
2. Filter rows, join with external data, plot.
3. No re-running needed.

### Story: Leaderboard stub feeds the web app

1. `runs/main/leaderboard.json` exists (stub schema).
2. Next.js app reads it via #033's finalized schema after #033 lands.
3. Cells render.

---

Blocked by: #020, #021, #023, #024
