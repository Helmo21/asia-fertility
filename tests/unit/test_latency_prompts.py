"""Tests for asia_fertility.latency.prompts."""

from __future__ import annotations

import pytest

from asia_fertility.latency.prompts import build_prompts


def test_build_prompts_returns_distinct():
    prompts = build_prompts("eng", n_total=10)
    assert len(prompts) == 10
    # Every prompt is unique (no two trials are identical → prefix cache cannot apply)
    assert len(set(prompts)) == 10


def test_build_prompts_includes_instruction():
    prompts = build_prompts("eng", n_total=2)
    for p in prompts:
        assert "Summarize" in p
        assert p.strip().endswith("sentence.")


def test_build_prompts_target_language_content():
    """Tamil prompts contain Tamil glyphs; English prompts don't."""
    eng = build_prompts("eng", n_total=3)
    tam = build_prompts("tam", n_total=3)
    # Tamil Unicode block is U+0B80–U+0BFF
    assert any(any("\u0b80" <= c <= "\u0bff" for c in p) for p in tam)
    assert not any(any("\u0b80" <= c <= "\u0bff" for c in p) for p in eng)


def test_build_prompts_raises_when_corpus_too_small():
    with pytest.raises(ValueError, match="need 999999"):
        build_prompts("eng", n_total=999_999)
