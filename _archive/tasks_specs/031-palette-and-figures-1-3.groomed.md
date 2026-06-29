# Palette + Figures 1–3 (heatmap, premium-by-script, cost)

Status: pending
Tags: `figures`, `matplotlib`, `palette`, `okabe-ito`, `report`
Depends on: #025
Blocks: #033

## Scope

The first three of six paper figures, plus the shared color palette. Each figure reads `runs/<name>/results.parquet` (or .csv) and writes a deterministic PNG (300 dpi) + SVG to `runs/<name>/figures/`.

### Files to create

- `src/fertiscope/report/__init__.py`
- `src/fertiscope/report/palette.py`
- `src/fertiscope/report/figures.py` (Figures 1, 2, 3 here; 4–6 in #032)
- `src/fertiscope/report/_io.py` — `load_run(run_dir)` returns DataFrame.
- `tests/unit/test_figures_1_3.py`

### Files to modify

- `src/fertiscope/cli.py` — partial `figures` command implementation.

### Interface and contract

`src/fertiscope/report/palette.py`:

```python
"""Okabe-Ito 8-color palette — deuteranopia/protanopia safe.

Reference: Okabe & Ito (2008). Color Universal Design.
"""

# Categorical colors (use for tokenizer families, scripts)
OKABE_ITO = {
    "black":     "#000000",
    "orange":    "#E69F00",
    "skyblue":   "#56B4E9",
    "green":     "#009E73",
    "yellow":    "#F0E442",
    "blue":      "#0072B2",
    "vermillion":"#D55E00",
    "purple":    "#CC79A7",
}

# Family color assignments — stable across figures
FAMILY_COLORS = {
    "openai":     "#0072B2",   # blue
    "meta":       "#E69F00",   # orange
    "google":     "#009E73",   # green
    "mistral":    "#D55E00",   # vermillion
    "qwen":       "#CC79A7",   # purple
    "deepseek":   "#56B4E9",   # skyblue
    "bigscience": "#F0E442",   # yellow
    "cohere":     "#000000",   # black
    "anthropic":  "#888888",
}

# Script color assignments
SCRIPT_COLORS = {
    "Latn": "#0072B2", "Deva": "#E69F00", "Beng": "#009E73",
    "Taml": "#D55E00", "Telu": "#CC79A7", "Knda": "#56B4E9",
    "Mlym": "#F0E442", "Sinh": "#888888", "Mymr": "#000000",
    "Khmr": "#7F4F24", "Laoo": "#A0522D", "Thai": "#5F9EA0",
}

# Sequential palette (use for heatmaps)
SEQUENTIAL = "viridis"   # matplotlib name
```

`src/fertiscope/report/_io.py`:

```python
from __future__ import annotations
from pathlib import Path
import json


def load_run(run_dir: str | Path):
    """Load results table + manifest from a run directory.

    Returns:
        (df, manifest) where df is a pandas DataFrame and manifest is a dict.
    """
    import pandas as pd                  # type: ignore
    run = Path(run_dir)
    parquet = run / "results.parquet"
    csv     = run / "results.csv"
    if parquet.exists():
        df = pd.read_parquet(parquet)
    elif csv.exists():
        df = pd.read_csv(csv)
    else:
        raise FileNotFoundError(f"No results file in {run}")
    manifest = json.loads((run / "manifest.json").read_text("utf-8"))
    return df, manifest
```

`src/fertiscope/report/figures.py` (figs 1–3):

```python
from __future__ import annotations
from pathlib import Path
from .palette import FAMILY_COLORS, SCRIPT_COLORS, SEQUENTIAL
from .. import __version__


def _setup_mpl():
    """Configure matplotlib for deterministic output."""
    import matplotlib                  # type: ignore
    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "fertiscope"
    matplotlib.rcParams["font.family"] = "DejaVu Sans"
    matplotlib.rcParams["figure.dpi"] = 100


def _footer(ax, manifest: dict) -> None:
    sha = manifest.get("config_sha256", "")[:7]
    ax.figure.text(0.99, 0.01,
                   f"fertiscope v{__version__} · manifest {sha}",
                   ha="right", va="bottom", fontsize=6, alpha=0.5)


def fig1_heatmap(run_dir: str | Path, out_dir: Path) -> tuple[Path, Path]:
    """Premium heatmap: rows = languages, cols = tokenizers, cells = premium."""
    _setup_mpl()
    import matplotlib.pyplot as plt
    import numpy as np
    from ._io import load_run
    df, manifest = load_run(run_dir)
    df = df[df["skip_reason"].isna()]
    pivot = df.pivot_table(index="iso", columns="tokenizer", values="premium", aggfunc="mean")

    fig, ax = plt.subplots(figsize=(12, 8))
    im = ax.imshow(pivot.values, aspect="auto", cmap=SEQUENTIAL, vmin=1.0, vmax=12.0)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    plt.colorbar(im, ax=ax, label="Premium (× English)")
    ax.set_title("Tokenizer premium by language × tokenizer", fontsize=14)

    # Annotate the worst N entries
    flat = [(i, j, pivot.values[i, j]) for i in range(pivot.shape[0]) for j in range(pivot.shape[1]) if not np.isnan(pivot.values[i,j])]
    flat.sort(key=lambda x: -x[2])
    for i, j, v in flat[:5]:
        ax.text(j, i, f"{v:.1f}×", ha="center", va="center", color="white", fontsize=8, fontweight="bold")

    _footer(ax, manifest)
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / "fig1_heatmap.png"
    svg = out_dir / "fig1_heatmap.svg"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(svg, format="svg", bbox_inches="tight")
    plt.close(fig)
    return png, svg


def fig2_premium_by_script(run_dir: str | Path, out_dir: Path) -> tuple[Path, Path]:
    """Bar chart grouped by script — shows the script-coverage effect."""
    _setup_mpl()
    import matplotlib.pyplot as plt
    from ._io import load_run
    df, manifest = load_run(run_dir)
    df = df[df["skip_reason"].isna()]
    df = df[df["tokenizer"] == "openai/cl100k_base"]   # showcase the worst tokenizer

    df_sorted = df.sort_values("premium", ascending=False)
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = [SCRIPT_COLORS.get(s, "#888") for s in df_sorted["script"]]
    ax.bar(df_sorted["iso"], df_sorted["premium"], color=colors)
    ax.errorbar(df_sorted["iso"], df_sorted["premium"],
                yerr=[df_sorted["premium"] - df_sorted["premium_ci_low"],
                      df_sorted["premium_ci_high"] - df_sorted["premium"]],
                fmt="none", color="black", alpha=0.5, capsize=2)
    ax.set_ylabel("Premium (× English)")
    ax.set_xlabel("Language")
    ax.set_title("Premium on cl100k_base, colored by script", fontsize=14)
    ax.tick_params(axis="x", rotation=45)

    _footer(ax, manifest)
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / "fig2_premium_by_script.png"
    svg = out_dir / "fig2_premium_by_script.svg"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(svg, format="svg", bbox_inches="tight")
    plt.close(fig)
    return png, svg


def fig3_cost(run_dir: str | Path, out_dir: Path) -> tuple[Path, Path]:
    """Monthly cost gap vs English at a representative workload (100k requests/month, 200 tokens/req)."""
    _setup_mpl()
    import matplotlib.pyplot as plt
    from ._io import load_run
    df, manifest = load_run(run_dir)
    df = df[df["skip_reason"].isna()]
    df = df[df["tokenizer"] == "openai/cl100k_base"]

    monthly_requests = 100_000
    avg_tokens_eng = 27 * monthly_requests   # paper figure
    rate_per_1m = 10.0    # GPT-4 Turbo input

    df_sorted = df.sort_values("cost_ratio", ascending=False)
    monthly_cost_usd = (df_sorted["cost_ratio"] * avg_tokens_eng) * rate_per_1m / 1_000_000

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = [SCRIPT_COLORS.get(s, "#888") for s in df_sorted["script"]]
    ax.bar(df_sorted["iso"], monthly_cost_usd, color=colors)
    ax.axhline(y=monthly_cost_usd[df_sorted["iso"] == "eng"].values[0] if "eng" in df_sorted["iso"].values else 0,
               color="black", linestyle="--", label="English baseline")
    ax.set_ylabel("Monthly cost (USD, 100k requests, GPT-4 Turbo input)")
    ax.set_xlabel("Language")
    ax.set_title("Monthly cost gap vs English (cl100k_base)", fontsize=14)
    ax.legend()
    ax.tick_params(axis="x", rotation=45)

    _footer(ax, manifest)
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / "fig3_cost.png"
    svg = out_dir / "fig3_cost.svg"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(svg, format="svg", bbox_inches="tight")
    plt.close(fig)
    return png, svg
```

`tests/unit/test_figures_1_3.py`:

```python
import pytest
from pathlib import Path
from fertiscope.report.figures import fig1_heatmap, fig2_premium_by_script, fig3_cost
from fertiscope.report.palette import FAMILY_COLORS, SCRIPT_COLORS

pytest.importorskip("pandas")
pytest.importorskip("matplotlib")


def _fixture_run(tmp_path):
    """Build a tiny results dir."""
    import json, pandas as pd
    rows = []
    for iso, script, premium, premium_ci_low, premium_ci_high, cost_ratio, family in [
        ("eng","Latn",1.00,1.00,1.00,1.00,"openai"),
        ("vie","Latn",2.25,2.10,2.40,2.25,"openai"),
        ("tam","Taml",7.19,6.90,7.50,7.19,"openai"),
        ("mya","Mymr",11.20,10.5,11.9,11.20,"openai"),
    ]:
        for tok in ["openai/cl100k_base","openai/o200k_base"]:
            rows.append(dict(
                corpus="flores", lang=iso, iso=iso, script=script, family="x",
                tokenizer=tok, tokenizer_family="openai", tokenizer_backend="tiktoken",
                n_sentences=50, tokens_sum=100, words_sum=10, chars_sum=200, bytes_sum=300,
                fertility=premium*1.3, fertility_ci_low=premium*1.2, fertility_ci_high=premium*1.4,
                premium=premium, premium_ci_low=premium_ci_low, premium_ci_high=premium_ci_high,
                cost_ratio=cost_ratio, cost_ratio_ci_low=cost_ratio*0.95, cost_ratio_ci_high=cost_ratio*1.05,
                cpt=4.5, cpt_ci_low=4.4, cpt_ci_high=4.6,
                bpt=2.3, bpt_ci_low=2.2, bpt_ci_high=2.4,
                segmenter_used="icu", tokenizer_unavailable=False, skip_reason=None,
            ))
    df = pd.DataFrame(rows)
    df.to_csv(tmp_path/"results.csv", index=False)
    (tmp_path/"manifest.json").write_text(json.dumps({"config_sha256":"abc1234567890"*5}), encoding="utf-8")
    return tmp_path


def test_fig1_heatmap(tmp_path):
    run = _fixture_run(tmp_path/"run")
    out = tmp_path/"figs"
    png, svg = fig1_heatmap(run, out)
    assert png.exists() and svg.exists()
    assert png.stat().st_size > 1000
    assert png.stat().st_size < 1_000_000


def test_fig2_script(tmp_path):
    run = _fixture_run(tmp_path/"run")
    out = tmp_path/"figs"
    png, svg = fig2_premium_by_script(run, out)
    assert png.exists() and svg.exists()


def test_fig3_cost(tmp_path):
    run = _fixture_run(tmp_path/"run")
    out = tmp_path/"figs"
    png, svg = fig3_cost(run, out)
    assert png.exists() and svg.exists()


def test_okabe_palette_complete():
    assert len(FAMILY_COLORS) >= 8
    # All hex strings
    for color in FAMILY_COLORS.values():
        assert color.startswith("#") and len(color) in (4, 7)
```

### Notes

- `matplotlib.use("Agg")` is essential for headless CI.
- `svg.hashsalt = "fertiscope"` fixes the SVG generator's hash → byte-stable SVG output for the same input.
- DejaVu Sans is bundled with matplotlib — guaranteed to support Devanagari, Tamil, Bengali, Burmese, Khmer, Lao glyphs (though rendering quality varies).
- Figures save as both PNG (publication raster) and SVG (vector for the website).
- The 5-worst-cell text annotation on the heatmap is a UX touch — communicates the punchline at a glance.

## Acceptance Criteria

- [ ] `fig1_heatmap(run_dir, out_dir)` produces `fig1_heatmap.png` and `.svg`.
- [ ] `fig2_premium_by_script(...)` produces files.
- [ ] `fig3_cost(...)` produces files.
- [ ] Each PNG is < 1MB and > 1KB.
- [ ] Provenance footer text "fertiscope vX.Y.Z · manifest abc1234" present.
- [ ] FAMILY_COLORS has ≥ 8 distinct hex strings.
- [ ] SCRIPT_COLORS has all 12 study scripts.
- [ ] All 4 unit tests pass.
- [ ] `mypy --strict src/fertiscope/report/` passes.
- [ ] Re-running fig generation produces bit-identical SVG (hashsalt set).

## User Stories

### Story: Author regenerates Figure 1 for v2

1. Runs `fertiscope figures --run runs/main --out runs/main/figures`.
2. Six PNGs + 6 SVGs in figures/.
3. Drops `fig1_heatmap.pdf` into the LaTeX paper.

### Story: Colorblind reviewer reads Figure 2

1. Reviewer with deuteranopia opens fig2.
2. Bars colored by script — Okabe-Ito palette → all distinguishable.
3. Reviewer accepts figure.

### Story: Maintainer detects rendering drift

1. matplotlib updates, default font changes.
2. Re-running figures produces visually different SVGs.
3. Maintainer pins matplotlib in `[viz]` extras.

---

Blocked by: #025
