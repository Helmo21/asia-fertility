"""Smoke tests for the CLI."""

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
    for sub in [
        "measure",
        "cost",
        "run",
        "reproduce",
        "figures",
        "leaderboard",
        "tokenizers",
        "corpora",
        "languages",
        "niah",
    ]:
        assert sub in r.stdout


def test_languages_list_works() -> None:
    r = runner.invoke(app, ["languages", "list"])
    assert r.exit_code == 0
    # spot-check a few expected isos appear
    for iso in ["eng", "tam", "mya", "vie"]:
        assert iso in r.stdout


def test_tokenizers_list_json_works() -> None:
    import json

    r = runner.invoke(app, ["tokenizers", "list", "--json"])
    assert r.exit_code == 0
    rows = json.loads(r.stdout)
    ids = {row["id"] for row in rows}
    # the three tiktoken tokenizers must always be registered
    assert {"openai/o200k_base", "openai/cl100k_base", "openai/o200k_harmony"} <= ids
