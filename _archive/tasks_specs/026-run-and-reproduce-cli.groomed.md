# `fertiscope run` and `fertiscope reproduce` CLI

Status: pending
Tags: `cli`, `study`, `reproduce`, `offline-demo`
Depends on: #003, #023, #024, #025
Blocks: None

## Scope

Wire the study runner to the CLI. `fertiscope run --config X.yaml` runs an arbitrary study and writes all artifacts; `fertiscope reproduce` runs `configs/study_reproduce.yaml` with extra UX polish (Rich progress, success summary, < 30s offline).

### Files to modify

- `src/fertiscope/cli.py` — replace `run` and `reproduce` stub bodies.

### Files to create

- `tests/unit/test_cli_run.py`
- `tests/unit/test_cli_reproduce.py`

### Interface and contract

`cli.py` — replace `run`:

```python
@app.command()
def run(
    config: str = typer.Option(..., "--config", help="Path to study YAML"),
    output_dir: str | None = typer.Option(None, "--output-dir"),
    hf_token: str | None = typer.Option(None, "--hf-token", envvar="HF_TOKEN"),
) -> None:
    """Full study from YAML config."""
    import os
    from pathlib import Path
    from fertiscope.config import StudyConfig
    from fertiscope.study.runner import run_study
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

    if hf_token:
        os.environ["HF_TOKEN"] = hf_token

    console = Console()
    cfg = StudyConfig.from_yaml(config)
    console.print(f"[bold]Loading study:[/bold] {cfg.name}")
    console.print(f"  languages: {len(cfg.languages)}, tokenizers: {len(cfg.tokenizers)}, corpora: {len(cfg.corpora)}")
    expected_rows = len(cfg.languages) * len(cfg.tokenizers) * len(cfg.corpora)
    console.print(f"  expected rows: {expected_rows}")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  BarColumn(), TaskProgressColumn(), console=console) as progress:
        task = progress.add_task("Measuring", total=expected_rows)
        # NOTE: runner currently doesn't emit per-row callbacks; we attach a progress hook
        # via a logging handler. For v0.2, just count after finish.
        result = run_study(cfg)
        progress.update(task, completed=expected_rows)

    out = result.write_all(Path(output_dir) if output_dir else None)
    skip_count = sum(1 for r in result.rows if r.skip_reason)
    console.print(f"[bold green]✓[/bold green] Wrote {len(result.rows)} rows ({skip_count} skipped) to {out}")
    console.print(f"  results.csv, results.json, results.parquet, leaderboard.json, manifest.json")
    console.print(f"  Manifest SHA: {result.manifest['config_sha256'][:12]}...")
```

`cli.py` — replace `reproduce`:

```python
@app.command()
def reproduce(
    output_dir: str = typer.Option("runs/reproduce", "--output-dir"),
) -> None:
    """Offline reference suite — one-command credibility demo."""
    from importlib.resources import files
    from pathlib import Path
    from fertiscope.config import StudyConfig
    from fertiscope.study.runner import run_study
    from rich.console import Console
    from rich.table import Table

    console = Console()
    console.print("[bold]FertiScope reproduce — offline credibility demo[/bold]")
    console.print("  7 languages × 3 tiktoken tokenizers × 10 bundled FLORES sentences")
    console.print("  No network, no API keys.\n")

    # Load the bundled study YAML
    cfg_yaml_path = files("fertiscope._defaults").joinpath("study_reproduce.yaml")
    cfg = StudyConfig.model_validate_json(__import__("json").dumps(
        __import__("yaml").safe_load(cfg_yaml_path.read_text("utf-8"))
    ))
    # Or simpler: cfg = StudyConfig.from_yaml(str(cfg_yaml_path)) once #023 includes
    # a bundled copy at _defaults/study_reproduce.yaml.

    import time
    t0 = time.time()
    result = run_study(cfg)
    elapsed = time.time() - t0
    out = result.write_all(Path(output_dir))

    # Show a summary table — the "credibility demo" output
    table = Table(title=f"FertiScope reproduce · {elapsed:.1f}s · {len(result.rows)} rows", title_style="bold")
    table.add_column("Lang", style="cyan")
    table.add_column("Tokenizer", style="dim")
    table.add_column("Fertility", justify="right")
    table.add_column("Premium",   justify="right")
    table.add_column("BPT",       justify="right")
    for r in result.rows:
        if r.skip_reason:
            continue
        fert = f"{r.fertility:.2f}"
        prem = "—" if r.iso == cfg.baseline_language else f"{r.premium:.2f}×"
        bpt  = f"{r.bpt:.2f}"
        table.add_row(r.iso, r.tokenizer, fert, prem, bpt)
    Console().print(table)

    console.print(f"\n[bold green]✓[/bold green] Output written to {out}")
    console.print(f"  Manifest SHA: {result.manifest['config_sha256'][:12]}...")
    if elapsed > 30:
        console.print(f"[yellow]⚠ Reproduce ran in {elapsed:.1f}s (target: < 30s)[/yellow]")
```

> Note: The `study_reproduce.yaml` must be ALSO bundled inside `src/fertiscope/_defaults/study_reproduce.yaml` so a pip-installed user can run `fertiscope reproduce` without checking out the repo. Add this in #023 or copy it here.

`tests/unit/test_cli_run.py`:

```python
from pathlib import Path
from typer.testing import CliRunner
from fertiscope.cli import app

def test_run_with_test_config(tmp_path):
    cfg_path = Path("configs/study_test.yaml")
    r = CliRunner().invoke(app, ["run", "--config", str(cfg_path), "--output-dir", str(tmp_path)])
    # `tmp_path` is empty by default; runner should create files and exit 0
    if r.exit_code != 0:
        print(r.stdout); print(r.stderr if hasattr(r, 'stderr') else '')
    assert r.exit_code == 0
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "results.csv").exists()
    assert "Wrote" in r.stdout
```

`tests/unit/test_cli_reproduce.py`:

```python
import time
from typer.testing import CliRunner
from fertiscope.cli import app

def test_reproduce_runs_under_30s(tmp_path):
    t0 = time.time()
    r = CliRunner().invoke(app, ["reproduce", "--output-dir", str(tmp_path)])
    elapsed = time.time() - t0
    assert r.exit_code == 0
    assert elapsed < 30, f"reproduce took {elapsed:.1f}s, expected < 30s"
    assert (tmp_path / "manifest.json").exists()
    # Output table should mention at least these
    for substr in ["eng", "tam", "mya", "Fertility"]:
        assert substr in r.stdout

def test_reproduce_no_network_required(tmp_path, monkeypatch):
    """Smoke test: blocking httpx should not affect reproduce."""
    import httpx
    def boom(*a, **kw): raise RuntimeError("no network allowed")
    monkeypatch.setattr(httpx, "get", boom)
    monkeypatch.setattr(httpx, "post", boom)
    r = CliRunner().invoke(app, ["reproduce", "--output-dir", str(tmp_path)])
    assert r.exit_code == 0
```

### Notes

- `fertiscope reproduce` MUST work without `HF_TOKEN`, without `[hf]` extra, and without internet. Only the `[oai]` extra is required (tiktoken).
- The Rich progress bar in `run` doesn't show per-cell granularity in v0.2 — runner doesn't emit callbacks. Future task: add a callback hook in #024.
- The reproduce summary table is the "demo output" reviewers see; keep it tight and informative.
- The `< 30s` constraint is critical for the credibility demo. If timings creep up over time, profile and trim.

## Acceptance Criteria

- [ ] `fertiscope run --config configs/study_test.yaml` exits 0 and writes 4-5 artifact files to `runs/test/`.
- [ ] CLI prints expected row count before measurement starts.
- [ ] CLI prints success summary with manifest SHA.
- [ ] `--hf-token` arg sets `HF_TOKEN` env var.
- [ ] `--output-dir` overrides the resolved output dir.
- [ ] `fertiscope reproduce` exits 0 in **< 30 seconds** with no network.
- [ ] `reproduce` produces a Rich summary table covering 7 languages.
- [ ] Both CLI tests pass.

## User Stories

### Story: Hackathon judge runs the demo

1. `pip install fertiscope[oai]`.
2. `fertiscope reproduce`.
3. 20 seconds later: table shows Tamil fertility ≈ 11× English on cl100k.
4. Judge believes the package without inspecting code.

### Story: Researcher kicks off the main study

1. Sets `HF_TOKEN`, accepts gated licenses.
2. `fertiscope run --config configs/study_main.yaml`.
3. CLI: "expected rows: 352". Progress bar.
4. After ~15 min: "✓ Wrote 352 rows (8 skipped) to runs/main. Manifest SHA: abc123def456..."
5. Open `runs/main/results.csv` in Excel.

### Story: User without keys hits a graceful exit

1. `fertiscope run --config configs/study_main.yaml` (no HF_TOKEN).
2. Gated tokenizers produce skip rows; CLI continues.
3. Final summary: "✓ 352 rows (96 skipped) — 8 tokenizers × 12 langs were gated and skipped."

---

Blocked by: #003, #023, #024, #025
