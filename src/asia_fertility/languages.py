"""16-language registry loaded from data/languages.yaml."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Literal

import yaml

Script = Literal[
    "Latn", "Thai", "Deva", "Beng", "Sinh",
    "Taml", "Telu", "Knda", "Mlym",
    "Mymr", "Khmr", "Laoo",
]


@dataclass(frozen=True)
class Language:
    iso: str
    name: str
    script: Script
    family: str
    flores_tag: str
    spaceless: bool
    notes: str = ""


@lru_cache(maxsize=1)
def load_languages() -> list[Language]:
    raw_text = files("asia_fertility.data").joinpath("languages.yaml").read_text("utf-8")
    raw = yaml.safe_load(raw_text)
    return [Language(**item) for item in raw["languages"]]


def get_language(iso: str) -> Language:
    for lang in load_languages():
        if lang.iso == iso:
            return lang
    raise KeyError(f"Unknown language iso '{iso}'. Known: {[l.iso for l in load_languages()]}")


def list_isos() -> list[str]:
    return [l.iso for l in load_languages()]
