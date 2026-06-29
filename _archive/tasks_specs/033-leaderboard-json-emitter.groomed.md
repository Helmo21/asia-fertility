# Leaderboard JSON emitter + `leaderboard` CLI

Status: pending
Tags: `leaderboard`, `json-schema`, `web-integration`, `cli`
Depends on: #025
Blocks: None

## Scope

Take a `StudyResult` and emit a `leaderboard.json` consumable by the Next.js web app. Schema v1.0 includes per-language best/worst tokenizer pointers, CI bounds, and BPT. Provides the `fertiscope leaderboard --run X --out Y` CLI.

### Files to create

- `src/fertiscope/report/leaderboard.py`
- `tests/unit/test_leaderboard.py`
- `docs/leaderboard_schema.md` — the consumer documentation.

### Files to modify

- `src/fertiscope/cli.py` — replace `leaderboard` stub body.

### Interface and contract

`src/fertiscope/report/leaderboard.py`:

```python
from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict


class LeaderboardTokenizerRow(TypedDict):
    id: str
    family: str
    backend: str
    fertility: dict           # {"point": ..., "low": ..., "high": ...}
    premium: dict | None
    cost_ratio: dict | None
    cpt: float
    bpt: float


class LeaderboardLanguage(TypedDict):
    iso: str
    name: str
    script: str
    family: str
    tokenizers: list[LeaderboardTokenizerRow]
    best_tokenizer: dict       # {"id": "...", "premium": ...}
    worst_tokenizer: dict


class LeaderboardSchema(TypedDict):
    schema_version: str
    generated_at: str
    package_version: str
    manifest_sha: str
    baseline_tokenizer: str
    languages: list[LeaderboardLanguage]


def emit_leaderboard(
    run_dir: str | Path,
    *,
    baseline_tokenizer: str = "openai/o200k_base",
) -> dict:
    """Read `run_dir/results.csv` + `manifest.json`, emit leaderboard dict."""
    from .._version import __version__ if False else None     # placeholder
    from fertiscope import __version__ as fertiscope_version
    from ._io import load_run
    from fertiscope.languages import get_language

    df, manifest = load_run(run_dir)
    df = df[df["skip_reason"].isna()]

    languages: list[LeaderboardLanguage] = []
    for iso in df["iso"].unique():
        sub = df[df["iso"] == iso].copy()
        if sub.empty:
            continue
        try:
            lang_meta = get_language(iso)
        except KeyError:
            continue

        tokenizers: list[LeaderboardTokenizerRow] = []
        for _, row in sub.iterrows():
            tokenizers.append({
                "id": row["tokenizer"],
                "family": row["tokenizer_family"],
                "backend": row["tokenizer_backend"],
                "fertility": {"point": float(row["fertility"]),
                              "low": float(row["fertility_ci_low"]),
                              "high": float(row["fertility_ci_high"])},
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

        # Find best (lowest premium) and worst (highest premium) for non-baseline
        # Baseline languages have no premium, so use fertility ranking
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
        "package_version": fertiscope_version,
        "manifest_sha": manifest.get("config_sha256", "")[:12],
        "baseline_tokenizer": baseline_tokenizer,
        "languages": sorted(languages, key=lambda l: l["iso"]),
    }


def _is_nan(x) -> bool:
    try:
        import math
        return math.isnan(float(x))
    except (TypeError, ValueError):
        return True


def write_leaderboard(run_dir: str | Path, out_path: str | Path,
                      baseline_tokenizer: str = "openai/o200k_base") -> Path:
    out = Path(out_path)
    lb = emit_leaderboard(run_dir, baseline_tokenizer=baseline_tokenizer)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(lb, indent=2, ensure_ascii=False), encoding="utf-8")
    return out
```

CLI:

```python
@app.command()
def leaderboard(run_dir: str = typer.Option(..., "--run"),
                out: str = typer.Option("leaderboard.json", "--out"),
                baseline: str = typer.Option("openai/o200k_base", "--baseline")) -> None:
    """Emit leaderboard JSON from a study run."""
    from fertiscope.report.leaderboard import write_leaderboard
    path = write_leaderboard(run_dir, out, baseline_tokenizer=baseline)
    typer.echo(f"✓ leaderboard written: {path}")
```

`docs/leaderboard_schema.md`:

```markdown
# leaderboard.json schema v1.0

Consumed by the Next.js web app at fertiscope.vercel.app.

## Top-level

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-06-28T12:00:00+00:00",
  "package_version": "0.3.0",
  "manifest_sha": "abc1234567",
  "baseline_tokenizer": "openai/o200k_base",
  "languages": [...]
}
```

## Per-language entry

```json
{
  "iso": "tam",
  "name": "Tamil",
  "script": "Taml",
  "family": "Dravidian",
  "tokenizers": [
    {
      "id": "openai/o200k_base",
      "family": "openai",
      "backend": "tiktoken",
      "fertility": {"point": 2.0, "low": 1.9, "high": 2.1},
      "premium":   {"point": 2.0, "low": 1.9, "high": 2.1},
      "cost_ratio":{"point": 2.0, "low": 1.9, "high": 2.1},
      "cpt": 5.62,
      "bpt": 2.34
    }
  ],
  "best_tokenizer":  {"id": "openai/o200k_base", "fertility": 2.0},
  "worst_tokenizer": {"id": "openai/cl100k_base", "fertility": 11.25}
}
```

## Stability guarantees

- `schema_version` follows semver. Breaking changes bump major.
- `manifest_sha` is the first 12 hex chars of the study's `config_sha256`.
- Languages without ANY successful tokenizer cell are OMITTED (not included with empty list).
- `premium` and `cost_ratio` are `null` for baseline-language rows.
```

`tests/unit/test_leaderboard.py`:

```python
import json, pytest
from pathlib import Path
from fertiscope.report.leaderboard import emit_leaderboard, write_leaderboard

def _fixture(tmp_path: Path) -> Path:
    """Build a small run fixture."""
    import pandas as pd
    rows = []
    for iso, script, premium, cost_ratio in [
        ("eng","Latn",1.0,1.0),
        ("vie","Latn",2.25,2.25),
        ("tam","Taml",7.19,7.19),
    ]:
        for tok in ["openai/cl100k_base","openai/o200k_base"]:
            p = premium if tok=="openai/cl100k_base" else premium*0.3
            cr = cost_ratio if tok=="openai/cl100k_base" else cost_ratio*0.3
            rows.append(dict(
                corpus="flores", lang=iso, iso=iso, script=script, family="x",
                tokenizer=tok, tokenizer_family="openai", tokenizer_backend="tiktoken",
                n_sentences=50, tokens_sum=100, words_sum=10, chars_sum=200, bytes_sum=300,
                fertility=p*1.3, fertility_ci_low=p*1.2, fertility_ci_high=p*1.4,
                premium=p if iso!="eng" else float("nan"),
                premium_ci_low=p*0.9 if iso!="eng" else float("nan"),
                premium_ci_high=p*1.1 if iso!="eng" else float("nan"),
                cost_ratio=cr if iso!="eng" else float("nan"),
                cost_ratio_ci_low=cr*0.9 if iso!="eng" else float("nan"),
                cost_ratio_ci_high=cr*1.1 if iso!="eng" else float("nan"),
                cpt=4.5, cpt_ci_low=4.4, cpt_ci_high=4.6,
                bpt=2.3, bpt_ci_low=2.2, bpt_ci_high=2.4,
                segmenter_used="icu", tokenizer_unavailable=False, skip_reason=None,
            ))
    pd.DataFrame(rows).to_csv(tmp_path/"results.csv", index=False)
    (tmp_path/"manifest.json").write_text(json.dumps({"config_sha256":"a"*64}), encoding="utf-8")
    return tmp_path


def test_schema_version(tmp_path):
    run = _fixture(tmp_path)
    lb = emit_leaderboard(run)
    assert lb["schema_version"] == "1.0"
    assert "generated_at" in lb
    assert "package_version" in lb

def test_languages_sorted(tmp_path):
    run = _fixture(tmp_path)
    lb = emit_leaderboard(run)
    isos = [l["iso"] for l in lb["languages"]]
    assert isos == sorted(isos)

def test_baseline_premium_null(tmp_path):
    run = _fixture(tmp_path)
    lb = emit_leaderboard(run)
    eng = next(l for l in lb["languages"] if l["iso"] == "eng")
    for tok in eng["tokenizers"]:
        assert tok["premium"] is None
        assert tok["cost_ratio"] is None

def test_best_worst_pointers(tmp_path):
    run = _fixture(tmp_path)
    lb = emit_leaderboard(run)
    tam = next(l for l in lb["languages"] if l["iso"] == "tam")
    assert tam["best_tokenizer"]["id"] == "openai/o200k_base"
    assert tam["worst_tokenizer"]["id"] == "openai/cl100k_base"

def test_write_leaderboard(tmp_path):
    run = _fixture(tmp_path)
    out = tmp_path / "leaderboard.json"
    write_leaderboard(run, out)
    assert out.exists()
    data = json.loads(out.read_text("utf-8"))
    assert data["schema_version"] == "1.0"

def test_bpt_included(tmp_path):
    run = _fixture(tmp_path)
    lb = emit_leaderboard(run)
    for lang in lb["languages"]:
        for tok in lang["tokenizers"]:
            assert "bpt" in tok and tok["bpt"] > 0
```

### Notes

- The schema explicitly versions itself so the Next.js consumer can bail if the version is unknown.
- `manifest_sha` is truncated to 12 hex chars for UX (fits in a tooltip).
- Baseline rows have `premium=null, cost_ratio=null` — the consumer must handle this. Documented.
- For the Next.js wiring: copy `leaderboard.json` into `fertiscope-web/data/leaderboard.json` and update the build to read from it. (That wiring is a small task left to web maintenance, not specced here.)

## Acceptance Criteria

- [ ] `emit_leaderboard(run)` returns a dict with all 5 top-level fields.
- [ ] `schema_version == "1.0"`.
- [ ] Languages sorted by ISO ascending.
- [ ] Baseline language's tokenizer rows have `premium == None` and `cost_ratio == None`.
- [ ] `best_tokenizer.id` is the tokenizer with the lowest fertility for that language.
- [ ] `worst_tokenizer.id` is the highest.
- [ ] Every tokenizer row includes `bpt`.
- [ ] `write_leaderboard(run, out)` writes valid JSON.
- [ ] CLI: `fertiscope leaderboard --run X --out Y` works.
- [ ] All 6 unit tests pass.
- [ ] `mypy --strict src/fertiscope/report/leaderboard.py` passes.
- [ ] Schema documented in `docs/leaderboard_schema.md`.

## User Stories

### Story: Next.js app consumes leaderboard

1. Build pipeline downloads `leaderboard.json` from HF dataset (after #036).
2. Renders the leaderboard view with BPT column and "best tokenizer" badge per row.
3. Tooltip shows manifest SHA: "data from manifest abc1234".

### Story: Author publishes leaderboard alongside PR

1. After `fertiscope run`, runs `fertiscope leaderboard --run runs/main --out leaderboard.json`.
2. Attaches to GitHub release as an asset.
3. Web app pulls it via raw GitHub URL until HF dataset publish.

### Story: Reviewer audits "best tokenizer" claims

1. Opens `leaderboard.json`.
2. Filters Tamil row.
3. Sees `best_tokenizer = openai/o200k_base` with fertility ~2.0.
4. Cross-checks with `tokenizers[].fertility.point` values — matches.

---

Blocked by: #025
