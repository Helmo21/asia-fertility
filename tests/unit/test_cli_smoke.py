"""Smoke tests for the CLI scaffolding."""
from __future__ import annotations

from typer.testing import CliRunner

from asia_fertility import __version__
from asia_fertility.cli import app

runner = CliRunner()


def test_version_flag() -> None:
    r = runner.invoke(app, ["--version"])
    assert r.exit_code == 0
    assert f"asia-fertility {__version__}" in r.stdout


def test_help_lists_subcommands() -> None:
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    for sub in ["measure", "cost", "run", "reproduce", "figures", "leaderboard", "tokenizers", "corpora", "languages", "niah"]:
        assert sub in r.stdout


def test_measure_not_implemented() -> None:
    r = runner.invoke(app, ["measure", "--text", "x"])
    assert r.exit_code == 2


def test_tokenizers_list_not_implemented() -> None:
    r = runner.invoke(app, ["tokenizers", "list"])
    assert r.exit_code == 2
