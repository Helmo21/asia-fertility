# CostCalculator + `fertiscope cost` CLI

Status: pending
Tags: `cost`, `cli`, `multi-currency`, `cheapest-model`
Depends on: #003, #006, #019, #020, #021
Blocks: None

## Scope

Tie prices + FX + tokenizer counts into a single `cost_of()` API and the `fertiscope cost` CLI. Output ranks models by cost, marks the cheapest, and shows local-currency conversions.

### Files to create

- `src/fertiscope/cost/model.py`
- `tests/unit/test_cost_model.py`
- `tests/unit/test_cli_cost.py`

### Files to modify

- `src/fertiscope/cli.py` — replace `cost` stub body.
- `src/fertiscope/cost/__init__.py` — export `cost_of`, `CostResult`.

### Interface and contract

`src/fertiscope/cost/model.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from fertiscope.tokenizers import get_tokenizer
from fertiscope.cost.prices import load_prices, PriceTable
from fertiscope.cost.fx     import load_fx, FXTable


@dataclass(frozen=True)
class CostResult:
    model_id: str
    tokenizer_id: str
    input_tokens: int
    output_tokens_est: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    costs_local: dict[str, float] = field(default_factory=dict)
    cheapest: bool = False


def cost_of(
    text: str,
    *,
    models: list[str],
    output_tokens_est: int = 200,
    currencies: list[str] | None = None,
    prices_path: str | Path | None = None,
    fx_path: str | Path | None = None,
) -> list[CostResult]:
    """Compute per-model cost of generating a response of `output_tokens_est` tokens
    in reply to `text`.

    Output is sorted ascending by `total_cost_usd`; the first row has `cheapest=True`.
    """
    if not models:
        raise ValueError("models must be non-empty")

    prices: PriceTable = load_prices(prices_path)
    fx:     FXTable     = load_fx(fx_path)
    currencies = currencies or ["USD"]

    rows: list[CostResult] = []
    for model_id in models:
        pricing = prices.get(model_id)
        tok = get_tokenizer(pricing.tokenizer)
        in_tokens = tok.count(text)

        # prices.input/.output are per 1M tokens, so divide.
        in_cost  = in_tokens          * pricing.input  / 1_000_000.0
        out_cost = output_tokens_est  * pricing.output / 1_000_000.0
        total_usd = in_cost + out_cost

        locals_ = {cur: fx.convert(total_usd, cur) for cur in currencies}

        rows.append(CostResult(
            model_id=model_id,
            tokenizer_id=pricing.tokenizer,
            input_tokens=in_tokens,
            output_tokens_est=output_tokens_est,
            input_cost_usd=in_cost,
            output_cost_usd=out_cost,
            total_cost_usd=total_usd,
            costs_local=locals_,
        ))

    rows.sort(key=lambda r: r.total_cost_usd)
    if rows:
        rows[0] = CostResult(
            **{**rows[0].__dict__, "cheapest": True}
        )
    return rows
```

`cli.py` — replace `cost`:

```python
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
    from fertiscope.cost import cost_of
    model_list = [m.strip() for m in models.split(",") if m.strip()]
    cur_list   = [c.strip() for c in currencies.split(",") if c.strip()]
    rows = cost_of(text, models=model_list, output_tokens_est=output_tokens_est,
                   currencies=cur_list, prices_path=prices_path, fx_path=fx_path)

    if json_out:
        import json, dataclasses
        typer.echo(json.dumps([dataclasses.asdict(r) for r in rows], indent=2, ensure_ascii=False))
        return

    from rich.console import Console
    from rich.table import Table
    table = Table(title=f"Cost · lang={lang} · output_est={output_tokens_est} tokens", title_style="bold")
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
        row_cells = [r.model_id, r.tokenizer_id, str(r.input_tokens), f"${r.total_cost_usd:.6f}"]
        for cur in cur_list:
            if cur != "USD":
                row_cells.append(f"{r.costs_local.get(cur, 0):.2f}")
        row_cells.append(cheapest)
        table.add_row(*row_cells)
    Console().print(table)
```

`tests/unit/test_cost_model.py`:

```python
import pytest
from fertiscope.cost.model import cost_of
from fertiscope.cost.exceptions import ModelNotInPrices

def test_basic_cost_single_model():
    rows = cost_of("hello world", models=["openai/gpt-4o"])
    assert len(rows) == 1
    r = rows[0]
    assert r.input_tokens > 0
    assert r.input_cost_usd >= 0
    assert r.output_cost_usd >= 0
    assert r.total_cost_usd == pytest.approx(r.input_cost_usd + r.output_cost_usd)
    assert r.cheapest is True            # single model = cheapest by default

def test_multi_model_sorts_by_cost():
    rows = cost_of("hello world", models=["openai/gpt-4-turbo", "openai/gpt-4o-mini", "openai/gpt-4o"])
    assert len(rows) == 3
    assert all(rows[i].total_cost_usd <= rows[i+1].total_cost_usd for i in range(len(rows)-1))
    assert rows[0].cheapest is True
    assert all(not r.cheapest for r in rows[1:])

def test_currency_conversion():
    rows = cost_of("hello", models=["openai/gpt-4o"], currencies=["USD", "VND"])
    assert "USD" in rows[0].costs_local
    assert "VND" in rows[0].costs_local
    assert rows[0].costs_local["VND"] > rows[0].costs_local["USD"]    # 1 USD > 0 VND

def test_unknown_model_raises():
    with pytest.raises(ModelNotInPrices):
        cost_of("hello", models=["not/a/real/model"])

def test_empty_models_raises():
    with pytest.raises(ValueError):
        cost_of("hello", models=[])

def test_known_value():
    """Hand-computed: gpt-4o = $2.50 / 1M input. 100 tokens input → $0.000250 input cost."""
    rows = cost_of("X" * 400,    # ~100 tokens (approximate)
                   models=["openai/gpt-4o"], output_tokens_est=0)
    r = rows[0]
    expected = r.input_tokens * 2.50 / 1_000_000.0
    assert r.input_cost_usd == pytest.approx(expected, rel=1e-9)
```

`tests/unit/test_cli_cost.py`:

```python
from typer.testing import CliRunner
from fertiscope.cli import app

def test_cost_cli_basic():
    r = CliRunner().invoke(app, ["cost", "--text", "hello", "--lang", "eng",
                                 "--models", "openai/gpt-4o,openai/gpt-3.5-turbo",
                                 "--currencies", "USD,VND"])
    assert r.exit_code == 0
    assert "openai/gpt-4o" in r.stdout
    assert "openai/gpt-3.5-turbo" in r.stdout
    assert "VND" in r.stdout

def test_cost_cli_json():
    import json
    r = CliRunner().invoke(app, ["cost", "--text", "hi", "--lang", "eng",
                                 "--models", "openai/gpt-4o", "--json"])
    assert r.exit_code == 0
    data = json.loads(r.stdout)
    assert len(data) == 1
    assert data[0]["model_id"] == "openai/gpt-4o"
    assert data[0]["cheapest"] is True
```

### Notes

- `output_tokens_est` defaults to 200 — typical short assistant reply. Document this default so users understand "the cost shown is for ONE request with a short reply".
- Sort key is `total_cost_usd` ascending. Stable sort (Python guarantees this) so ties preserve input order.
- The `cheapest` flag is mutated via dataclass replace; consider using `dataclasses.replace` if maintainers prefer that style.
- `cost_of` does NOT compute a "monthly bill" — that's a higher-level UX layer. The cost calculator returns per-request, and the user multiplies. Document.
- For tokenizers that are count-only (Anthropic/Gemini): same code path works because they implement `.count()`. Test this with the API mock pattern from #008.

## Acceptance Criteria

- [ ] `cost_of("hello", models=["openai/gpt-4o"])` returns a list with one `CostResult` where `cheapest is True`.
- [ ] `cost_of(..., models=[a, b, c])` sorts by `total_cost_usd` ascending.
- [ ] Currency conversion via FX table works for `USD` and `VND`.
- [ ] Unknown model → `ModelNotInPrices`.
- [ ] Empty models list → `ValueError`.
- [ ] Hand-computed reference matches within ±1e-9.
- [ ] `fertiscope cost --text "..." --lang vie --models openai/gpt-4o,openai/gpt-3.5-turbo --currencies USD,VND` prints a Rich table with USD + VND columns and marks the cheapest model.
- [ ] `fertiscope cost --json` outputs valid JSON.
- [ ] All 8 unit tests pass.
- [ ] `mypy --strict src/fertiscope/cost/model.py` passes.

## User Stories

### Story: Quick decision on cheapest model for Vietnamese

1. Vietnamese team runs `fertiscope cost --text "<sample VN prompt>" --lang vie --models openai/gpt-4o,openai/gpt-3.5-turbo,meta/llama-3.1-8b-instruct,google/gemma-4-27b --currencies VND`.
2. Output: rows sorted by USD cost, ✓ on the cheapest.
3. They see VND figures alongside USD.
4. Decision: switch to Gemma 4 for cost-sensitive workloads.

### Story: CI auto-prices a sample

1. CI runs `fertiscope cost --text "$(cat sample.txt)" --json > costs.json`.
2. Downstream script reads JSON, posts to a dashboard.

### Story: User picks their own snapshot

1. User overrides bundled prices: `fertiscope cost --prices configs/prices_2026-06.yaml --text ...`.
2. SHA logged for reproducibility (handled in #025 study runner).

---

Blocked by: #003, #006, #019, #020, #021
