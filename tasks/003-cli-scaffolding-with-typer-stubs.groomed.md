# CLI scaffolding with typer stubs

Status: pending
Tags: `cli`, `typer`, `stubs`
Depends on: #002
Blocks: #004, #009, #011, #019, #022, #026, #030, #033

## Scope

Wire `fertiscope` as a typer app with every future subcommand pre-declared but raising `NotImplementedError` referencing the task that will implement it. After this task, `fertiscope --help` lists the full surface area and each subcommand fails loud and obvious. No measurement logic yet.

### Files to create

- `src/fertiscope/cli.py`
- `tests/unit/test_cli_smoke.py`

### Files to modify

- None.

### Interface and contract

`src/fertiscope/cli.py`:

```python
"""FertiScope CLI entry point. Subcommand bodies are implemented in later tasks."""
from __future__ import annotations

import typer
from rich import print

from fertiscope import __version__

app = typer.Typer(
    name="fertiscope",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
    help="Tokenizer fertility, cost, and multi-turn context-budget analyzer.",
)

tokenizers_app = typer.Typer(help="Tokenizer registry commands.")
corpora_app   = typer.Typer(help="Corpus registry commands.")
languages_app = typer.Typer(help="Language registry commands.")
niah_app      = typer.Typer(help="Multi-turn needle-in-haystack benchmark commands.")

app.add_typer(tokenizers_app, name="tokenizers")
app.add_typer(corpora_app,    name="corpora")
app.add_typer(languages_app,  name="languages")
app.add_typer(niah_app,       name="niah")


def _not_implemented(task_id: str) -> None:
    raise typer.Exit(code=2) from NotImplementedError(f"Implemented in task #{task_id}")


@app.callback(invoke_without_command=True)
def _root(version: bool = typer.Option(False, "--version", "-V")) -> None:
    if version:
        print(f"fertiscope {__version__}")
        raise typer.Exit()


@app.command()
def measure(text: str = typer.Option(..., "--text"),
            lang: str = typer.Option("eng", "--lang"),
            tokenizer: str = typer.Option("openai/o200k_base", "--tokenizer")) -> None:
    """Token count, fertility, premium, CPT, BPT for input text. (#019)"""
    _not_implemented("019")


@app.command()
def cost(text: str = typer.Option(..., "--text"),
         lang: str = typer.Option(..., "--lang"),
         models: str = typer.Option("openai/gpt-4o", "--models"),
         currencies: str = typer.Option("USD", "--currencies")) -> None:
    """Cost per model per language. (#022)"""
    _not_implemented("022")


@app.command()
def run(config: str = typer.Option(..., "--config")) -> None:
    """Full study from YAML config. (#026)"""
    _not_implemented("026")


@app.command()
def reproduce() -> None:
    """Offline reference suite — one-command credibility demo. (#026)"""
    _not_implemented("026")


@app.command()
def figures(run_dir: str = typer.Option(..., "--run"),
            out_dir: str = typer.Option(..., "--out"),
            niah_run: str | None = typer.Option(None, "--niah-run")) -> None:
    """Regenerate figures from a study run. (#031, #032)"""
    _not_implemented("031")


@app.command()
def leaderboard(run_dir: str = typer.Option(..., "--run"),
                out: str = typer.Option("leaderboard.json", "--out")) -> None:
    """Emit leaderboard JSON from a study run. (#033)"""
    _not_implemented("033")


@tokenizers_app.command("list")
def tokenizers_list(available_only: bool = typer.Option(False, "--available-only"),
                    json_out: bool = typer.Option(False, "--json")) -> None:
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
def niah_run(config: str = typer.Option(..., "--config"),
             yes: bool = typer.Option(False, "--yes", "-y")) -> None:
    """Run the multi-turn NIAH sweep. (#030)"""
    _not_implemented("030")


@niah_app.command("resume")
def niah_resume(output_dir: str = typer.Option(..., "--output-dir")) -> None:
    """Resume an interrupted NIAH sweep. (#030)"""
    _not_implemented("030")


@niah_app.command("report")
def niah_report(output_dir: str = typer.Option(..., "--output-dir")) -> None:
    """Print recall heatmap from an NIAH run. (#030)"""
    _not_implemented("030")


if __name__ == "__main__":
    app()
```

`tests/unit/test_cli_smoke.py`:

- Uses `typer.testing.CliRunner`.
- Asserts `fertiscope --version` prints `fertiscope 0.2.0` and exits 0.
- Asserts `fertiscope --help` exits 0 and mentions every subcommand by name (`measure`, `cost`, `run`, `reproduce`, `figures`, `leaderboard`, `tokenizers`, `corpora`, `languages`, `niah`).
- Asserts `fertiscope measure --text x` exits with code 2 and the `NotImplementedError` chain mentions `#019`.

### Notes

- The `_not_implemented` helper uses `raise … from NotImplementedError(...)` so the user sees the task-ID hint in the exception chain without typer pretty-printing it as an unhandled crash.
- `pretty_exceptions_show_locals=False` keeps tracebacks tight.
- Sub-typer-apps (`tokenizers`, `corpora`, `languages`, `niah`) use the noun-verb pattern. Single-noun-level commands (`measure`, `cost`, `run`, `reproduce`, `figures`, `leaderboard`) stay flat for ergonomics.
- DO NOT shell-execute anything in this task. CLI bodies just raise.

## Acceptance Criteria

- [ ] `uv run fertiscope --help` exits 0 and lists 10 visible subcommands or sub-typers.
- [ ] `uv run fertiscope --version` prints `fertiscope 0.2.0`.
- [ ] `uv run fertiscope measure --text x` exits with code 2, traceback mentions `task #019`.
- [ ] `uv run fertiscope tokenizers list` exits with code 2, traceback mentions `task #009`.
- [ ] `uv run fertiscope niah run --config foo` exits with code 2, mentions `task #030`.
- [ ] `tests/unit/test_cli_smoke.py` passes (≥ 4 assertions).
- [ ] `uv run ruff check src/fertiscope/cli.py` is clean.
- [ ] `uv run mypy src/fertiscope/cli.py` is clean.
- [ ] No subcommand body has more than 1 line of logic (`_not_implemented("NNN")`).

## User Stories

### Story: New contributor maps the surface

1. Clones the repo, runs `fertiscope --help`.
2. Sees the full command tree.
3. Knows which tasks to implement to fill which command without reading the roadmap.

### Story: Failing fast

1. User runs `fertiscope measure --text "hello"` against current main.
2. Gets a clear error: "Implemented in task #019".
3. Knows exactly where to look.

---

Blocked by: #002
