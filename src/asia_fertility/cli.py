"""asia-fertility CLI entry point."""

from __future__ import annotations

import typer
from rich import print as rprint

from asia_fertility import __version__

app = typer.Typer(
    name="asia-fertility",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
    help="Tokenizer fertility, cost, and multi-turn context-budget analyzer for low-resource Asian languages.",
)

tokenizers_app = typer.Typer(help="Tokenizer registry commands.")
corpora_app = typer.Typer(help="Corpus registry commands.")
languages_app = typer.Typer(help="Language registry commands.")
niah_app = typer.Typer(help="Multi-turn needle-in-haystack benchmark commands.")
latency_app = typer.Typer(help="Wall-clock latency benchmark commands.")

app.add_typer(tokenizers_app, name="tokenizers")
app.add_typer(corpora_app, name="corpora")
app.add_typer(languages_app, name="languages")
app.add_typer(niah_app, name="niah")
app.add_typer(latency_app, name="latency")


@app.callback(invoke_without_command=True)
def _root(version: bool = typer.Option(False, "--version", "-V")) -> None:
    if version:
        rprint(f"asia-fertility {__version__}")
        raise typer.Exit()


# ----------------------------- measure ------------------------------------ #


@app.command()
def measure(
    text: str | None = typer.Option(None, "--text", help="Inline text to measure."),
    corpus: str | None = typer.Option(None, "--corpus", help="Corpus name (e.g. flores)."),
    path: str | None = typer.Option(None, "--path", help="Path to custom JSONL/CSV."),
    lang: str = typer.Option("eng", "--lang"),
    tokenizer: str = typer.Option("openai/o200k_base", "--tokenizer"),
    baseline_lang: str = typer.Option("eng", "--baseline-lang"),
    n_sentences: int | None = typer.Option(None, "--n-sentences"),
    n_resamples: int = typer.Option(1000, "--n-resamples"),
    rng_seed: int = typer.Option(42, "--rng-seed"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Compute fertility, premium, CPT, BPT for input text or corpus with bootstrap CIs."""
    from asia_fertility.core import per_sentence
    from asia_fertility.core.aggregate_ci import aggregate_with_cis
    from asia_fertility.core.segmentation import count_words
    from asia_fertility.corpora import Sentence, load_corpus
    from asia_fertility.tokenizers import get_tokenizer

    if text is None and corpus is None:
        typer.echo("Provide --text or --corpus", err=True)
        raise typer.Exit(code=2)

    tok = get_tokenizer(tokenizer)

    if text is not None:
        target_metrics = [
            per_sentence(Sentence(id="cli:0", lang=lang, text=text), tok, segmenter=count_words)
        ]
        baseline_metrics = None
    else:
        loaded = load_corpus(corpus, path=path) if corpus == "custom" else load_corpus(corpus)
        target_sentences = list(loaded.iter_sentences(lang, limit=n_sentences))
        if lang != baseline_lang:
            baseline_sentences = list(loaded.iter_sentences(baseline_lang, limit=n_sentences))
            baseline_metrics = [
                per_sentence(s, tok, segmenter=count_words) for s in baseline_sentences
            ]
        else:
            baseline_metrics = None
        target_metrics = [per_sentence(s, tok, segmenter=count_words) for s in target_sentences]

    agg = aggregate_with_cis(
        target_metrics, baseline=baseline_metrics, n_resamples=n_resamples, rng_seed=rng_seed
    )

    if json_out:
        import dataclasses
        import json as _json

        typer.echo(_json.dumps(dataclasses.asdict(agg), default=str, indent=2, ensure_ascii=False))
        return

    from rich.console import Console
    from rich.table import Table

    title = f"asia-fertility measure · lang={agg.lang} · tokenizer={agg.tokenizer_id} · n={agg.n_sentences}"
    table = Table(title=title, title_style="bold")
    table.add_column("Metric")
    table.add_column("Point", justify="right")
    table.add_column("95% CI", justify="right")

    def fmt(t: tuple[float, float, float] | None) -> tuple[str, str]:
        if t is None:
            return ("—", "—")
        p, lo, hi = t
        return (f"{p:.3f}", f"[{lo:.3f}, {hi:.3f}]")

    for name, val in [
        ("Fertility (tokens/word)", agg.fertility),
        ("Premium (vs baseline)", agg.premium),
        ("Cost ratio (same content)", agg.cost_ratio),
        ("CPT (chars/token)", agg.cpt),
        ("BPT (bytes/token)", agg.bpt),
    ]:
        p, ci = fmt(val)
        table.add_row(name, p, ci)
    Console().print(table)


# ----------------------------- cost --------------------------------------- #


@app.command()
def cost(
    text: str = typer.Option(..., "--text"),
    lang: str = typer.Option(..., "--lang"),
    models: str = typer.Option("openai/gpt-4o", "--models", help="Comma-separated model IDs"),
    currencies: str = typer.Option("USD", "--currencies", help="Comma-separated currency codes"),
    output_tokens_est: int = typer.Option(200, "--output-tokens-est"),
    prices_path: str | None = typer.Option(None, "--prices"),
    fx_path: str | None = typer.Option(None, "--fx"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Cost per model per language for a representative input."""
    from asia_fertility.cost import cost_of

    model_list = [m.strip() for m in models.split(",") if m.strip()]
    cur_list = [c.strip() for c in currencies.split(",") if c.strip()]
    rows = cost_of(
        text,
        models=model_list,
        output_tokens_est=output_tokens_est,
        currencies=cur_list,
        prices_path=prices_path,
        fx_path=fx_path,
    )

    if json_out:
        import dataclasses
        import json as _json

        typer.echo(_json.dumps([dataclasses.asdict(r) for r in rows], indent=2, ensure_ascii=False))
        return

    from rich.console import Console
    from rich.table import Table

    table = Table(
        title=f"Cost · lang={lang} · output_est={output_tokens_est} tokens", title_style="bold"
    )
    table.add_column("Model", style="cyan")
    table.add_column("Tokenizer", style="dim")
    table.add_column("In tok", justify="right")
    table.add_column("USD total", justify="right")
    for cur in cur_list:
        if cur != "USD":
            table.add_column(cur, justify="right")
    table.add_column("Cheapest", justify="center")

    for r in rows:
        cheapest = "[bold green]✓[/bold green]" if r.cheapest else ""
        cells = [r.model_id, r.tokenizer_id, str(r.input_tokens), f"${r.total_cost_usd:.6f}"]
        for cur in cur_list:
            if cur != "USD":
                cells.append(f"{r.costs_local.get(cur, 0):.2f}")
        cells.append(cheapest)
        table.add_row(*cells)
    Console().print(table)


# ----------------------------- run / reproduce ---------------------------- #


@app.command()
def run(
    config: str = typer.Option(..., "--config"),
    output_dir: str | None = typer.Option(None, "--output-dir"),
    hf_token: str | None = typer.Option(None, "--hf-token", envvar="HF_TOKEN"),
) -> None:
    """Full study from YAML config."""
    import os
    from pathlib import Path

    from rich.console import Console

    from asia_fertility.config import StudyConfig
    from asia_fertility.study.runner import run_study

    if hf_token:
        os.environ["HF_TOKEN"] = hf_token

    console = Console()
    cfg = StudyConfig.from_yaml(config)
    console.print(f"[bold]Loading study:[/bold] {cfg.name}")
    console.print(
        f"  languages: {len(cfg.languages)}, tokenizers: {len(cfg.tokenizers)}, corpora: {len(cfg.corpora)}"
    )
    expected = len(cfg.languages) * len(cfg.tokenizers) * len(cfg.corpora)
    console.print(f"  expected rows: {expected}")

    result = run_study(cfg)
    out = result.write_all(Path(output_dir) if output_dir else None)
    skipped = sum(1 for r in result.rows if r.skip_reason)
    console.print(
        f"[bold green]✓[/bold green] Wrote {len(result.rows)} rows ({skipped} skipped) to {out}"
    )
    console.print("  results.csv, results.json, results.parquet, leaderboard.json, manifest.json")
    if result.manifest:
        console.print(f"  Manifest SHA: {result.manifest['config_sha256'][:12]}...")


@app.command()
def reproduce(output_dir: str = typer.Option("runs/reproduce", "--output-dir")) -> None:
    """Offline reference suite — one-command credibility demo."""
    typer.echo("`reproduce` is wired to the bundled reference suite, which is not shipped in v0.2.")
    typer.echo(
        "Run `asia-fertility run --config configs/study_test.yaml` for a small smoke study instead."
    )
    raise typer.Exit(code=1)


# ----------------------------- figures / leaderboard ---------------------- #


@app.command()
def figures(
    run_dir: str = typer.Option(..., "--run"),
    out_dir: str = typer.Option(..., "--out"),
    niah_run: str | None = typer.Option(None, "--niah-run"),
    latency_run: str | None = typer.Option(None, "--latency-run"),
) -> None:
    """Regenerate the 7 paper figures from a study run."""
    from pathlib import Path

    from asia_fertility.report.figures import (
        fig1_heatmap,
        fig2_premium_by_script,
        fig3_cost,
        fig4_context_exhaustion,
        fig5_in_context_capacity,
        fig6_premium_vs_recall,
        fig7_cost_vs_latency,
    )

    out = Path(out_dir)
    for name, fn in [
        ("fig1", lambda: fig1_heatmap(run_dir, out)),
        ("fig2", lambda: fig2_premium_by_script(run_dir, out)),
        ("fig3", lambda: fig3_cost(run_dir, out)),
        ("fig4", lambda: fig4_context_exhaustion(run_dir, out)),
        ("fig5", lambda: fig5_in_context_capacity(run_dir, out)),
        ("fig6", lambda: fig6_premium_vs_recall(run_dir, out, niah_run)),
        ("fig7", lambda: fig7_cost_vs_latency(run_dir, out, latency_run)),
    ]:
        png, svg = fn()
        typer.echo(f"  ✓ {name}: {png.name}, {svg.name}")
    typer.echo(f"All 6 figures written to {out}")


@app.command()
def leaderboard(
    run_dir: str = typer.Option(..., "--run"),
    out: str = typer.Option("leaderboard.json", "--out"),
    baseline: str = typer.Option("openai/o200k_base", "--baseline"),
) -> None:
    """Emit leaderboard JSON from a study run."""
    from asia_fertility.report.leaderboard import write_leaderboard

    path = write_leaderboard(run_dir, out, baseline_tokenizer=baseline)
    typer.echo(f"✓ leaderboard written: {path}")


# ----------------------------- tokenizers --------------------------------- #


@tokenizers_app.command("list")
def tokenizers_list(
    available_only: bool = typer.Option(False, "--available-only"),
    json_out: bool = typer.Option(False, "--json"),
    family: str | None = typer.Option(None, "--family"),
) -> None:
    """List registered tokenizers + availability."""
    from asia_fertility.tokenizers import is_available, list_tokenizers

    rows = list_tokenizers(available_only=available_only)
    if family:
        rows = [r for r in rows if r.family == family]

    if json_out:
        import json as _json

        out = [
            {
                "id": r.id,
                "family": r.family,
                "backend": r.backend,
                "gated": r.gated,
                "extra": r.extra,
                "available": is_available(r.id),
                "notes": r.notes,
            }
            for r in rows
        ]
        typer.echo(_json.dumps(out, indent=2, ensure_ascii=False))
        return

    from rich.console import Console
    from rich.table import Table

    table = Table(title=f"Registered tokenizers ({len(rows)})", title_style="bold")
    table.add_column("ID", style="cyan")
    table.add_column("Family", style="magenta")
    table.add_column("Backend", style="yellow")
    table.add_column("Available", justify="center")
    table.add_column("Gated", justify="center")
    table.add_column("Extra")
    table.add_column("Notes", overflow="fold")

    for r in rows:
        avail = "[green]✓[/green]" if is_available(r.id) else "[red]✗[/red]"
        gated = "[yellow]🔒[/yellow]" if r.gated else ""
        table.add_row(r.id, r.family, r.backend, avail, gated, r.extra or "—", r.notes)

    Console().print(table)


# ----------------------------- corpora / languages ------------------------ #


@corpora_app.command("list")
def corpora_list() -> None:
    """List registered corpora."""
    from rich.console import Console
    from rich.table import Table

    from asia_fertility.corpora import list_corpora

    names = list_corpora()
    table = Table(title=f"Registered corpora ({len(names)})", title_style="bold")
    table.add_column("Name", style="cyan")
    for n in names:
        table.add_row(n)
    Console().print(table)


@languages_app.command("list")
def languages_list() -> None:
    """List study languages with ISO codes, scripts, families."""
    from rich.console import Console
    from rich.table import Table

    from asia_fertility.languages import load_languages

    langs = load_languages()
    table = Table(title=f"Study languages ({len(langs)})", title_style="bold")
    table.add_column("ISO", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Script")
    table.add_column("Family")
    table.add_column("FLORES tag", style="dim")
    table.add_column("Spaceless", justify="center")
    table.add_column("Notes", overflow="fold")
    for lg in langs:
        spaceless = "[yellow]✓[/yellow]" if lg.spaceless else ""
        table.add_row(lg.iso, lg.name, lg.script, lg.family, lg.flores_tag, spaceless, lg.notes)
    Console().print(table)


# ----------------------------- niah --------------------------------------- #


@niah_app.command("run")
def niah_run(
    config: str = typer.Option(..., "--config"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Run the multi-turn needle-in-haystack sweep."""
    import asyncio

    from asia_fertility.niah import NIAHConfig, estimate_cost_usd, run_niah

    cfg = NIAHConfig.from_yaml(config)
    cost = estimate_cost_usd(cfg)
    typer.echo(f"Total cells: {cfg.total_cells()}, models: {len(cfg.models)}")
    typer.echo(f"Estimated cost (gpt-4o-mini-equivalent): ~${cost:.2f}")
    if not yes and not typer.confirm("Proceed?"):
        raise typer.Exit(code=1)
    csv_path = asyncio.run(run_niah(cfg))
    typer.echo(f"✓ wrote {csv_path}")


@niah_app.command("report")
def niah_report(output_dir: str = typer.Option(..., "--output-dir")) -> None:
    """Print recall summary from an NIAH run."""
    import csv as _csv
    from collections import defaultdict
    from pathlib import Path

    from rich.console import Console
    from rich.table import Table

    csv_path = Path(output_dir) / "results.csv"
    by_cell: dict[tuple, list[bool]] = defaultdict(list)
    with csv_path.open("r", encoding="utf-8") as f:
        for row in _csv.DictReader(f):
            key = (row["model"], row["iso"], int(row["fill_tokens"]))
            by_cell[key].append(row["recalled"].lower() == "true")

    table = Table(title=f"NIAH recall · {csv_path}")
    table.add_column("Model", style="cyan")
    table.add_column("Lang")
    table.add_column("Fill")
    table.add_column("Recall", justify="right")
    for (model, iso, fill), hits in sorted(by_cell.items()):
        rate = sum(hits) / len(hits)
        table.add_row(model, iso, str(fill), f"{rate:.2f} ({sum(hits)}/{len(hits)})")
    Console().print(table)


# ----------------------------- latency ------------------------------------ #


@latency_app.command("run")
def latency_run(
    config: str = typer.Option(..., "--config"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Measure wall-clock latency penalty per (model × language) cell."""
    import asyncio

    from asia_fertility.latency import LatencyConfig, estimate_cost_usd, run_latency

    cfg = LatencyConfig.from_yaml(config)
    cost = estimate_cost_usd(cfg)
    typer.echo(
        f"Total calls: {cfg.total_calls()} "
        f"({cfg.n_warmup} warmup + {cfg.n_trials} trials per cell, "
        f"{len(cfg.models)} models × {len(cfg.languages)} langs)"
    )
    typer.echo(f"Estimated cost (gpt-4o-mini-equivalent): ~${cost:.4f}")
    if not yes and not typer.confirm("Proceed?"):
        raise typer.Exit(code=1)
    csv_path = asyncio.run(run_latency(cfg))
    typer.echo(f"✓ wrote {csv_path}")


@latency_app.command("report")
def latency_report_cmd(
    output_dir: str = typer.Option(..., "--output-dir"),
    baseline_lang: str = typer.Option("eng", "--baseline-lang"),
) -> None:
    """Print latency penalty (× English baseline) per (model × language)."""
    from rich.console import Console
    from rich.table import Table

    from asia_fertility.latency import latency_report

    out = latency_report(output_dir, baseline_lang=baseline_lang)
    summary = out["summary"]
    penalty = out["latency_penalty"]

    table = Table(title=f"Latency benchmark · {output_dir}/results.csv", title_style="bold")
    table.add_column("Model", style="cyan")
    table.add_column("Lang")
    table.add_column("n", justify="right")
    table.add_column("Errors", justify="right")
    table.add_column("Mean total ms", justify="right")
    table.add_column("95% CI ms", justify="right")
    table.add_column("Mean TTFT ms", justify="right")
    table.add_column(f"× {baseline_lang}", justify="right", style="bold")

    rows = sorted(summary.items(), key=lambda kv: kv[0])
    for key, row in rows:
        model, iso = key.split("|", 1)
        p = penalty.get(key)
        table.add_row(
            model,
            iso,
            str(row["n"]),
            str(row["errors"]),
            f"{row['total_ms_mean']:.0f}",
            f"[{row['total_ms_ci_low']:.0f}, {row['total_ms_ci_high']:.0f}]",
            f"{row['ttft_ms_mean']:.0f}",
            f"{p:.2f}×" if p else "—",
        )
    Console().print(table)


if __name__ == "__main__":
    app()
