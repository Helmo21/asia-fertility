"""FastAPI app for `fertiscope serve`. Single-process local web UI."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from fertiscope.cost import prices_for_tokenizer
from fertiscope.data import flores_sample
from fertiscope.fertility import (
    ConversationReport,
    FertilityReport,
    Turn,
    analyze,
    analyze_conversation,
)
from fertiscope.tokenizers import TOKENIZERS


HERE = Path(__file__).parent
TEMPLATES_DIR = HERE / "templates"
STATIC_DIR = HERE / "static"
INDEX_HTML = TEMPLATES_DIR / "index.html"

app = FastAPI(
    title="FertiScope",
    description="Tokenizer fertility analysis for EN <-> VI (local web UI).",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class AnalyzeRequest(BaseModel):
    en: str = Field(..., min_length=1, description="English baseline text.")
    vi: str = Field(..., min_length=1, description="Vietnamese parallel text.")
    tokenizers: List[str] = Field(
        default_factory=lambda: list(TOKENIZERS.keys()),
        description="Tokenizer ids to run.",
    )


class TurnIn(BaseModel):
    role: str = Field("user", description="system | user | assistant")
    en: str = Field("", description="English text for this turn.")
    vi: str = Field("", description="Vietnamese parallel text for this turn.")


class ConversationRequest(BaseModel):
    turns: List[TurnIn] = Field(..., min_length=1)
    tokenizers: List[str] = Field(default_factory=lambda: list(TOKENIZERS.keys()))


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(INDEX_HTML, media_type="text/html")


@app.get("/api/tokenizers")
def list_tokenizers():
    return {
        "tokenizers": [
            {
                "id": s.id,
                "family": s.family,
                "display_name": s.display_name,
                "notes": s.notes,
            }
            for s in TOKENIZERS.values()
        ]
    }


@app.get("/api/flores-sample")
def get_flores_sample():
    return {
        "en": flores_sample.en_text(),
        "vi": flores_sample.vi_text(),
        "sentence_count": flores_sample.sentence_count(),
    }


def _report_to_dict(report: FertilityReport) -> dict:
    """Serialize FertilityReport to a flat JSON-able dict the frontend can render."""
    price_rows = []
    for price in prices_for_tokenizer(report.tokenizer_id):
        if price.input_per_1m_usd <= 0:
            continue
        price_rows.append(
            {
                "provider": price.provider,
                "model": price.model,
                "input_per_1m_usd": price.input_per_1m_usd,
                "output_per_1m_usd": price.output_per_1m_usd,
                "en_cost_usd": price.input_per_1m_usd * report.en.tokens / 1_000_000,
                "vi_cost_usd": price.input_per_1m_usd * report.vi.tokens / 1_000_000,
                "notes": price.notes,
            }
        )

    return {
        "tokenizer_id": report.tokenizer_id,
        "tokenizer_display": report.tokenizer_display,
        "en": {
            "words": report.en.words,
            "tokens": report.en.tokens,
            "fertility": round(report.en.fertility, 3),
        },
        "vi": {
            "words": report.vi.words,
            "tokens": report.vi.tokens,
            "fertility": round(report.vi.fertility, 3),
        },
        "fertility_ratio": round(report.fertility_ratio, 3),
        "cost_multiplier": round(report.cost_multiplier, 3),
        "prices": price_rows,
        "context": {
            "ctx_4096": {
                "avg_tokens_per_example": round(report.context_4096.avg_tokens_per_example, 1),
                "max_examples": report.context_4096.max_examples,
                "utilization_curve": report.context_4096.utilization_curve,
            },
            "ctx_8192": {
                "avg_tokens_per_example": round(report.context_8192.avg_tokens_per_example, 1),
                "max_examples": report.context_8192.max_examples,
                "utilization_curve": report.context_8192.utilization_curve,
            },
        },
        "notes": report.notes,
    }


@app.post("/api/analyze")
def analyze_endpoint(req: AnalyzeRequest):
    invalid = [t for t in req.tokenizers if t not in TOKENIZERS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"unknown tokenizers: {invalid}")

    reports = []
    errors = []
    for tid in req.tokenizers:
        try:
            r = analyze(req.en, req.vi, tid)
            reports.append(_report_to_dict(r))
        except Exception as exc:
            errors.append({"tokenizer_id": tid, "error": str(exc)})

    return {"reports": reports, "errors": errors}


def _conversation_to_dict(report: ConversationReport) -> dict:
    price_rows = []
    for price in prices_for_tokenizer(report.tokenizer_id):
        if price.input_per_1m_usd <= 0:
            continue
        # Multi-turn cost: every turn re-sends the cumulative history, so
        # total billed input tokens = sum of cumulative_tokens at each turn.
        # We compute both: per-corpus and stateless-API-realistic.
        per_corpus_en = price.input_per_1m_usd * report.total_en_tokens / 1_000_000
        per_corpus_vi = price.input_per_1m_usd * report.total_vi_tokens / 1_000_000
        stateless_en = price.input_per_1m_usd * sum(t.cumulative_en_tokens for t in report.turns) / 1_000_000
        stateless_vi = price.input_per_1m_usd * sum(t.cumulative_vi_tokens for t in report.turns) / 1_000_000
        price_rows.append({
            "provider": price.provider,
            "model": price.model,
            "input_per_1m_usd": price.input_per_1m_usd,
            "per_corpus_en_usd": per_corpus_en,
            "per_corpus_vi_usd": per_corpus_vi,
            "stateless_en_usd": stateless_en,
            "stateless_vi_usd": stateless_vi,
        })

    return {
        "tokenizer_id": report.tokenizer_id,
        "tokenizer_display": report.tokenizer_display,
        "total_en_words": report.total_en_words,
        "total_en_tokens": report.total_en_tokens,
        "total_vi_words": report.total_vi_words,
        "total_vi_tokens": report.total_vi_tokens,
        "fertility_ratio": report.fertility_ratio,
        "first_overflow_turn_4096": report.first_overflow_turn_4096,
        "first_overflow_turn_8192": report.first_overflow_turn_8192,
        "predicted_overflow_turn_4096": report.predicted_overflow_turn_4096,
        "predicted_overflow_turn_8192": report.predicted_overflow_turn_8192,
        "projected_slope_en": report.projected_slope_en,
        "projected_slope_vi": report.projected_slope_vi,
        "projection": [
            {
                "turn_index": p.turn_index,
                "cumulative_en_tokens": p.cumulative_en_tokens,
                "cumulative_vi_tokens": p.cumulative_vi_tokens,
            }
            for p in report.projection
        ],
        "turns": [
            {
                "turn_index": t.turn_index,
                "role": t.role,
                "en_words": t.en_words,
                "en_tokens": t.en_tokens,
                "vi_words": t.vi_words,
                "vi_tokens": t.vi_tokens,
                "cumulative_en_tokens": t.cumulative_en_tokens,
                "cumulative_vi_tokens": t.cumulative_vi_tokens,
                "cumulative_pct_4096": t.cumulative_pct_4096,
                "cumulative_pct_8192": t.cumulative_pct_8192,
            }
            for t in report.turns
        ],
        "prices": price_rows,
    }


@app.post("/api/analyze-conversation")
def analyze_conversation_endpoint(req: ConversationRequest):
    invalid = [t for t in req.tokenizers if t not in TOKENIZERS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"unknown tokenizers: {invalid}")
    # Drop turns where BOTH en and vi are empty
    turns = [Turn(role=t.role, en=t.en, vi=t.vi) for t in req.turns if t.en or t.vi]
    if not turns:
        raise HTTPException(status_code=400, detail="all turns are empty; provide at least one with text")

    reports = []
    errors = []
    for tid in req.tokenizers:
        try:
            r = analyze_conversation(turns, tid)
            reports.append(_conversation_to_dict(r))
        except Exception as exc:
            errors.append({"tokenizer_id": tid, "error": str(exc)})

    return {"reports": reports, "errors": errors}
