"""NIAH runner: walks the (model × lang × fill × position × trial) grid."""

from __future__ import annotations

import asyncio
import csv
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from asia_fertility.corpora import load_corpus
from asia_fertility.languages import get_language
from asia_fertility.tokenizers import get_tokenizer

from .haystack import build_haystack
from .markers import get_marker
from .providers import ChatError, OpenRouterProvider, RetryableError
from .scoring import recall_score


class NIAHConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    languages: list[str]
    models: list[str]
    corpus: str = "flores"
    fill_targets: list[int] = Field(default_factory=lambda: [4096, 16384, 65536])
    positions: list[float] = Field(default_factory=lambda: [0.05, 0.25, 0.50, 0.75, 0.95])
    trials: int = 2
    output_dir: str = "runs/niah/{name}"
    concurrency: int = 4
    sizing_tokenizer: str = "openai/o200k_base"

    @classmethod
    def from_yaml(cls, path: str | Path) -> NIAHConfig:
        return cls.model_validate(yaml.safe_load(Path(path).read_text("utf-8")))

    def resolve_output_dir(self) -> Path:
        return Path(self.output_dir.format(name=self.name))

    def total_cells(self) -> int:
        return (
            len(self.models)
            * len(self.languages)
            * len(self.fill_targets)
            * len(self.positions)
            * self.trials
        )


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


def estimate_cost_usd(cfg: NIAHConfig) -> float:
    """Rough cost estimate assuming gpt-4o-mini pricing."""
    avg_in = sum(cfg.fill_targets) / len(cfg.fill_targets)
    avg_out = 50.0
    in_rate = 0.15 / 1_000_000
    out_rate = 0.60 / 1_000_000
    per_call = avg_in * in_rate + avg_out * out_rate
    return per_call * cfg.total_cells()


def _load_completed(csv_path: Path) -> set[tuple]:
    if not csv_path.exists():
        return set()
    done: set[tuple] = set()
    with csv_path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            done.add(
                (
                    row["model"],
                    row["iso"],
                    int(row["fill_tokens"]),
                    float(row["position_pct"]),
                    int(row["trial"]),
                )
            )
    return done


async def _run_one(
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
    language = get_language(lang)
    marker = get_marker(language.script, cfg.positions.index(position))
    try:
        h = build_haystack(
            sentences,
            target_tokens=fill,
            tokenizer=sizing_tok,
            marker=marker,
            position_pct=position,
        )
    except Exception as e:
        return NIAHRow(
            model=model,
            lang=language.name,
            iso=lang,
            script=language.script,
            fill_tokens=fill,
            position_pct=position,
            trial=trial,
            marker=marker,
            actual_tokens=0,
            marker_position_tokens=0,
            response="",
            recalled=False,
            error=f"haystack: {e}",
        )

    messages = [
        {
            "role": "system",
            "content": "Read the following text carefully. Recall any unusual marker phrases when asked.",
        },
        {
            "role": "user",
            "content": h.text
            + "\n\nWhat is the marker phrase in the text above? Respond with ONLY the marker phrase, nothing else.",
        },
    ]
    t0 = time.time()
    try:
        response = await provider.chat(model, messages, max_tokens=100)
        recalled = recall_score(response, marker)
        err = ""
    except (ChatError, RetryableError) as e:
        response, recalled, err = "", False, str(e)[:200]
    elapsed = time.time() - t0

    return NIAHRow(
        model=model,
        lang=language.name,
        iso=lang,
        script=language.script,
        fill_tokens=fill,
        position_pct=position,
        trial=trial,
        marker=marker,
        actual_tokens=h.actual_tokens,
        marker_position_tokens=h.marker_position_tokens,
        response=response,
        recalled=recalled,
        error=err,
        elapsed_seconds=elapsed,
    )


async def run_niah(cfg: NIAHConfig) -> Path:
    out_dir = cfg.resolve_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "results.csv"
    completed = _load_completed(csv_path)

    write_header = not csv_path.exists()
    f = csv_path.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(f, fieldnames=list(NIAHRow.__dataclass_fields__))
    if write_header:
        writer.writeheader()

    sizing_tok = get_tokenizer(cfg.sizing_tokenizer)
    provider = OpenRouterProvider(max_concurrency=cfg.concurrency)
    corpus = load_corpus(cfg.corpus)
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
                        tasks.append(
                            _run_one(
                                provider,
                                cfg,
                                model,
                                lang,
                                fill,
                                position,
                                trial,
                                sentence_cache[lang],
                                sizing_tok,
                            )
                        )

    total = len(tasks)
    for completed_count, coro in enumerate(asyncio.as_completed(tasks), start=1):
        row = await coro
        writer.writerow(asdict(row))
        f.flush()
        if completed_count % 10 == 0 or completed_count == total:
            print(
                f"  [{completed_count}/{total}] last: {row.iso}/{row.model} fill={row.fill_tokens} pos={row.position_pct} recall={row.recalled}",
                flush=True,
            )

    f.close()
    await provider.aclose()
    return csv_path
