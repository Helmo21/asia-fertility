"""Visualize the llama3.1:8b context-window needle-in-haystack sweep.

Outputs two panels in one figure:
  (a) Recall heatmap: rows = context window, columns = injection depth (5/25/50/75/95%).
  (b) Recall latency vs context window (log-x).
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

HERE = Path(__file__).parent
RESULTS = HERE / "sweep_results.json"
OUT_PNG = HERE / "sweep_results.png"

POSITIONS = [5.0, 25.0, 50.0, 75.0, 95.0]


def load():
    data = json.loads(RESULTS.read_text())
    rows = sorted(
        (w for w in data["windows"] if "recall_results" in w),
        key=lambda w: w["window"],
    )
    return data["model"], rows


def build_matrix(rows):
    mat = np.zeros((len(rows), len(POSITIONS)), dtype=int)
    for i, row in enumerate(rows):
        rec = row["recall_results"]
        for j, pct in enumerate(POSITIONS):
            hit = next((r for r in rec.values() if r["injected_at_pct"] == pct), None)
            mat[i, j] = 1 if (hit and hit["recalled"]) else 0
    return mat


def fmt_window(n):
    return f"{n // 1024}k" if n >= 1024 else str(n)


def main():
    model, rows = load()
    mat = build_matrix(rows)
    windows = [r["window"] for r in rows]
    recall_s = [r["recall_seconds"] for r in rows]

    fig, (ax_heat, ax_lat) = plt.subplots(
        1, 2, figsize=(13, 5.2), gridspec_kw={"width_ratios": [1.4, 1.0]}
    )

    # --- (a) Heatmap ------------------------------------------------------
    cmap = ListedColormap(["#f4f1ea", "#1f8a4c"])  # lost / recalled
    ax_heat.imshow(mat, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax_heat.set_xticks(range(len(POSITIONS)))
    ax_heat.set_xticklabels([f"{int(p)}%" for p in POSITIONS])
    ax_heat.set_yticks(range(len(windows)))
    ax_heat.set_yticklabels([fmt_window(w) for w in windows])
    ax_heat.set_xlabel("Marker injection depth (% of context)")
    ax_heat.set_ylabel("Context window (num_ctx)")
    ax_heat.set_title("Needle recall by injection depth")
    # Cell annotations
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            txt = "RECALL" if mat[i, j] == 1 else "LOST"
            color = "white" if mat[i, j] == 1 else "#7a6e5d"
            ax_heat.text(j, i, txt, ha="center", va="center", fontsize=8, color=color)
    # Gridlines
    ax_heat.set_xticks(np.arange(-0.5, len(POSITIONS), 1), minor=True)
    ax_heat.set_yticks(np.arange(-0.5, len(windows), 1), minor=True)
    ax_heat.grid(which="minor", color="white", linewidth=1.5)
    ax_heat.tick_params(which="minor", length=0)
    ax_heat.legend(
        handles=[
            Patch(facecolor="#1f8a4c", label="Recalled"),
            Patch(facecolor="#f4f1ea", edgecolor="#cabba0", label="Lost"),
        ],
        loc="upper right",
        bbox_to_anchor=(1.0, -0.12),
        ncol=2,
        frameon=False,
    )

    # --- (b) Latency line -------------------------------------------------
    ax_lat.plot(windows, recall_s, marker="o", color="#264653", linewidth=2)
    ax_lat.set_xscale("log", base=2)
    ax_lat.set_xticks(windows)
    ax_lat.set_xticklabels([fmt_window(w) for w in windows])
    ax_lat.set_xlabel("Context window (num_ctx)")
    ax_lat.set_ylabel("Recall latency (s)")
    ax_lat.set_title("Recall latency vs context window")
    ax_lat.grid(alpha=0.3)
    for x, y in zip(windows, recall_s):
        ax_lat.annotate(f"{y:.0f}s", (x, y), textcoords="offset points",
                        xytext=(0, 8), ha="center", fontsize=9)

    fig.suptitle(
        f"Context degradation sweep — {model} (FLORES-200 English)",
        fontsize=13, fontweight="bold", y=1.02,
    )
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
    print(f"Saved {OUT_PNG}")


if __name__ == "__main__":
    main()
