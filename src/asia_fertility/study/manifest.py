"""Manifest builder with SHA256 hashes for reproducibility."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from asia_fertility import __version__
from asia_fertility.cost.fx import fx_sha256
from asia_fertility.cost.prices import prices_sha256

if TYPE_CHECKING:
    from asia_fertility.config import StudyConfig


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tokenizer_versions(tokenizer_ids: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for tid in tokenizer_ids:
        if tid.startswith("openai/"):
            try:
                import tiktoken  # type: ignore
                out[tid] = f"tiktoken=={tiktoken.__version__}"
            except ImportError:
                out[tid] = "tiktoken=missing"
        elif tid.startswith("anthropic/"):
            try:
                import anthropic  # type: ignore
                out[tid] = f"anthropic=={anthropic.__version__}"
            except ImportError:
                out[tid] = "anthropic=missing"
        elif tid.startswith("google/gemini"):
            out[tid] = "google-genai"
        else:
            try:
                import transformers  # type: ignore
                out[tid] = f"transformers=={transformers.__version__}"
            except ImportError:
                out[tid] = "transformers=missing"
    return out


def build_manifest(cfg: "StudyConfig", *, n_rows: int) -> dict:
    cfg_json = cfg.model_dump_json()
    return {
        "schema_version": "1.0",
        "package_version": __version__,
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "config_sha256": _sha256_text(cfg_json),
        "config": json.loads(cfg_json),
        "prices_sha256": prices_sha256(),
        "fx_sha256": fx_sha256(),
        "tokenizer_versions": _tokenizer_versions(cfg.tokenizers),
        "n_rows": n_rows,
        "host": {
            "os": platform.system(),
            "os_release": platform.release(),
            "python": sys.version.split()[0],
            "machine": platform.machine(),
        },
    }
