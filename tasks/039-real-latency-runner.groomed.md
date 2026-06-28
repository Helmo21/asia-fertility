# Real generation-latency runner (optional moat)

Status: pending (v0.4 optional)
Tags: `latency`, `benchmarking`, `openrouter`, `async`, `optional`
Depends on: #029, #023
Blocks: None

## Scope

Actually time LLM generation across languages — moving beyond "tokens ≈ latency" assumption. Times TTFT (time-to-first-token) and per-output-token throughput, with warmup discarded and cache disclosure.

The defense: when reviewers ask "did you verify your latency claim?" — yes, here's the data.

### Files to create

- `src/fertiscope/latency/__init__.py`
- `src/fertiscope/latency/runner.py`
- `configs/latency_main.yaml`
- `tests/unit/test_latency_runner.py`

### Files to modify

- `src/fertiscope/cli.py` — add `latency` subcommand.

### Interface and contract

`src/fertiscope/latency/runner.py`:

```python
from __future__ import annotations
import asyncio
import csv
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal
import yaml
from pydantic import BaseModel, Field, ConfigDict
import httpx

from fertiscope.corpora import load_corpus
from fertiscope.languages import get_language


class LatencyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    languages: list[str]
    models: list[str]
    corpus: str = "flores"
    n_sentences: int = 20
    warmup: int = 3
    trials: int = 5
    output_dir: str = "runs/latency/{name}"
    max_output_tokens: int = 200
    concurrency: int = 2     # latency tests need low concurrency for accuracy

    @classmethod
    def from_yaml(cls, p: str | Path) -> "LatencyConfig":
        return cls.model_validate(yaml.safe_load(Path(p).read_text("utf-8")))

    def resolve_output_dir(self) -> Path:
        return Path(self.output_dir.format(name=self.name))


@dataclass(frozen=True)
class LatencyRow:
    model: str
    lang: str
    iso: str
    sentence_id: str
    trial: int
    input_chars: int
    ttft_ms: float            # time to first token
    total_ms: float
    output_chars: int
    chars_per_second: float   # output throughput
    error: str = ""


async def _time_one_call(client: httpx.AsyncClient, model: str, prompt: str,
                         max_tokens: int) -> tuple[float, float, str]:
    """Returns (ttft_ms, total_ms, output_text). Uses OpenRouter streaming."""
    import os
    headers = {
        "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY','')}",
        "HTTP-Referer": "https://fertiscope.vercel.app",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "stream": True,
    }
    t_start = time.perf_counter()
    ttft = None
    output = []
    async with client.stream("POST", "/chat/completions", json=body, headers=headers) as resp:
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            if ttft is None:
                ttft = (time.perf_counter() - t_start) * 1000
            try:
                import json as _json
                chunk = _json.loads(data)
                delta = chunk["choices"][0]["delta"].get("content", "")
                output.append(delta)
            except (KeyError, IndexError, _json.JSONDecodeError):
                continue
    total = (time.perf_counter() - t_start) * 1000
    return ttft or total, total, "".join(output)


async def run_latency(cfg: LatencyConfig) -> Path:
    out_dir = cfg.resolve_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "results.csv"

    write_header = not csv_path.exists()
    f = csv_path.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(f, fieldnames=list(LatencyRow.__dataclass_fields__))
    if write_header:
        writer.writeheader()

    corpus = load_corpus(cfg.corpus)
    sem = asyncio.Semaphore(cfg.concurrency)
    async with httpx.AsyncClient(
        base_url="https://openrouter.ai/api/v1", timeout=120.0,
    ) as client:
        for model in cfg.models:
            for lang in cfg.languages:
                sentences = list(corpus.iter_sentences(lang, limit=cfg.n_sentences + cfg.warmup))
                lang_meta = get_language(lang)

                async def one(sent, trial):
                    async with sem:
                        try:
                            ttft, total, out = await _time_one_call(
                                client, model, sent.text + "\n\nSummarize in one sentence.",
                                cfg.max_output_tokens,
                            )
                            err = ""
                        except Exception as e:
                            ttft, total, out, err = 0.0, 0.0, "", str(e)
                        cps = (len(out) / (total / 1000)) if total > 0 else 0.0
                        return LatencyRow(
                            model=model, lang=lang_meta.name, iso=lang,
                            sentence_id=sent.id, trial=trial,
                            input_chars=len(sent.text),
                            ttft_ms=ttft, total_ms=total,
                            output_chars=len(out),
                            chars_per_second=cps, error=err,
                        )

                # Warmup — discarded
                for sent in sentences[:cfg.warmup]:
                    await one(sent, trial=-1)

                # Measured trials
                tasks = [one(sentences[cfg.warmup + i % (len(sentences) - cfg.warmup)], trial=t)
                         for i in range(cfg.n_sentences) for t in range(cfg.trials)]
                for coro in asyncio.as_completed(tasks):
                    row = await coro
                    writer.writerow(asdict(row))
                    f.flush()

    f.close()
    return csv_path
```

CLI:

```python
@app.command()
def latency(config: str = typer.Option(..., "--config"),
            yes: bool = typer.Option(False, "--yes", "-y")) -> None:
    """Time real LLM generation across (model × language) cells."""
    import asyncio
    from fertiscope.latency.runner import LatencyConfig, run_latency

    cfg = LatencyConfig.from_yaml(config)
    n_calls = len(cfg.models) * len(cfg.languages) * (cfg.warmup + cfg.n_sentences * cfg.trials)
    est = 0.001 * n_calls       # crude $0.001/call upper bound
    typer.echo(f"Latency benchmark: {n_calls} calls (incl. warmup), ~${est:.2f}")
    if not yes:
        if not typer.confirm("Proceed?"):
            raise typer.Exit(1)
    csv_path = asyncio.run(run_latency(cfg))
    typer.echo(f"✓ {csv_path}")
```

`configs/latency_main.yaml`:

```yaml
name: main
languages: [eng, vie, tam, mya]
models: ["openai/gpt-4o-mini", "openai/gpt-3.5-turbo"]
corpus: flores
n_sentences: 20
warmup: 3
trials: 3
output_dir: runs/latency/main
max_output_tokens: 200
concurrency: 2
```

### Notes

- **Warmup discarded**: first N calls per (model, lang) have inflated TTFT due to OpenRouter routing decisions. Discard.
- **Caching disclosure**: Anthropic auto-caches matching prefixes — must vary text per call (we do; we use different FLORES sentences).
- **Concurrency=2**: tight latency measurement needs minimal contention.
- The chars/second throughput is a coarse proxy; reviewers should treat it as comparative, not absolute.
- Streaming is essential to measure TTFT separately from total.

## Acceptance Criteria

- [ ] `LatencyConfig.from_yaml("configs/latency_main.yaml")` loads.
- [ ] `fertiscope latency --config X --yes` runs end-to-end (with `OPENROUTER_API_KEY`).
- [ ] Output CSV has columns: `model, lang, iso, sentence_id, trial, input_chars, ttft_ms, total_ms, output_chars, chars_per_second, error`.
- [ ] Warmup rows (trial=-1) are NOT written to output.
- [ ] Concurrency limit enforced (verified via test mock).
- [ ] Cost estimate printed before run.
- [ ] All unit tests pass.
- [ ] `mypy --strict src/fertiscope/latency/` passes.

## User Stories

### Story: Reviewer asks "did you measure latency?"

1. v2 paper §X: "We measured TTFT and per-output-token throughput on gpt-4o-mini across (eng, vie, tam, mya). Correlation with token count r=0.94, slope 1.02×."
2. Cites `runs/latency/main/results.csv`.
3. Caveat closed.

### Story: Maintainer benchmarks a new model

1. Adds `meta-llama/llama-4-scout` to models.
2. Reruns `fertiscope latency`.
3. Compares throughput vs llama-3.1-8b.

---

Blocked by: #029, #023
