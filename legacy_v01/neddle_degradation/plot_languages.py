"""Visualize the multilingual needle-in-haystack sweep results.

Layout:
  Top:    2x2 grid of recall heatmaps, one per language (window x depth).
  Bottom: two summary panels:
            (a) recall latency vs context window, one line per language
            (b) total markers recalled (0-5) vs context window, one line per language
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

HERE = Path(__file__).parent
RESULTS = HERE / "sweep_languages_results.json"
OUT_PNG = HERE / "sweep_languages.png"

POSITIONS = [5.0, 25.0, 50.0, 75.0, 95.0]
WINDOWS = [4096, 8192, 16384, 32768, 65536, 131072]
LANG_ORDER = ["Thai", "Tamil", "Hindi", "Khmer"]
LANG_COLOR = {
    "Thai":  "#e76f51",
    "Tamil": "#2a9d8f",
    "Hindi": "#e9c46a",
    "Khmer": "#264653",
}


def fmt_window(n):
    return f"{n // 1024}k"


def load():
    data = json.loads(RESULTS.read_text())
    by = {lang: {} for lang in LANG_ORDER}
    for r in data["rows"]:
        if "error" in r:
            continue
        by[r["language"]][r["window"]] = r
    return data["model"], by


def lang_matrix(by_lang):
    mat = np.zeros((len(WINDOWS), len(POSITIONS)), dtype=int)
    for i, w in enumerate(WINDOWS):
        row = by_lang.get(w)
        if not row:
            mat[i, :] = -1
            continue
        rec = row["recall_results"]
        for j, pct in enumerate(POSITIONS):
            hit = next((r for r in rec.values() if r["injected_at_pct"] == pct), None)
            mat[i, j] = 1 if (hit and hit["recalled"]) else 0
    return mat


def draw_heatmap(ax, mat, title):
    cmap = ListedColormap(["#f4f1ea", "#1f8a4c"])
    ax.imshow(mat, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(POSITIONS)))
    ax.set_xticklabels([f"{int(p)}%" for p in POSITIONS], fontsize=8)
    ax.set_yticks(range(len(WINDOWS)))
    ax.set_yticklabels([fmt_window(w) for w in WINDOWS], fontsize=8)
    ax.set_title(title, fontsize=11, fontweight="bold")
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            if mat[i, j] == 1:
                ax.text(j, i, "Y", ha="center", va="center", fontsize=9, color="white",
                        fontweight="bold")
            elif mat[i, j] == 0:
                ax.text(j, i, "·", ha="center", va="center", fontsize=10, color="#a89989")
    ax.set_xticks(np.arange(-0.5, len(POSITIONS), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(WINDOWS), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.2)
    ax.tick_params(which="minor", length=0)


def main():
    model, by = load()

    fig = plt.figure(figsize=(14, 10))
    gs = fig.add_gridspec(3, 4, height_ratios=[1.4, 0.05, 1.0], hspace=0.45, wspace=0.30)

    # Row 0: heatmaps (one per language)
    for col, lang in enumerate(LANG_ORDER):
        ax = fig.add_subplot(gs[0, col])
        mat = lang_matrix(by[lang])
        draw_heatmap(ax, mat, lang)
        if col == 0:
            ax.set_ylabel("Context window (num_ctx)")
        if col in (0, 1, 2, 3):
            ax.set_xlabel("Injection depth")

    # Row 1: legend strip (use as legend area)
    legend_ax = fig.add_subplot(gs[1, :])
    legend_ax.axis("off")
    legend_ax.legend(
        handles=[
            Patch(facecolor="#1f8a4c", label="Recalled"),
            Patch(facecolor="#f4f1ea", edgecolor="#cabba0", label="Lost"),
        ],
        loc="center", ncol=2, frameon=False, fontsize=10,
    )

    # Row 2: summary line charts
    ax_lat = fig.add_subplot(gs[2, :2])
    ax_score = fig.add_subplot(gs[2, 2:])

    for lang in LANG_ORDER:
        windows = sorted(by[lang].keys())
        latencies = [by[lang][w]["recall_seconds"] for w in windows]
        scores = [sum(1 for r in by[lang][w]["recall_results"].values() if r["recalled"])
                  for w in windows]
        ax_lat.plot(windows, latencies, marker="o", linewidth=2,
                    color=LANG_COLOR[lang], label=lang)
        ax_score.plot(windows, scores, marker="s", linewidth=2,
                      color=LANG_COLOR[lang], label=lang)

    for ax in (ax_lat, ax_score):
        ax.set_xscale("log", base=2)
        ax.set_xticks(WINDOWS)
        ax.set_xticklabels([fmt_window(w) for w in WINDOWS])
        ax.set_xlabel("Context window (num_ctx)")
        ax.grid(alpha=0.3)
        ax.legend(loc="best", fontsize=9, frameon=True)

    ax_lat.set_ylabel("Recall latency (s)")
    ax_lat.set_title("Recall latency vs context window", fontsize=11)

    ax_score.set_ylabel("Markers recalled (of 5)")
    ax_score.set_ylim(-0.3, 5.3)
    ax_score.set_yticks(range(6))
    ax_score.set_title("Total markers recalled vs context window", fontsize=11)

    fig.suptitle(
        f"Multilingual needle-in-haystack sweep — {model} (FLORES-200)",
        fontsize=14, fontweight="bold", y=0.995,
    )

    fig.savefig(OUT_PNG, dpi=140, bbox_inches="tight")
    print(f"Saved {OUT_PNG}")


if __name__ == "__main__":
    main()
