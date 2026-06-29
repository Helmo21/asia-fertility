# Figures 4–6 (context exhaustion, in-context capacity, premium-vs-recall)

Status: pending
Tags: `figures`, `matplotlib`, `niah`, `report`
Depends on: #025, #030, #031
Blocks: #033

## Scope

The remaining three paper figures. Figure 6 cross-references NIAH results (#030) and gracefully degrades when those aren't available.

### Files to create

- `tests/unit/test_figures_4_6.py`

### Files to modify

- `src/fertiscope/report/figures.py` — add `fig4_context_exhaustion`, `fig5_in_context_capacity`, `fig6_premium_vs_recall`.
- `src/fertiscope/cli.py` — complete the `figures` command to run all 6.

### Interface and contract

Add to `src/fertiscope/report/figures.py`:

```python
def fig4_context_exhaustion(run_dir: str | Path, out_dir: Path,
                            tokenizer_id: str = "openai/cl100k_base",
                            words_per_turn: int = 100,
                            window: int = 4096) -> tuple[Path, Path]:
    """Cumulative context use across turns. Reproduces paper Figure 2."""
    _setup_mpl()
    import matplotlib.pyplot as plt
    import numpy as np
    from ._io import load_run
    from .palette import SCRIPT_COLORS

    df, manifest = load_run(run_dir)
    df = df[df["skip_reason"].isna()]
    df = df[df["tokenizer"] == tokenizer_id]

    fig, ax = plt.subplots(figsize=(10, 6))
    turns = np.arange(0, 50)
    for _, row in df.iterrows():
        if np.isnan(row["fertility"]):
            continue
        # tokens per turn = fertility * words_per_turn
        tokens_per_turn = row["fertility"] * words_per_turn
        cum = turns * tokens_per_turn
        color = SCRIPT_COLORS.get(row["script"], "#888")
        ax.plot(turns, cum, color=color, alpha=0.7, label=row["iso"])
        # Mark crossing point
        crossings = np.where(cum >= window)[0]
        if len(crossings) > 0:
            t = crossings[0]
            ax.scatter([t], [cum[t]], color=color, s=30, zorder=5)

    ax.axhline(y=window, color="black", linestyle="--", label=f"{window}-token window")
    ax.set_xlabel("Turn")
    ax.set_ylabel("Cumulative tokens")
    ax.set_title(f"Context exhaustion · {tokenizer_id} · {words_per_turn} words/turn")
    ax.legend(loc="upper left", ncol=2, fontsize=8)

    _footer(ax, manifest)
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / "fig4_context_exhaustion.png"
    svg = out_dir / "fig4_context_exhaustion.svg"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(svg, format="svg", bbox_inches="tight")
    plt.close(fig)
    return png, svg


def fig5_in_context_capacity(run_dir: str | Path, out_dir: Path,
                             tokenizer_id: str = "openai/cl100k_base",
                             window: int = 8192, reply_reserve: int = 512,
                             words_per_example: int = 100) -> tuple[Path, Path]:
    """Bar chart: how many in-context examples fit per language. Reproduces paper Figure 3."""
    _setup_mpl()
    import matplotlib.pyplot as plt
    import numpy as np
    from ._io import load_run
    from .palette import SCRIPT_COLORS

    df, manifest = load_run(run_dir)
    df = df[df["skip_reason"].isna()]
    df = df[df["tokenizer"] == tokenizer_id]

    df = df.copy()
    df["tokens_per_example"] = df["fertility"] * words_per_example
    df["examples_fit"] = ((window - reply_reserve) // df["tokens_per_example"]).astype(int)
    df = df.sort_values("examples_fit")

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = [SCRIPT_COLORS.get(s, "#888") for s in df["script"]]
    ax.bar(df["iso"], df["examples_fit"], color=colors)
    ax.set_ylabel(f"Examples that fit in {window}-token window")
    ax.set_xlabel("Language")
    ax.set_title(f"In-context capacity · {tokenizer_id} · {words_per_example}-word examples", fontsize=14)
    ax.tick_params(axis="x", rotation=45)

    _footer(ax, manifest)
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / "fig5_in_context_capacity.png"
    svg = out_dir / "fig5_in_context_capacity.svg"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(svg, format="svg", bbox_inches="tight")
    plt.close(fig)
    return png, svg


def fig6_premium_vs_recall(run_dir: str | Path, out_dir: Path,
                           niah_run_dir: str | Path | None = None) -> tuple[Path, Path]:
    """Scatter: x = premium, y = recall @ 128k. Renders placeholder if NIAH missing."""
    _setup_mpl()
    import matplotlib.pyplot as plt
    from ._io import load_run
    from .palette import SCRIPT_COLORS
    from pathlib import Path as P

    df, manifest = load_run(run_dir)

    fig, ax = plt.subplots(figsize=(8, 6))

    if niah_run_dir is None or not P(niah_run_dir).exists():
        ax.text(0.5, 0.5,
                "Figure 6 — NIAH data required\n\nRun: fertiscope niah run --config configs/niah_main.yaml\nThen re-run figures with --niah-run runs/niah/main",
                ha="center", va="center", fontsize=12, transform=ax.transAxes,
                bbox=dict(boxstyle="round", facecolor="#FFEEEE", edgecolor="#CC0000"))
        ax.set_axis_off()
        _footer(ax, manifest)
    else:
        import pandas as pd
        niah_df = pd.read_csv(P(niah_run_dir) / "results.csv")
        recall = niah_df[niah_df["fill_tokens"] >= 100000].groupby("iso")["recalled"].mean().to_dict()

        x, y, c, labels = [], [], [], []
        sub = df[df["skip_reason"].isna() & (df["tokenizer"] == "openai/cl100k_base")]
        for _, row in sub.iterrows():
            iso = row["iso"]
            if iso in recall:
                x.append(row["premium"])
                y.append(recall[iso])
                c.append(SCRIPT_COLORS.get(row["script"], "#888"))
                labels.append(iso)
        ax.scatter(x, y, c=c, s=80, alpha=0.7)
        for xi, yi, lab in zip(x, y, labels):
            ax.annotate(lab, (xi, yi), xytext=(5, 5), textcoords="offset points", fontsize=8)
        ax.set_xlabel("Premium (× English)")
        ax.set_ylabel("Recall @ ≥100k tokens")
        ax.set_title("Premium vs NIAH recall at long context", fontsize=14)
        _footer(ax, manifest)

    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / "fig6_premium_vs_recall.png"
    svg = out_dir / "fig6_premium_vs_recall.svg"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(svg, format="svg", bbox_inches="tight")
    plt.close(fig)
    return png, svg
```

Update CLI:

```python
@app.command()
def figures(run_dir: str = typer.Option(..., "--run"),
            out_dir: str = typer.Option(..., "--out"),
            niah_run: str | None = typer.Option(None, "--niah-run")) -> None:
    """Regenerate all 6 figures from a study run."""
    from pathlib import Path
    from fertiscope.report.figures import (
        fig1_heatmap, fig2_premium_by_script, fig3_cost,
        fig4_context_exhaustion, fig5_in_context_capacity, fig6_premium_vs_recall,
    )
    out = Path(out_dir)
    for name, fn in [
        ("fig1", lambda: fig1_heatmap(run_dir, out)),
        ("fig2", lambda: fig2_premium_by_script(run_dir, out)),
        ("fig3", lambda: fig3_cost(run_dir, out)),
        ("fig4", lambda: fig4_context_exhaustion(run_dir, out)),
        ("fig5", lambda: fig5_in_context_capacity(run_dir, out)),
        ("fig6", lambda: fig6_premium_vs_recall(run_dir, out, niah_run)),
    ]:
        png, svg = fn()
        typer.echo(f"  ✓ {name}: {png.name}, {svg.name}")
    typer.echo(f"All 6 figures written to {out}")
```

`tests/unit/test_figures_4_6.py`: same fixture pattern as #031, asserts files produced.

### Notes

- Fig 4 reproduces paper Figure 2 (Tamil/Malayalam cross 4096 tokens around turn 3, English around turn 32).
- Fig 5 reproduces paper Figure 3 (English fits ~60 examples, Tamil 5-6).
- Fig 6 is the **new figure for v2** — paper Figure 6. Without NIAH data, render an informative placeholder rather than crash.
- Use `gridspec` for Figure 1 if you want a sidebar legend, but standard `imshow + colorbar` is fine.

## Acceptance Criteria

- [ ] `fig4_context_exhaustion` produces PNG + SVG; lines reach the 4096 threshold.
- [ ] `fig5_in_context_capacity` produces PNG + SVG with bars ordered ascending.
- [ ] `fig6_premium_vs_recall` with `niah_run_dir=None` renders placeholder (no crash).
- [ ] `fig6_premium_vs_recall` with NIAH data produces a scatter with ≥ 4 points.
- [ ] `fertiscope figures --run X --out Y` generates 6 PNGs + 6 SVGs and prints progress.
- [ ] All 3 unit tests pass.
- [ ] All 6 figures saved as PNG (300 dpi) + SVG.
- [ ] `mypy --strict src/fertiscope/report/figures.py` passes.

## User Stories

### Story: Author drafts the v2 paper

1. Runs `fertiscope run --config study_main.yaml` then `fertiscope niah run --config niah_main.yaml`.
2. `fertiscope figures --run runs/main --niah-run runs/niah/main --out runs/main/figures`.
3. Six figures land. Author drops `.pdf` versions into LaTeX.

### Story: Researcher without NIAH data

1. Just runs the study (no NIAH).
2. `fertiscope figures --run runs/main --out figs`.
3. Figures 1-5 generated normally; Figure 6 shows placeholder.
4. Researcher knows how to fill the gap.

---

Blocked by: #025, #030, #031
