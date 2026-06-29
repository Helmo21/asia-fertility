"""CostCalculator: token counts → multi-currency cost rows."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from asia_fertility.tokenizers import get_tokenizer

from .fx import FXTable, load_fx
from .prices import PriceTable, load_prices


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
    if not models:
        raise ValueError("models must be non-empty")

    prices: PriceTable = load_prices(prices_path)
    fx: FXTable = load_fx(fx_path)
    currencies = currencies or ["USD"]

    rows: list[CostResult] = []
    for model_id in models:
        pricing = prices.get(model_id)
        tok = get_tokenizer(pricing.tokenizer)
        in_tokens = tok.count(text)

        in_cost = in_tokens * pricing.input / 1_000_000.0
        out_cost = output_tokens_est * pricing.output / 1_000_000.0
        total_usd = in_cost + out_cost

        locals_ = {cur: fx.convert(total_usd, cur) for cur in currencies}

        rows.append(
            CostResult(
                model_id=model_id,
                tokenizer_id=pricing.tokenizer,
                input_tokens=in_tokens,
                output_tokens_est=output_tokens_est,
                input_cost_usd=in_cost,
                output_cost_usd=out_cost,
                total_cost_usd=total_usd,
                costs_local=locals_,
            )
        )

    rows.sort(key=lambda r: r.total_cost_usd)
    if rows:
        rows[0] = replace(rows[0], cheapest=True)
    return rows
