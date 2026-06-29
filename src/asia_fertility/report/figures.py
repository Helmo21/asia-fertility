"""All six paper figures, deterministic, 300dpi PNG + SVG."""

from __future__ import annotations

from pathlib import Path

from asia_fertility import __version__

from ._io import load_run
from .palette import SCRIPT_COLORS, SEQUENTIAL


def _setup_mpl() -> None:
    import matplotlib

    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "asia_fertility"
    matplotlib.rcParams["font.family"] = "DejaVu Sans"
    matplotlib.rcParams["figure.dpi"] = 100


def _footer(ax, manifest: dict) -> None:
    sha = (manifest.get("config_sha256") or "")[:7]
    ax.figure.text(
        0.99,
        0.005,
        f"asia-fertility v{__version__} · manifest {sha}",
        ha="right",
        va="bottom",
        fontsize=6,
        alpha=0.5,
    )


def _save(fig, out_dir: Path, name: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / f"{name}.png"
    svg = out_dir / f"{name}.svg"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(svg, format="svg", bbox_inches="tight")
    return png, svg


def fig1_heatmap(run_dir: str | Path, out_dir: Path) -> tuple[Path, Path]:
    """Cost-ratio heatmap: rows=languages (sorted), cols=tokenizers, cells=cost ratio."""
    _setup_mpl()
    import matplotlib.pyplot as plt
    import numpy as np

    df, manifest = load_run(run_dir)
    df = df[df["skip_reason"].isna() | (df["skip_reason"] == "")]
    df = df[df["iso"] != "eng"]
    pivot = df.pivot_table(index="iso", columns="tokenizer", values="cost_ratio", aggfunc="mean")
    if pivot.empty:
        raise ValueError("No data for fig1_heatmap")
    # Sort languages by worst-case (max cost ratio across tokenizers)
    pivot = pivot.reindex(pivot.max(axis=1).sort_values().index)

    fig, ax = plt.subplots(figsize=(11, 7))
    im = ax.imshow(pivot.values, aspect="auto", cmap=SEQUENTIAL, vmin=1.0, vmax=15.0)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([c.split("/")[-1] for c in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    plt.colorbar(im, ax=ax, label="Cost ratio (× English)")
    ax.set_title("Same-content cost ratio by language × tokenizer", fontsize=13)

    # Annotate top 5 worst
    flat = [
        (i, j, pivot.values[i, j])
        for i in range(pivot.shape[0])
        for j in range(pivot.shape[1])
        if not np.isnan(pivot.values[i, j])
    ]
    flat.sort(key=lambda x: -x[2])
    for i, j, v in flat[:5]:
        ax.text(
            j,
            i,
            f"{v:.1f}×",
            ha="center",
            va="center",
            color="white",
            fontsize=8,
            fontweight="bold",
        )

    _footer(ax, manifest)
    return _save(fig, Path(out_dir), "fig1_heatmap")


def fig2_premium_by_script(run_dir: str | Path, out_dir: Path) -> tuple[Path, Path]:
    """Cost ratio bars on cl100k, colored by script, sorted descending."""
    _setup_mpl()
    import matplotlib.pyplot as plt

    df, manifest = load_run(run_dir)
    df = df[(df["skip_reason"].isna()) | (df["skip_reason"] == "")]
    df = df[df["iso"] != "eng"]
    df = df[df["tokenizer"] == "openai/cl100k_base"]
    df_sorted = df.sort_values("cost_ratio", ascending=False).reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = [SCRIPT_COLORS.get(s, "#888") for s in df_sorted["script"]]
    ax.bar(
        df_sorted["iso"], df_sorted["cost_ratio"], color=colors, edgecolor="white", linewidth=0.5
    )

    # Error bars from CI
    yerr_low = (df_sorted["cost_ratio"] - df_sorted["cost_ratio_ci_low"]).clip(lower=0)
    yerr_high = (df_sorted["cost_ratio_ci_high"] - df_sorted["cost_ratio"]).clip(lower=0)
    ax.errorbar(
        df_sorted["iso"],
        df_sorted["cost_ratio"],
        yerr=[yerr_low, yerr_high],
        fmt="none",
        color="black",
        alpha=0.4,
        capsize=2,
    )

    ax.set_ylabel("Cost ratio (× English)", fontsize=11)
    ax.set_xlabel("Language", fontsize=11)
    ax.set_title("Same-content cost on cl100k_base, by language", fontsize=13)
    ax.tick_params(axis="x", rotation=45)

    # Script legend
    legend_handles = []
    seen_scripts: set[str] = set()
    for script in df_sorted["script"]:
        if script not in seen_scripts:
            seen_scripts.add(script)
            legend_handles.append(
                plt.Rectangle((0, 0), 1, 1, color=SCRIPT_COLORS.get(script, "#888"), label=script)
            )
    ax.legend(handles=legend_handles, title="Script", loc="upper right", fontsize=8)

    _footer(ax, manifest)
    return _save(fig, Path(out_dir), "fig2_premium_by_script")


def fig3_cost(run_dir: str | Path, out_dir: Path) -> tuple[Path, Path]:
    """Monthly cost (USD) at 100k requests/month, GPT-4 Turbo input pricing."""
    _setup_mpl()
    import matplotlib.pyplot as plt

    df, manifest = load_run(run_dir)
    df = df[(df["skip_reason"].isna()) | (df["skip_reason"] == "")]
    df = df[df["tokenizer"] == "openai/cl100k_base"]

    # 27 tokens/request English baseline (from paper); 100k requests; $10/1M input
    monthly_requests = 100_000
    avg_eng_tokens = 27
    rate = 10.0 / 1_000_000
    df = df.copy()
    df["monthly_usd"] = df["cost_ratio"] * avg_eng_tokens * monthly_requests * rate
    df = df.sort_values("monthly_usd").reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = [SCRIPT_COLORS.get(s, "#888") for s in df["script"]]
    ax.bar(df["iso"], df["monthly_usd"], color=colors, edgecolor="white", linewidth=0.5)
    baseline = df.loc[df["iso"] == "eng", "monthly_usd"]
    if len(baseline) > 0:
        ax.axhline(
            baseline.values[0],
            color="black",
            linestyle="--",
            linewidth=1,
            label=f"English: ${baseline.values[0]:.0f}/mo",
        )
    ax.set_ylabel("Estimated monthly cost (USD, 100k requests, GPT-4 Turbo input)")
    ax.set_xlabel("Language")
    ax.set_title("Monthly cost gap vs English (cl100k_base)", fontsize=13)
    ax.legend()
    ax.tick_params(axis="x", rotation=45)

    _footer(ax, manifest)
    return _save(fig, Path(out_dir), "fig3_cost")


def fig4_context_exhaustion(run_dir: str | Path, out_dir: Path) -> tuple[Path, Path]:
    """Cumulative tokens across turns; mark window crossings."""
    _setup_mpl()
    import matplotlib.pyplot as plt
    import numpy as np

    df, manifest = load_run(run_dir)
    df = df[(df["skip_reason"].isna()) | (df["skip_reason"] == "")]
    df = df[df["tokenizer"] == "openai/cl100k_base"]

    window = 4096
    words_per_turn = 100
    turns = np.arange(0, 50)

    fig, ax = plt.subplots(figsize=(10, 6))
    for _, row in df.iterrows():
        if np.isnan(row["fertility"]):
            continue
        tokens_per_turn = row["fertility"] * words_per_turn
        cum = turns * tokens_per_turn
        color = SCRIPT_COLORS.get(row["script"], "#888")
        ax.plot(turns, cum, color=color, alpha=0.7, label=row["iso"], linewidth=1.2)
        crossings = np.where(cum >= window)[0]
        if len(crossings) > 0:
            t = crossings[0]
            ax.scatter(
                [t], [cum[t]], color=color, s=30, zorder=5, edgecolors="black", linewidths=0.5
            )

    ax.axhline(y=window, color="black", linestyle="--", linewidth=1, label=f"{window}-token window")
    ax.set_xlabel("Turn (100 words/turn)")
    ax.set_ylabel("Cumulative tokens")
    ax.set_ylim(0, window * 2.5)
    ax.set_title("Context-window exhaustion · cl100k_base", fontsize=13)
    ax.legend(loc="upper left", ncol=2, fontsize=8)

    _footer(ax, manifest)
    return _save(fig, Path(out_dir), "fig4_context_exhaustion")


def fig5_in_context_capacity(run_dir: str | Path, out_dir: Path) -> tuple[Path, Path]:
    """How many 100-word examples fit in an 8192-token window."""
    _setup_mpl()
    import matplotlib.pyplot as plt

    df, manifest = load_run(run_dir)
    df = df[(df["skip_reason"].isna()) | (df["skip_reason"] == "")]
    df = df[df["tokenizer"] == "openai/cl100k_base"]

    window = 8192
    reply_reserve = 512
    words_per_example = 100

    df = df.copy()
    df["tokens_per_example"] = df["fertility"] * words_per_example
    df["examples_fit"] = ((window - reply_reserve) // df["tokens_per_example"]).astype(int)
    df = df.sort_values("examples_fit").reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = [SCRIPT_COLORS.get(s, "#888") for s in df["script"]]
    ax.bar(df["iso"], df["examples_fit"], color=colors, edgecolor="white", linewidth=0.5)
    ax.set_ylabel(f"Examples that fit in {window}-token window")
    ax.set_xlabel("Language")
    ax.set_title(
        f"In-context capacity · cl100k_base · {words_per_example}-word examples", fontsize=13
    )
    ax.tick_params(axis="x", rotation=45)

    for i, val in enumerate(df["examples_fit"]):
        ax.text(i, val + 0.5, str(val), ha="center", va="bottom", fontsize=8)

    _footer(ax, manifest)
    return _save(fig, Path(out_dir), "fig5_in_context_capacity")


def fig6_premium_vs_recall(
    run_dir: str | Path, out_dir: Path, niah_run_dir: str | Path | None = None
) -> tuple[Path, Path]:
    """Scatter: cost ratio vs NIAH recall at long context."""
    _setup_mpl()
    from pathlib import Path as P

    import matplotlib.pyplot as plt

    df, manifest = load_run(run_dir)
    fig, ax = plt.subplots(figsize=(8, 6))

    if (
        niah_run_dir is None
        or not P(niah_run_dir).exists()
        or not (P(niah_run_dir) / "results.csv").exists()
    ):
        ax.text(
            0.5,
            0.5,
            "Figure 6 — NIAH data required.\n\nRun: asia-fertility niah run --config configs/niah_main.yaml\nThen re-run figures with --niah-run <output_dir>",
            ha="center",
            va="center",
            fontsize=11,
            transform=ax.transAxes,
            bbox=dict(boxstyle="round", facecolor="#FFEEEE", edgecolor="#CC0000"),
        )
        ax.set_axis_off()
        _footer(ax, manifest)
        return _save(fig, Path(out_dir), "fig6_premium_vs_recall")

    import pandas as pd

    niah_df = pd.read_csv(P(niah_run_dir) / "results.csv")
    recall = niah_df.groupby("iso")["recalled"].mean().to_dict()
    df_ok = df[
        (df["skip_reason"].isna() | (df["skip_reason"] == ""))
        & (df["tokenizer"] == "openai/cl100k_base")
    ]

    x, y, c, labels = [], [], [], []
    for _, row in df_ok.iterrows():
        iso = row["iso"]
        if iso in recall:
            x.append(row["cost_ratio"])
            y.append(recall[iso])
            c.append(SCRIPT_COLORS.get(row["script"], "#888"))
            labels.append(iso)

    ax.scatter(x, y, c=c, s=80, alpha=0.7, edgecolors="black", linewidths=0.5)
    for xi, yi, lab in zip(x, y, labels):
        ax.annotate(lab, (xi, yi), xytext=(5, 5), textcoords="offset points", fontsize=9)
    ax.set_xlabel("Cost ratio (× English, cl100k_base)")
    ax.set_ylabel("Recall (mean across positions × trials)")
    ax.set_title("Cost vs NIAH recall", fontsize=13)
    ax.set_xscale("log")

    _footer(ax, manifest)
    return _save(fig, Path(out_dir), "fig6_premium_vs_recall")


def fig7_cost_vs_latency(
    run_dir: str | Path,
    out_dir: Path,
    latency_run_dir: str | Path | None = None,
    baseline_lang: str = "eng",
) -> tuple[Path, Path]:
    """Scatter: cost_ratio vs measured wall-clock latency ratio.

    Each dot = one (model, language) cell. Color encodes script. The
    diagonal (latency_ratio = cost_ratio) is overlaid; deviation from
    the diagonal is the message of the figure. Pearson r is computed
    and printed in the title.

    If `latency_run_dir` is None or missing, a placeholder is rendered
    explaining how to produce the data.
    """
    _setup_mpl()
    from pathlib import Path as P

    import matplotlib.pyplot as plt

    df, manifest = load_run(run_dir)
    fig, ax = plt.subplots(figsize=(8, 6))

    if (
        latency_run_dir is None
        or not P(latency_run_dir).exists()
        or not (P(latency_run_dir) / "results.csv").exists()
    ):
        ax.text(
            0.5,
            0.5,
            "Figure 7 — latency data required.\n\nRun: asia-fertility latency run --config configs/latency_main.yaml\nThen re-run figures with --latency-run <output_dir>",
            ha="center",
            va="center",
            fontsize=11,
            transform=ax.transAxes,
            bbox=dict(boxstyle="round", facecolor="#EEEEFF", edgecolor="#0000CC"),
        )
        ax.set_axis_off()
        _footer(ax, manifest)
        return _save(fig, Path(out_dir), "fig7_cost_vs_latency")

    import numpy as np
    import pandas as pd

    lat = pd.read_csv(P(latency_run_dir) / "results.csv")
    # Drop warmup + errored rows
    lat = lat[~lat["is_warmup"].astype(str).str.lower().eq("true")]
    lat = lat[lat["error"].fillna("") == ""]

    # Mean total_ms per (model, iso)
    g = lat.groupby(["model", "iso"])["total_ms"].mean().reset_index()
    # Latency ratio per (model, iso) = total_ms(iso) / total_ms(baseline) for that model
    baselines = g[g["iso"] == baseline_lang].set_index("model")["total_ms"]
    g = g[g["iso"] != baseline_lang].copy()
    g["latency_ratio"] = g.apply(
        lambda r: r["total_ms"] / baselines.get(r["model"], np.nan), axis=1
    )

    # Cost ratio is tokenizer-dependent. Use cl100k_base as the canonical reference.
    # (Same as fig2/fig3.)
    df_cost = df[(df["skip_reason"].isna() | (df["skip_reason"] == ""))]
    df_cost = df_cost[df_cost["tokenizer"] == "openai/cl100k_base"]
    cost_by_iso = df_cost.set_index("iso")["cost_ratio"].to_dict()
    script_by_iso = df_cost.set_index("iso")["script"].to_dict()

    g["cost_ratio"] = g["iso"].map(cost_by_iso)
    g["script"] = g["iso"].map(script_by_iso)
    g = g.dropna(subset=["cost_ratio", "latency_ratio"])

    if g.empty:
        ax.text(
            0.5,
            0.5,
            "No overlapping (model, lang) cells\nbetween leaderboard and latency runs.",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        ax.set_axis_off()
        _footer(ax, manifest)
        return _save(fig, Path(out_dir), "fig7_cost_vs_latency")

    # Plot per-model dots
    colors = [SCRIPT_COLORS.get(s, "#888") for s in g["script"]]
    ax.scatter(
        g["cost_ratio"],
        g["latency_ratio"],
        c=colors,
        s=80,
        alpha=0.7,
        edgecolors="black",
        linewidths=0.5,
    )

    # Annotate one dot per iso (mean across models if multiple)
    iso_means = g.groupby("iso")[["cost_ratio", "latency_ratio"]].mean()
    for iso, row in iso_means.iterrows():
        ax.annotate(
            iso,
            (row["cost_ratio"], row["latency_ratio"]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=9,
        )

    # Diagonal: y = x  (latency_ratio = cost_ratio)
    lim = max(g["cost_ratio"].max(), g["latency_ratio"].max()) * 1.1
    ax.plot([1, lim], [1, lim], color="black", linestyle="--", alpha=0.4, label="y = x")

    # Pearson r
    r = float(np.corrcoef(g["cost_ratio"], g["latency_ratio"])[0, 1])

    ax.set_xlabel("Cost ratio (× English, cl100k_base)")
    ax.set_ylabel(f"Latency ratio (× {baseline_lang}, wall-clock)")
    ax.set_title(f"Cost vs measured latency · Pearson r = {r:.3f}", fontsize=13)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.legend(loc="upper left", fontsize=8)

    _footer(ax, manifest)
    return _save(fig, Path(out_dir), "fig7_cost_vs_latency")
