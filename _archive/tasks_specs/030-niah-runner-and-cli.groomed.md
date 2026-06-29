# NIAH runner with resume + `fertiscope niah` CLI

Status: pending
Tags: `niah`, `runner`, `resumable`, `cli`, `cost-confirmation`
Depends on: #003, #012, #027, #028, #029
Blocks: None

## Scope

The orchestrator that walks the `(model × language × fill_target × position × trial)` grid, calls the OpenRouter provider, scores recall, and writes incremental CSVs. Includes a cost-estimate confirmation gate, resume capability, and the `fertiscope niah {run,resume,report}` subcommands.

### Files to create

- `src/fertiscope/niah/runner.py`
- `src/fertiscope/niah/scoring.py`
- `configs/niah_main.yaml`
- `configs/niah_test.yaml`
- `tests/unit/test_niah_runner.py`
- `tests/unit/test_niah_scoring.py`

### Files to modify

- `src/fertiscope/cli.py` — replace `niah run/resume/report` stubs.

### Interface and contract

`src/fertiscope/niah/scoring.py`:

```python
from __future__ import annotations
import unicodedata


def recall_score(response: str, marker: str) -> bool:
    """Return True if marker appears in response (NFC-normalized substring match).

    We use exact substring rather than fuzzy match to avoid false positives.
    NFC normalization handles decomposed-vs-composed Unicode artifacts.
    """
    r = unicodedata.normalize("NFC", response)
    m = unicodedata.normalize("NFC", marker)
    return m in r
```

`src/fertiscope/niah/runner.py`:

```python
from __future__ import annotations
import asyncio
import csv
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal
import yaml
from pydantic import BaseModel, Field, ConfigDict

from fertiscope.tokenizers import get_tokenizer
from fertiscope.corpora import load_corpus
from fertiscope.languages import get_language
from fertiscope.niah.markers import get_marker
from fertiscope.niah.haystack import build_haystack
from fertiscope.niah.providers import OpenRouterProvider, ChatError, RetryableError
from fertiscope.niah.scoring import recall_score


class NIAHConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    languages: list[str]
    models: list[str]        # OpenRouter model ids, e.g. "openai/gpt-4o-mini"
    corpus: str = "flores"
    fill_targets: list[int] = Field(default_factory=lambda: [4096, 16384, 65536, 131072])
    positions: list[float] = Field(default_factory=lambda: [0.05, 0.25, 0.50, 0.75, 0.95])
    trials: int = 3
    provider: Literal["openrouter"] = "openrouter"
    output_dir: str = "runs/niah/{name}"
    concurrency: int = 4
    sizing_tokenizer: str = "openai/o200k_base"   # used only for haystack sizing

    @classmethod
    def from_yaml(cls, path: str | Path) -> "NIAHConfig":
        return cls.model_validate(yaml.safe_load(Path(path).read_text("utf-8")))

    def resolve_output_dir(self) -> Path:
        return Path(self.output_dir.format(name=self.name))

    def total_cells(self) -> int:
        return len(self.models) * len(self.languages) * len(self.fill_targets) * len(self.positions) * self.trials


@dataclass(frozen=True)
class NIAHRow:
    model: str
    lang: str
    iso: str
    script: str
    fill_tokens: int
    position_pct: float
    trial: int
    marker: str
    actual_tokens: int
    marker_position_tokens: int
    response: str
    recalled: bool
    error: str = ""
    elapsed_seconds: float = 0.0


def estimate_cost_usd(cfg: NIAHConfig, prices: dict[str, float] | None = None) -> float:
    """Rough cost estimate. Defaults to gpt-4o-mini pricing.

    Per call: avg input = fill_target / 2, avg output = 50 tokens.
    """
    avg_input  = sum(cfg.fill_targets) / len(cfg.fill_targets) / 2
    avg_output = 50.0
    # Default conservative: gpt-4o-mini at $0.15/1M input, $0.60/1M output
    in_rate  = 0.15 / 1_000_000
    out_rate = 0.60 / 1_000_000
    per_call = avg_input * in_rate + avg_output * out_rate
    return per_call * cfg.total_cells() * len(cfg.models)


async def _run_one_cell(
    provider: OpenRouterProvider,
    cfg: NIAHConfig,
    model: str,
    lang: str,
    fill: int,
    position: float,
    trial: int,
    sentences,
    sizing_tok,
) -> NIAHRow:
    import time
    language = get_language(lang)
    marker = get_marker(language.script, cfg.positions.index(position))

    h = build_haystack(sentences, target_tokens=fill, tokenizer=sizing_tok,
                      marker=marker, position_pct=position)

    messages = [
        {"role": "system", "content": "Read the following text carefully. Recall any unusual marker phrases when asked."},
        {"role": "user", "content": h.text + "\n\nWhat is the marker phrase in the text above? Respond with only the marker."},
    ]
    t0 = time.time()
    try:
        response = await provider.chat(model, messages, max_tokens=100)
        recalled = recall_score(response, marker)
        err = ""
    except (ChatError, RetryableError) as e:
        response = ""
        recalled = False
        err = str(e)
    elapsed = time.time() - t0

    return NIAHRow(
        model=model, lang=language.name, iso=lang, script=language.script,
        fill_tokens=fill, position_pct=position, trial=trial,
        marker=marker, actual_tokens=h.actual_tokens,
        marker_position_tokens=h.marker_position_tokens,
        response=response, recalled=recalled, error=err, elapsed_seconds=elapsed,
    )


def _load_completed(csv_path: Path) -> set[tuple]:
    """Read existing CSV (if any) and return the set of (model, iso, fill, position, trial)
    tuples already completed."""
    if not csv_path.exists():
        return set()
    done: set[tuple] = set()
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            done.add((row["model"], row["iso"], int(row["fill_tokens"]),
                      float(row["position_pct"]), int(row["trial"])))
    return done


async def run_niah(cfg: NIAHConfig) -> Path:
    """Walk the grid, write rows incrementally to results.csv. Resumable."""
    out_dir = cfg.resolve_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "results.csv"
    completed = _load_completed(csv_path)

    write_header = not csv_path.exists()
    file = csv_path.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(file, fieldnames=list(NIAHRow.__dataclass_fields__))
    if write_header:
        writer.writeheader()

    sizing_tok = get_tokenizer(cfg.sizing_tokenizer)
    provider = OpenRouterProvider(max_concurrency=cfg.concurrency)

    # Cache per-language sentence lists
    corpus = load_corpus(cfg.corpus) if cfg.corpus != "custom" else load_corpus("custom", path="<set by caller>")
    sentence_cache: dict[str, list] = {}

    tasks = []
    for model in cfg.models:
        for lang in cfg.languages:
            if lang not in sentence_cache:
                sentence_cache[lang] = list(corpus.iter_sentences(lang, limit=2000))
            for fill in cfg.fill_targets:
                for position in cfg.positions:
                    for trial in range(cfg.trials):
                        key = (model, lang, fill, position, trial)
                        if key in completed:
                            continue
                        tasks.append(_run_one_cell(provider, cfg, model, lang, fill, position, trial,
                                                  sentence_cache[lang], sizing_tok))

    for coro in asyncio.as_completed(tasks):
        row = await coro
        writer.writerow(asdict(row))
        file.flush()

    file.close()
    await provider.aclose()
    return csv_path
```

`cli.py` — replace `niah_run/resume/report`:

```python
@niah_app.command("run")
def niah_run(
    config: str = typer.Option(..., "--config"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip cost confirmation"),
) -> None:
    """Run the multi-turn NIAH sweep."""
    import asyncio
    from fertiscope.niah.runner import NIAHConfig, run_niah, estimate_cost_usd

    cfg = NIAHConfig.from_yaml(config)
    cost = estimate_cost_usd(cfg)
    typer.echo(f"Estimated cost (gpt-4o-mini-equivalent): ~${cost:.2f}")
    typer.echo(f"Total cells: {cfg.total_cells()}, models: {len(cfg.models)}")
    if not yes:
        confirm = typer.confirm("Proceed?")
        if not confirm:
            raise typer.Exit(code=1)
    csv_path = asyncio.run(run_niah(cfg))
    typer.echo(f"✓ Wrote {csv_path}")


@niah_app.command("resume")
def niah_resume(output_dir: str = typer.Option(..., "--output-dir"),
                config: str = typer.Option(..., "--config")) -> None:
    """Resume an interrupted NIAH sweep."""
    import asyncio
    from fertiscope.niah.runner import NIAHConfig, run_niah
    cfg = NIAHConfig.from_yaml(config)
    csv_path = asyncio.run(run_niah(cfg))
    typer.echo(f"✓ Resumed; CSV at {csv_path}")


@niah_app.command("report")
def niah_report(output_dir: str = typer.Option(..., "--output-dir")) -> None:
    """Print recall heatmap from an NIAH run."""
    from pathlib import Path
    import csv as csvmod
    from collections import defaultdict
    from rich.console import Console
    from rich.table import Table

    csv_path = Path(output_dir) / "results.csv"
    by_cell: dict[tuple, list[bool]] = defaultdict(list)
    with csv_path.open("r", encoding="utf-8") as f:
        for row in csvmod.DictReader(f):
            by_cell[(row["model"], row["iso"], int(row["fill_tokens"]), float(row["position_pct"]))].append(row["recalled"] == "True")

    table = Table(title=f"NIAH recall · {csv_path}")
    table.add_column("Model"); table.add_column("Lang"); table.add_column("Fill"); table.add_column("Pos"); table.add_column("Recall", justify="right")
    for (model, iso, fill, pos), hits in sorted(by_cell.items()):
        rate = sum(hits) / len(hits)
        table.add_row(model, iso, str(fill), f"{pos:.2f}", f"{rate:.2f} ({sum(hits)}/{len(hits)})")
    Console().print(table)
```

`configs/niah_test.yaml`:

```yaml
name: test
languages: [eng, tam]
models: ["openai/gpt-4o-mini"]
corpus: flores
fill_targets: [4096]
positions: [0.5]
trials: 1
output_dir: runs/niah/test
concurrency: 2
sizing_tokenizer: openai/o200k_base
```

`configs/niah_main.yaml`:

```yaml
name: main
languages: [eng, vie, ind, zsm, tgl, tha, hin, ben, sin, tam, tel, kan, mal, mya, khm, lao]
models:
  - openai/gpt-4o-mini
  - openai/gpt-3.5-turbo
  - meta-llama/llama-3.1-8b-instruct
corpus: flores
fill_targets: [4096, 16384, 65536, 131072]
positions: [0.05, 0.25, 0.50, 0.75, 0.95]
trials: 3
output_dir: runs/niah/main
concurrency: 4
sizing_tokenizer: openai/o200k_base
```

`tests/unit/test_niah_scoring.py`:

```python
from fertiscope.niah.scoring import recall_score

def test_exact_match():
    assert recall_score("the marker is MARKER-AURORA", "MARKER-AURORA")

def test_no_match():
    assert not recall_score("nothing here", "MARKER-AURORA")

def test_nfc_normalization():
    """Decomposed input + composed marker should still match."""
    decomp = "MARKER-cafe\u0301"
    comp   = "MARKER-café"
    assert recall_score(decomp, comp)
```

`tests/unit/test_niah_runner.py`:

```python
import pytest, asyncio
from pathlib import Path
from fertiscope.niah.runner import NIAHConfig, estimate_cost_usd, _load_completed

def test_cost_estimate():
    cfg = NIAHConfig(name="t", languages=["eng"], models=["a"], fill_targets=[8192],
                     positions=[0.5], trials=1, sizing_tokenizer="openai/o200k_base")
    cost = estimate_cost_usd(cfg)
    assert 0 < cost < 1.0

def test_load_completed_empty(tmp_path):
    assert _load_completed(tmp_path / "noexist.csv") == set()

def test_load_completed_resumes(tmp_path):
    csv = tmp_path / "r.csv"
    csv.write_text(
        "model,iso,fill_tokens,position_pct,trial\n"
        "m1,eng,4096,0.5,0\n"
        "m1,tam,4096,0.5,0\n",
        encoding="utf-8",
    )
    done = _load_completed(csv)
    assert ("m1", "eng", 4096, 0.5, 0) in done
    assert len(done) == 2
```

### Notes

- **No real OpenRouter calls in CI.** The unit tests cover cost estimate, resume reading, and scoring. Integration tests would require a real key — skip in default CI.
- The `corpus="custom"` path is left as a stub here; passing a custom path requires the CLI to wire `--corpus-path` (omitted for v0.2 simplicity).
- The runner uses `asyncio.as_completed` so finished cells write to disk immediately — kills mid-run lose only the in-flight calls.
- The cost estimate is conservative (gpt-4o-mini pricing). Users running GPT-5 should multiply mentally. Document.
- Sentences cache is per-language to avoid re-tokenizing FLORES for every cell.

## Acceptance Criteria

- [ ] `NIAHConfig.from_yaml("configs/niah_test.yaml")` loads.
- [ ] `cfg.total_cells()` returns the expected count (e.g. 2 langs × 1 model × 1 fill × 1 pos × 1 trial = 2).
- [ ] `estimate_cost_usd(cfg)` returns a positive USD value.
- [ ] `_load_completed` returns empty set for missing CSV.
- [ ] `_load_completed` correctly parses an existing CSV.
- [ ] `fertiscope niah run --config configs/niah_test.yaml` prints cost estimate and prompts unless `--yes`.
- [ ] `fertiscope niah report --output-dir <path>` prints a recall table.
- [ ] All 6 unit tests pass.
- [ ] `mypy --strict src/fertiscope/niah/runner.py` passes.

## User Stories

### Story: Author runs the v2 NIAH for the paper

1. `OPENROUTER_API_KEY` set.
2. `fertiscope niah run --config configs/niah_main.yaml`.
3. CLI: "Estimated cost: $1.85. Total cells: 2880. Proceed? [y/N]".
4. Types `y`.
5. Runner writes rows incrementally over ~2 hours.
6. `fertiscope niah report --output-dir runs/niah/main` prints heatmap.

### Story: Crash recovery

1. Run mid-sweep, laptop sleeps, OpenRouter times out, runner crashes.
2. `fertiscope niah resume --config configs/niah_main.yaml --output-dir runs/niah/main`.
3. Reads existing CSV (1247 rows), skips those cells, resumes from cell 1248.
4. No duplicates, no wasted API spend.

### Story: Cost-gate stops a mistake

1. User mistakenly sets `fill_targets: [131072]` and `trials: 10`.
2. CLI: "Estimated cost: $48.20".
3. User reads, realizes, aborts.

---

Blocked by: #003, #012, #027, #028, #029
