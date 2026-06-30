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
models_app = typer.Typer(
    help="Canonical model registry (pricing + tokenizer + benchmark coverage)."
)
niah_app = typer.Typer(help="Multi-turn needle-in-haystack benchmark commands.")
latency_app = typer.Typer(help="Wall-clock latency benchmark commands.")

app.add_typer(tokenizers_app, name="tokenizers")
app.add_typer(corpora_app, name="corpora")
app.add_typer(languages_app, name="languages")
app.add_typer(models_app, name="models")
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
    from asia_fertility.cost.prices import ModelNotInPrices, load_prices

    model_list = [m.strip() for m in models.split(",") if m.strip()]
    cur_list = [c.strip() for c in currencies.split(",") if c.strip()]
    try:
        rows = cost_of(
            text,
            models=model_list,
            output_tokens_est=output_tokens_est,
            currencies=cur_list,
            prices_path=prices_path,
            fx_path=fx_path,
        )
    except ModelNotInPrices as e:
        from asia_fertility.registry import load_registry

        # Pull the failing id out of the error message (everything in quotes)
        msg = str(e)
        bad_id = msg.split("'")[1] if "'" in msg else ""
        suggestions = load_registry().suggest(bad_id, n=3) if bad_id else []
        known = sorted(load_prices(prices_path).models.keys())
        out = [str(e)]
        if suggestions:
            out.append(f"\nDid you mean: {', '.join(suggestions)} ?")
        out.append(f"\nBundled prices cover {len(known)} model IDs:")
        out.append("  " + "\n  ".join(known))
        out.append("\nPass --prices PATH to supply a custom YAML for other models.")
        typer.echo("\n".join(out), err=True)
        raise typer.Exit(code=2) from None

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
    typer.echo(
        "`reproduce` is reserved for the bundled reference suite (not yet shipped in 0.4.0)."
    )
    typer.echo("For a small smoke study use:")
    typer.echo("  asia-fertility run --config configs/study_test.yaml")
    typer.echo("For the full leaderboard use:")
    typer.echo("  asia-fertility run --config configs/study_main.yaml")
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
        fig6b_recall_heatmap,
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
        ("fig6b", lambda: fig6b_recall_heatmap(run_dir, out, niah_run)),
        ("fig7", lambda: fig7_cost_vs_latency(run_dir, out, latency_run)),
    ]:
        png, svg = fn()
        typer.echo(f"  ✓ {name}: {png.name}, {svg.name}")
    typer.echo(f"All figures written to {out}")


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


# ----------------------------- models ------------------------------------- #


@models_app.command("list")
def models_list(
    benchmarked_only: bool = typer.Option(
        False, "--benchmarked-only", help="Only show models with non-empty benchmarked_in."
    ),
    family: str | None = typer.Option(None, "--family", help="Filter by vendor family."),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """List entries from the canonical model registry (models_<snapshot>.yaml)."""
    from asia_fertility.registry import load_registry

    reg = load_registry()
    rows = reg.all(include_aliases=False)
    if benchmarked_only:
        rows = [r for r in rows if r.benchmarked_in]
    if family:
        rows = [r for r in rows if r.family == family]

    if json_out:
        import json as _json

        payload = {
            "schema_version": reg.schema_version,
            "snapshot_date": str(reg.snapshot_date),
            "models": [
                {
                    "id": r.id,
                    "family": r.family,
                    "pricing": {"input": r.input_price_per_1m, "output": r.output_price_per_1m},
                    "context_window": r.context_window,
                    "sizing_tokenizer": r.sizing_tokenizer,
                    "native_tokenizer": r.native_tokenizer,
                    "benchmarked_in": list(r.benchmarked_in),
                }
                for r in rows
            ],
        }
        typer.echo(_json.dumps(payload, indent=2, ensure_ascii=False))
        return

    from rich.console import Console
    from rich.table import Table

    table = Table(
        title=f"Model registry · snapshot {reg.snapshot_date} · {len(rows)} entries",
        title_style="bold",
    )
    table.add_column("Model ID", style="cyan")
    table.add_column("Family", style="dim")
    table.add_column("In $/1M", justify="right")
    table.add_column("Out $/1M", justify="right")
    table.add_column("Window", justify="right")
    table.add_column("Sizing tok", overflow="fold")
    table.add_column("Benchmarked", overflow="fold")
    for r in rows:
        bench = ",".join(r.benchmarked_in) if r.benchmarked_in else "[dim]—[/dim]"
        table.add_row(
            r.id,
            r.family,
            f"${r.input_price_per_1m:.2f}",
            f"${r.output_price_per_1m:.2f}",
            f"{r.context_window:,}",
            r.sizing_tokenizer,
            bench,
        )
    Console().print(table)


@models_app.command("show")
def models_show(model_id: str = typer.Argument(..., help="Model ID to look up.")) -> None:
    """Show full registry detail for one model, resolving aliases."""
    from asia_fertility.registry import load_registry

    reg = load_registry()
    if not reg.has(model_id):
        suggestions = reg.suggest(model_id, n=3)
        msg = f"Unknown model '{model_id}'."
        if suggestions:
            msg += f"\nDid you mean: {', '.join(suggestions)} ?"
        typer.echo(msg, err=True)
        raise typer.Exit(code=2)
    raw = reg.models[model_id]
    rec = reg.get(model_id)  # resolves alias
    from rich.console import Console
    from rich.table import Table

    note = ""
    if raw.alias_of:
        note = f"[dim](alias of {raw.alias_of})[/dim]"
    table = Table(title=f"Model · {model_id} {note}", title_style="bold")
    table.add_column("Field")
    table.add_column("Value", overflow="fold")
    table.add_row("Family", rec.family)
    table.add_row("Input price / 1M tokens", f"${rec.input_price_per_1m:.4f} {reg.currency}")
    table.add_row("Output price / 1M tokens", f"${rec.output_price_per_1m:.4f} {reg.currency}")
    table.add_row("Context window", f"{rec.context_window:,} tokens")
    table.add_row("Sizing tokenizer", rec.sizing_tokenizer)
    table.add_row("Native tokenizer", rec.native_tokenizer)
    table.add_row("OpenRouter route", rec.openrouter_route or "[dim]—[/dim]")
    table.add_row("Native API route", rec.native_route or "[dim]—[/dim]")
    table.add_row(
        "Benchmarked in", ", ".join(rec.benchmarked_in) if rec.benchmarked_in else "[dim]—[/dim]"
    )
    if rec.notes:
        table.add_row("Notes", rec.notes)
    Console().print(table)


# ----------------------------- niah --------------------------------------- #


@niah_app.command("run")
def niah_run(
    config: str = typer.Option(..., "--config"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Run the multi-turn needle-in-haystack sweep."""
    import asyncio
    import os

    from asia_fertility.niah import NIAHConfig, estimate_cost_usd, run_niah

    if not os.environ.get("OPENROUTER_API_KEY"):
        typer.echo(
            "OPENROUTER_API_KEY not set. Source your .env first:\n"
            "  source ~/Documents/WORK/CODE/LABS/fertiscope/.env\n"
            "or export the key in your current shell.",
            err=True,
        )
        raise typer.Exit(code=2)

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
    """Print recall summary and write niah_report.json from an NIAH run."""
    import csv as _csv
    import json as _json
    from collections import defaultdict
    from pathlib import Path

    from rich.console import Console
    from rich.table import Table

    csv_path = Path(output_dir) / "results.csv"
    by_cell: dict[tuple, list[bool]] = defaultdict(list)
    by_cell_err: dict[tuple, int] = defaultdict(int)
    by_model: dict[str, list[bool]] = defaultdict(list)
    by_model_lang: dict[tuple, list[bool]] = defaultdict(list)
    by_model_fill: dict[tuple, list[bool]] = defaultdict(list)

    with csv_path.open("r", encoding="utf-8") as f:
        for row in _csv.DictReader(f):
            # Defensive: skip rows whose CSV-parsing produced a non-conforming key
            try:
                model = row["model"]
                iso = row["iso"]
                fill = int(row["fill_tokens"])
            except (KeyError, ValueError, TypeError):
                continue
            hit = row["recalled"].lower() == "true"
            err = bool(row.get("error", "").strip())
            key = (model, iso, fill)
            by_cell[key].append(hit)
            if err:
                by_cell_err[key] += 1
            by_model[model].append(hit)
            by_model_lang[(model, iso)].append(hit)
            by_model_fill[(model, fill)].append(hit)

    # Per (model, iso, fill) detailed cells
    cells = []
    for (model, iso, fill), hits in sorted(by_cell.items()):
        cells.append(
            {
                "model": model,
                "iso": iso,
                "fill_tokens": fill,
                "n": len(hits),
                "recalled": sum(hits),
                "recall_rate": round(sum(hits) / len(hits), 4) if hits else None,
                "errors": by_cell_err.get((model, iso, fill), 0),
            }
        )

    # Per-model aggregates
    per_model = []
    for model in sorted(by_model):
        hits = by_model[model]
        per_model.append(
            {
                "model": model,
                "n": len(hits),
                "recalled": sum(hits),
                "recall_rate": round(sum(hits) / len(hits), 4) if hits else None,
            }
        )

    # Per (model, fill) for the heatmap
    per_model_fill = []
    for (model, fill), hits in sorted(by_model_fill.items()):
        per_model_fill.append(
            {
                "model": model,
                "fill_tokens": fill,
                "n": len(hits),
                "recalled": sum(hits),
                "recall_rate": round(sum(hits) / len(hits), 4) if hits else None,
            }
        )

    report = {
        "source_csv": str(csv_path),
        "n_cells": sum(len(v) for v in by_cell.values()),
        "n_models": len(by_model),
        "n_langs": len({k[1] for k in by_cell}),
        "n_fills": len({k[2] for k in by_cell}),
        "overall_recall_rate": round(
            sum(sum(v) for v in by_cell.values()) / max(1, sum(len(v) for v in by_cell.values())),
            4,
        ),
        "per_model": per_model,
        "per_model_fill": per_model_fill,
        "cells": cells,
    }

    json_path = Path(output_dir) / "niah_report.json"
    json_path.write_text(_json.dumps(report, indent=2), encoding="utf-8")

    table = Table(title=f"NIAH recall · {csv_path}")
    table.add_column("Model", style="cyan")
    table.add_column("Lang")
    table.add_column("Fill")
    table.add_column("Recall", justify="right")
    for (model, iso, fill), hits in sorted(by_cell.items()):
        rate = sum(hits) / len(hits)
        table.add_row(model, iso, str(fill), f"{rate:.2f} ({sum(hits)}/{len(hits)})")
    Console().print(table)
    Console().print(f"\n[bold]Wrote[/bold] {json_path}")


@niah_app.command("lookup")
def niah_lookup(
    lang: str = typer.Option(..., "--lang", help="Language ISO code (e.g. tam, mya)."),
    context: int = typer.Option(
        ..., "--context", help="Context window in tokens (4096/16384/32768/65536/131072)."
    ),
    model: str | None = typer.Option(
        None, "--model", help="Filter to one model (substring match on the OpenRouter id)."
    ),
    with_cost: bool = typer.Option(
        False,
        "--with-cost",
        help="Join with the model registry to add per-1M input + output prices.",
    ),
) -> None:
    """Query the bundled NIAH recall table for a (lang × context) deployment decision.

    Uses the v0.3 dataset (16 langs × 5 models × 5 fills × 5 positions × 2 trials)
    shipped under asia_fertility/_defaults/niah_recall_*.json. The lookup picks the
    nearest fill_target ≤ context and returns recall_rate per model so you can
    pick a vendor based on script-native retrieval at the depth you actually use.
    With --with-cost, joins to the model registry to add pricing.
    """
    import json as _json
    from importlib.resources import files

    from rich.console import Console
    from rich.table import Table

    data = _json.loads(
        files("asia_fertility._defaults")
        .joinpath("niah_recall_2026-06.json")
        .read_text(encoding="utf-8")
    )
    fills = sorted(data["fills_tested"])
    nearest = max((f for f in fills if f <= context), default=fills[0])
    rows = [
        c
        for c in data["cells"]
        if c["iso"] == lang
        and c["fill_tokens"] == nearest
        and (model is None or model in c["model"])
    ]
    if not rows:
        typer.echo(
            f"No data for lang={lang}, context≈{nearest} tokens. "
            f"Available langs: {', '.join(data['languages'])}.",
            err=True,
        )
        raise typer.Exit(code=1)
    rows.sort(key=lambda r: -(r["recall_rate"] or 0))

    reg = None
    if with_cost:
        from asia_fertility.registry import load_registry

        reg = load_registry()

    title = (
        f"NIAH recall · lang={lang} · context≤{context} "
        f"(nearest fill = {nearest})  ·  source: {data['version']}"
    )
    table = Table(title=title)
    table.add_column("Model", style="cyan")
    table.add_column("Recall", justify="right")
    table.add_column("n", justify="right")
    table.add_column("Errors", justify="right")
    if with_cost:
        table.add_column("In $/1M", justify="right")
        table.add_column("Out $/1M", justify="right")
        table.add_column("Approx cost (this prompt)", justify="right")
    for r in rows:
        recall = r["recall_rate"]
        cell = f"{recall:.0%} ({r['recalled']}/10)" if recall is not None else "—"
        line = [r["model"], cell, "10", str(r["errors"])]
        if with_cost and reg is not None:
            try:
                rec = reg.get(r["model"])
                in_p = f"${rec.input_price_per_1m:.2f}"
                out_p = f"${rec.output_price_per_1m:.2f}"
                # Approximate cost of one prompt at this fill (input only) + 100 tokens output
                input_cost = nearest * rec.input_price_per_1m / 1_000_000
                output_cost = 100 * rec.output_price_per_1m / 1_000_000
                approx = f"${input_cost + output_cost:.6f}"
            except KeyError:
                in_p = out_p = approx = "[dim]—[/dim]"
            line += [in_p, out_p, approx]
        table.add_row(*line)
    Console().print(table)
    if with_cost:
        Console().print(
            f"  [dim]Approx cost = {nearest:,} input tokens × in-price + "
            f"100 output tokens × out-price, per the model registry.[/dim]"
        )


# ----------------------------- latency ------------------------------------ #


@latency_app.command("run")
def latency_run(
    config: str = typer.Option(..., "--config"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Measure wall-clock latency penalty per (model × language) cell."""
    import asyncio
    import os

    from asia_fertility.latency import LatencyConfig, estimate_cost_usd, run_latency

    if not os.environ.get("OPENROUTER_API_KEY"):
        typer.echo(
            "OPENROUTER_API_KEY not set. Source your .env first:\n"
            "  source ~/Documents/WORK/CODE/LABS/fertiscope/.env\n"
            "or export the key in your current shell.",
            err=True,
        )
        raise typer.Exit(code=2)

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
