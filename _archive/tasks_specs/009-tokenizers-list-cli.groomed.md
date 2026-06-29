# `fertiscope tokenizers list` CLI command

Status: pending
Tags: `cli`, `tokenizers`, `rich`, `ux`
Depends on: #003, #005, #006, #007, #008
Blocks: None (UX-only; doesn't gate measurement paths)

## Scope

Replace the `NotImplementedError` stub in `tokenizers list` with a real implementation that prints a Rich table of all registered tokenizers, their backend, family, availability, gating, and the extras required to load them. Supports `--available-only` and `--json` flags.

### Files to modify

- `src/fertiscope/cli.py` — replace the `tokenizers_list` stub body.

### Files to create

- `tests/unit/test_cli_tokenizers_list.py`

### Interface and contract

In `cli.py`, replace:

```python
@tokenizers_app.command("list")
def tokenizers_list(available_only: bool = ..., json_out: bool = ...) -> None:
    _not_implemented("009")
```

with:

```python
@tokenizers_app.command("list")
def tokenizers_list(
    available_only: bool = typer.Option(False, "--available-only", help="Only show tokenizers that can load successfully."),
    json_out: bool = typer.Option(False, "--json", help="Emit machine-readable JSON instead of a table."),
    family: str | None = typer.Option(None, "--family", help="Filter by family (openai, meta, google, ...)"),
) -> None:
    """List registered tokenizers and availability."""
    from fertiscope.tokenizers import list_tokenizers, is_available

    rows = list_tokenizers(available_only=available_only)
    if family:
        rows = [r for r in rows if r.family == family]

    if json_out:
        import json
        out = [{
            "id": r.id,
            "family": r.family,
            "backend": r.backend,
            "gated": r.gated,
            "extra": r.extra,
            "available": is_available(r.id),
            "notes": r.notes,
        } for r in rows]
        typer.echo(json.dumps(out, indent=2, ensure_ascii=False))
        return

    from rich.console import Console
    from rich.table import Table

    table = Table(title=f"Registered tokenizers ({len(rows)})", title_style="bold")
    table.add_column("ID",        style="cyan")
    table.add_column("Family",    style="magenta")
    table.add_column("Backend",   style="yellow")
    table.add_column("Available", justify="center")
    table.add_column("Gated",     justify="center")
    table.add_column("Extra")
    table.add_column("Notes", overflow="fold")

    for r in rows:
        avail = "[green]✓[/green]" if is_available(r.id) else "[red]✗[/red]"
        gated = "[yellow]🔒[/yellow]" if r.gated else ""
        table.add_row(r.id, r.family, r.backend, avail, gated, r.extra or "—", r.notes)

    Console().print(table)
```

`tests/unit/test_cli_tokenizers_list.py`:

```python
import json
from typer.testing import CliRunner
from fertiscope.cli import app

runner = CliRunner()

def test_list_default():
    result = runner.invoke(app, ["tokenizers", "list"])
    assert result.exit_code == 0
    assert "openai/o200k_base" in result.stdout
    assert "anthropic/claude" in result.stdout

def test_list_json():
    result = runner.invoke(app, ["tokenizers", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    ids = {row["id"] for row in data}
    assert {"openai/o200k_base", "openai/cl100k_base", "meta/llama-3.1", "google/gemma-4", "anthropic/claude", "google/gemini"} <= ids
    assert all({"id", "family", "backend", "gated", "extra", "available", "notes"} <= row.keys() for row in data)

def test_list_filter_family():
    result = runner.invoke(app, ["tokenizers", "list", "--family", "openai", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert all(row["family"] == "openai" for row in data)
    assert len(data) >= 3   # cl100k, o200k, o200k_harmony

def test_list_available_only_with_extras():
    # If tiktoken is installed (it is in CI dev), at minimum openai rows should appear
    result = runner.invoke(app, ["tokenizers", "list", "--available-only", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert all(row["available"] for row in data)
```

### Notes

- The Rich table uses `✓` / `✗` / `🔒` emoji glyphs. Test environments that don't render Unicode well will still pass JSON-mode tests.
- `--family` filtering is a UX nice-to-have, but it's also useful for `fertiscope tokenizers list --family meta --json | jq` patterns.
- Row count in title (`Registered tokenizers (13)`) gives immediate orientation.
- Don't sort by `id` only — the registry already sorts by `(family, id)` so OpenAI's three encodings cluster together.
- Document the `--json` schema in `docs/usage.md` (#037).

## Acceptance Criteria

- [ ] `fertiscope tokenizers list` exits 0 and prints a Rich table.
- [ ] Table contains at least these IDs: `openai/o200k_base`, `openai/cl100k_base`, `openai/o200k_harmony`, `meta/llama-3.1`, `google/gemma-4`, `mistral/tekken`, `qwen/qwen3`, `bigscience/bloom`, `cohere/aya-expanse`, `anthropic/claude`, `google/gemini` (≥ 11 rows total).
- [ ] `fertiscope tokenizers list --json` outputs valid JSON parsable by `json.loads`.
- [ ] Each JSON row has keys: `id`, `family`, `backend`, `gated`, `extra`, `available`, `notes`.
- [ ] `fertiscope tokenizers list --available-only` filters out rows where `is_available()` is False.
- [ ] `fertiscope tokenizers list --family meta --json` returns only `family == "meta"` rows.
- [ ] All 4 CLI tests pass.
- [ ] No real network call during the `list` command.

## User Stories

### Story: Developer surveys available tokenizers

1. Runs `fertiscope tokenizers list`.
2. Sees a Rich table: 11 rows, 3 available locally, 8 marked unavailable with extras hints.
3. Runs `pip install fertiscope[hf,api]`, retries → more rows green.

### Story: CI script consumes the registry

1. CI runs `fertiscope tokenizers list --available-only --json > available.json`.
2. Downstream script reads `available.json` and decides which study config to run.

### Story: Filtering by family

1. User wants only OpenAI rows: `fertiscope tokenizers list --family openai`.
2. Sees 3 rows: o200k_base, o200k_harmony, cl100k_base.
3. Clean, focused view.

---

Blocked by: #003, #005, #006, #007, #008
