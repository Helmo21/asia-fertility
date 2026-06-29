"""v0.3.1: CLI checks OPENROUTER_API_KEY before the cost-estimate prompt."""

from __future__ import annotations

from typer.testing import CliRunner

from asia_fertility.cli import app

runner = CliRunner()


def test_latency_run_bails_early_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    # Write a minimal config so YAML loading succeeds (but we should never reach it)
    cfg = tmp_path / "lat.yaml"
    cfg.write_text(
        "name: t\nlanguages: [eng]\nmodels: [openai/gpt-4o-mini]\nn_warmup: 1\nn_trials: 1\n",
        encoding="utf-8",
    )
    r = runner.invoke(app, ["latency", "run", "--config", str(cfg), "--yes"])
    assert r.exit_code == 2
    # User sees the actionable hint, not a stack trace
    assert "OPENROUTER_API_KEY not set" in r.output
    # Importantly: no cost-estimate / no confirmation prompt before the bail
    assert "Estimated cost" not in r.output
    assert "Proceed?" not in r.output


def test_niah_run_bails_early_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    cfg = tmp_path / "niah.yaml"
    cfg.write_text(
        "name: t\nlanguages: [eng]\nmodels: [openai/gpt-4o-mini]\n"
        "fill_targets: [4096]\npositions: [0.5]\ntrials: 1\n",
        encoding="utf-8",
    )
    r = runner.invoke(app, ["niah", "run", "--config", str(cfg), "--yes"])
    assert r.exit_code == 2
    assert "OPENROUTER_API_KEY not set" in r.output
    assert "Estimated cost" not in r.output
