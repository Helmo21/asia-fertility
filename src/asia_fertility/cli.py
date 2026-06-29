"""asia-fertility CLI entry point. Subcommand bodies are implemented in later tasks."""

from __future__ import annotations

import typer
from rich import print as rprint

from asia_fertility import __version__

app = typer.Typer(
    name="asia-fertility",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
    help="Tokenizer fertility, cost, and multi-turn context-budget analyzer.",
)

tokenizers_app = typer.Typer(help="Tokenizer registry commands.")
corpora_app = typer.Typer(help="Corpus registry commands.")
languages_app = typer.Typer(help="Language registry commands.")
niah_app = typer.Typer(help="Multi-turn needle-in-haystack benchmark commands.")

app.add_typer(tokenizers_app, name="tokenizers")
app.add_typer(corpora_app, name="corpora")
app.add_typer(languages_app, name="languages")
app.add_typer(niah_app, name="niah")


def _not_implemented(task_id: str) -> None:
    raise typer.Exit(code=2) from NotImplementedError(f"Implemented in task #{task_id}")


@app.callback(invoke_without_command=True)
def _root(version: bool = typer.Option(False, "--version", "-V")) -> None:
    if version:
        rprint(f"asia-fertility {__version__}")
        raise typer.Exit()


@app.command()
def measure(
    text: str | None = typer.Option(None, "--text"),
    corpus: str | None = typer.Option(None, "--corpus"),
    path: str | None = typer.Option(None, "--path"),
    lang: str = typer.Option("eng", "--lang"),
    tokenizer: str = typer.Option("openai/o200k_base", "--tokenizer"),
    baseline_lang: str = typer.Option("eng", "--baseline-lang"),
    n_resamples: int = typer.Option(1000, "--n-resamples"),
    rng_seed: int = typer.Option(42, "--rng-seed"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Token count, fertility, premium, CPT, BPT for input text. (#019)"""
    _not_implemented("019")


@app.command()
def cost(
    text: str = typer.Option(..., "--text"),
    lang: str = typer.Option(..., "--lang"),
    models: str = typer.Option("openai/gpt-4o", "--models"),
    currencies: str = typer.Option("USD", "--currencies"),
    output_tokens_est: int = typer.Option(200, "--output-tokens-est"),
    prices_path: str | None = typer.Option(None, "--prices"),
    fx_path: str | None = typer.Option(None, "--fx"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Cost per model per language. (#022)"""
    _not_implemented("022")


@app.command()
def run(
    config: str = typer.Option(..., "--config"),
    output_dir: str | None = typer.Option(None, "--output-dir"),
    hf_token: str | None = typer.Option(None, "--hf-token", envvar="HF_TOKEN"),
) -> None:
    """Full study from YAML config. (#026)"""
    _not_implemented("026")


@app.command()
def reproduce(output_dir: str = typer.Option("runs/reproduce", "--output-dir")) -> None:
    """Offline reference suite — one-command credibility demo. (#026)"""
    _not_implemented("026")


@app.command()
def figures(
    run_dir: str = typer.Option(..., "--run"),
    out_dir: str = typer.Option(..., "--out"),
    niah_run: str | None = typer.Option(None, "--niah-run"),
) -> None:
    """Regenerate figures from a study run. (#031, #032)"""
    _not_implemented("031")


@app.command()
def leaderboard(
    run_dir: str = typer.Option(..., "--run"),
    out: str = typer.Option("leaderboard.json", "--out"),
    baseline: str = typer.Option("openai/o200k_base", "--baseline"),
) -> None:
    """Emit leaderboard JSON from a study run. (#033)"""
    _not_implemented("033")


@tokenizers_app.command("list")
def tokenizers_list(
    available_only: bool = typer.Option(False, "--available-only"),
    json_out: bool = typer.Option(False, "--json"),
    family: str | None = typer.Option(None, "--family"),
) -> None:
    """List registered tokenizers and availability. (#009)"""
    _not_implemented("009")


@corpora_app.command("list")
def corpora_list() -> None:
    """List registered corpora. (#010)"""
    _not_implemented("010")


@languages_app.command("list")
def languages_list() -> None:
    """List study languages with ISO codes, scripts, families. (#011)"""
    _not_implemented("011")


@niah_app.command("run")
def niah_run(
    config: str = typer.Option(..., "--config"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Run the multi-turn NIAH sweep. (#030)"""
    _not_implemented("030")


@niah_app.command("resume")
def niah_resume(
    output_dir: str = typer.Option(..., "--output-dir"),
    config: str = typer.Option(..., "--config"),
) -> None:
    """Resume an interrupted NIAH sweep. (#030)"""
    _not_implemented("030")


@niah_app.command("report")
def niah_report(output_dir: str = typer.Option(..., "--output-dir")) -> None:
    """Print recall heatmap from an NIAH run. (#030)"""
    _not_implemented("030")


if __name__ == "__main__":
    app()
