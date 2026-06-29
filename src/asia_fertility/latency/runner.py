"""Latency benchmark runner — streaming OpenRouter calls with TTFT timing.

Mirrors the niah/runner.py design:
  - resumable via incremental CSV writes
  - per-cell warmup discarded, N timed trials measured
  - dedup key = (model, iso, trial)
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import httpx
import yaml
from pydantic import BaseModel, ConfigDict, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from asia_fertility.languages import get_language

from ..niah.providers import ChatError, RetryableError, _retryable
from .prompts import build_prompts

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #


class LatencyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    languages: list[str]
    models: list[str]
    corpus: Literal["flores"] = "flores"
    n_warmup: int = Field(default=3, ge=0)
    n_trials: int = Field(default=10, ge=1)
    max_output_tokens: int = Field(default=200, gt=0)
    output_dir: str = "runs/latency/{name}"
    concurrency: int = Field(default=2, ge=1)
    timeout: float = Field(default=120.0, gt=0)

    @classmethod
    def from_yaml(cls, path: str | Path) -> LatencyConfig:
        return cls.model_validate(yaml.safe_load(Path(path).read_text("utf-8")))

    def resolve_output_dir(self) -> Path:
        return Path(self.output_dir.format(name=self.name))

    def total_calls(self) -> int:
        per_cell = self.n_warmup + self.n_trials
        return len(self.languages) * len(self.models) * per_cell


# --------------------------------------------------------------------------- #
# Row schema
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class LatencyRow:
    model: str
    iso: str
    script: str
    trial: int  # negative for warmup, 0..n_trials-1 for measured
    is_warmup: bool
    prompt_chars: int
    ttft_ms: float
    total_ms: float
    output_chars: int
    error: str = ""


# --------------------------------------------------------------------------- #
# Streaming provider
# --------------------------------------------------------------------------- #


class _StreamingProvider:
    """Thin wrapper around httpx.AsyncClient for streaming chat completions.

    Returns (ttft_ms, total_ms, response_text) per call. Retries on 429/5xx
    with exponential backoff (same policy as niah.providers).
    """

    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
        max_concurrency: int = 2,
    ) -> None:
        key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise ChatError("OPENROUTER_API_KEY not set")
        self._client = httpx.AsyncClient(
            base_url=base_url or self.DEFAULT_BASE_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "HTTP-Referer": "https://github.com/Helmo21/asia-fertility",
                "X-Title": "asia-fertility latency",
            },
            timeout=timeout,
        )
        self._sem = asyncio.Semaphore(max_concurrency)

    async def chat_with_timing(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 200,
        temperature: float = 0.0,
    ) -> tuple[float, float, str]:
        async with self._sem:
            return await self._stream_with_retry(model, prompt, max_tokens, temperature)

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(RetryableError),
        reraise=True,
    )
    async def _stream_with_retry(
        self,
        model: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple[float, float, str]:
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        t_start = time.perf_counter()
        ttft_ms: float | None = None
        chunks: list[str] = []
        try:
            async with self._client.stream("POST", "/chat/completions", json=body) as resp:
                if _retryable(resp.status_code):
                    text = await resp.aread()
                    raise RetryableError(f"{resp.status_code}: {text.decode()[:200]}")
                if resp.status_code >= 400:
                    text = await resp.aread()
                    raise ChatError(f"{resp.status_code}: {text.decode()[:200]}")

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    if ttft_ms is None:
                        ttft_ms = (time.perf_counter() - t_start) * 1000.0
                    try:
                        payload = json.loads(data)
                        delta = payload["choices"][0]["delta"].get("content", "") or ""
                        chunks.append(delta)
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                        continue
        except httpx.TransportError as e:
            raise RetryableError(f"transport: {e}") from e

        total_ms = (time.perf_counter() - t_start) * 1000.0
        if ttft_ms is None:
            ttft_ms = total_ms
        return ttft_ms, total_ms, "".join(chunks)

    async def aclose(self) -> None:
        await self._client.aclose()


# --------------------------------------------------------------------------- #
# Cost estimate (conservative, for the CLI confirmation prompt)
# --------------------------------------------------------------------------- #


def estimate_cost_usd(cfg: LatencyConfig) -> float:
    """Conservative input+output cost at gpt-4o-mini rates."""
    avg_input_tokens = 200.0  # ~200 chars/sentence on FLORES eng baseline; grows with fertility
    avg_output_tokens = cfg.max_output_tokens / 4.0  # models rarely fill the cap
    per_call = avg_input_tokens * 0.15 / 1_000_000.0 + avg_output_tokens * 0.60 / 1_000_000.0
    return per_call * cfg.total_calls()


# --------------------------------------------------------------------------- #
# Resumability — read existing CSV
# --------------------------------------------------------------------------- #


def _load_completed(csv_path: Path) -> set[tuple]:
    if not csv_path.exists():
        return set()
    done: set[tuple] = set()
    with csv_path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            done.add((row["model"], row["iso"], int(row["trial"])))
    return done


# --------------------------------------------------------------------------- #
# Cell execution
# --------------------------------------------------------------------------- #


async def _run_one(
    provider: _StreamingProvider,
    model: str,
    lang: str,
    trial: int,
    prompt: str,
    max_tokens: int,
    n_warmup: int,
) -> LatencyRow:
    is_warmup = trial < 0
    language = get_language(lang)
    try:
        ttft, total, response = await provider.chat_with_timing(
            model, prompt, max_tokens=max_tokens
        )
        err = ""
    except (ChatError, RetryableError) as e:
        ttft, total, response = 0.0, 0.0, ""
        err = str(e)[:200]
    return LatencyRow(
        model=model,
        iso=lang,
        script=language.script,
        trial=trial,
        is_warmup=is_warmup,
        prompt_chars=len(prompt),
        ttft_ms=ttft,
        total_ms=total,
        output_chars=len(response),
        error=err,
    )


# --------------------------------------------------------------------------- #
# Run + report
# --------------------------------------------------------------------------- #


async def run_latency(cfg: LatencyConfig) -> Path:
    """Walk the grid (model × lang × {warmup, trials}); write CSV incrementally."""
    out_dir = cfg.resolve_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "results.csv"
    completed = _load_completed(csv_path)

    write_header = not csv_path.exists()
    f = csv_path.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(f, fieldnames=list(LatencyRow.__dataclass_fields__))
    if write_header:
        writer.writeheader()

    provider = _StreamingProvider(max_concurrency=cfg.concurrency, timeout=cfg.timeout)

    # Per-language prompt cache (build once, reuse across models)
    prompts_by_lang: dict[str, list[str]] = {}

    tasks: list = []
    n_total_per_cell = cfg.n_warmup + cfg.n_trials
    for model in cfg.models:
        for lang in cfg.languages:
            if lang not in prompts_by_lang:
                prompts_by_lang[lang] = build_prompts(lang, n_total_per_cell, cfg.corpus)
            for i in range(n_total_per_cell):
                trial_idx = i - cfg.n_warmup  # negative for warmup, 0+ for measured
                key = (model, lang, trial_idx)
                if key in completed:
                    continue
                tasks.append(
                    _run_one(
                        provider,
                        model,
                        lang,
                        trial_idx,
                        prompts_by_lang[lang][i],
                        cfg.max_output_tokens,
                        cfg.n_warmup,
                    )
                )

    total = len(tasks)
    for done_count, coro in enumerate(asyncio.as_completed(tasks), start=1):
        row = await coro
        writer.writerow(asdict(row))
        f.flush()
        if done_count % 10 == 0 or done_count == total:
            tag = "warmup" if row.is_warmup else "trial"
            print(
                f"  [{done_count}/{total}] last: {row.iso}/{row.model} {tag} trial={row.trial} "
                f"ttft={row.ttft_ms:.0f}ms total={row.total_ms:.0f}ms err={row.error[:40]!r}",
                flush=True,
            )

    f.close()
    await provider.aclose()
    return csv_path


def latency_report(output_dir: str | Path, baseline_lang: str = "eng") -> dict:
    """Aggregate per (model, iso) — mean total_ms with bootstrap CI; compute penalty vs baseline."""
    import numpy as np

    csv_path = Path(output_dir) / "results.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"No results at {csv_path}")

    cells: dict[tuple[str, str], list[float]] = defaultdict(list)
    ttfts: dict[tuple[str, str], list[float]] = defaultdict(list)
    errs: dict[tuple[str, str], int] = defaultdict(int)

    with csv_path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["is_warmup"].lower() == "true":
                continue
            key = (row["model"], row["iso"])
            if row["error"]:
                errs[key] += 1
                continue
            cells[key].append(float(row["total_ms"]))
            ttfts[key].append(float(row["ttft_ms"]))

    def bootstrap(xs: list[float], n: int = 1000, seed: int = 42) -> tuple[float, float, float]:
        if len(xs) < 2:
            v = float(xs[0]) if xs else float("nan")
            return v, v, v
        rng = np.random.default_rng(seed)
        means = [float(np.mean(rng.choice(xs, len(xs), replace=True))) for _ in range(n)]
        return (
            float(np.mean(xs)),
            float(np.quantile(means, 0.025)),
            float(np.quantile(means, 0.975)),
        )

    summary: dict[tuple[str, str], dict] = {}
    for key, vals in cells.items():
        m, lo, hi = bootstrap(vals)
        t_m, t_lo, t_hi = bootstrap(ttfts[key])
        summary[key] = {
            "n": len(vals),
            "errors": errs.get(key, 0),
            "total_ms_mean": m,
            "total_ms_ci_low": lo,
            "total_ms_ci_high": hi,
            "ttft_ms_mean": t_m,
            "ttft_ms_ci_low": t_lo,
            "ttft_ms_ci_high": t_hi,
        }

    # per-model latency penalty vs baseline
    penalties: dict[tuple[str, str], float] = {}
    models = {k[0] for k in summary}
    for model in models:
        base = summary.get((model, baseline_lang))
        if not base:
            continue
        for (m2, iso), row in summary.items():
            if m2 != model:
                continue
            penalties[(model, iso)] = row["total_ms_mean"] / base["total_ms_mean"]

    return {
        "summary": {f"{m}|{i}": v for (m, i), v in summary.items()},
        "latency_penalty": {f"{m}|{i}": p for (m, i), p in penalties.items()},
        "baseline_lang": baseline_lang,
    }
