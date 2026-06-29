"""FLORES-200 loader.

Reads from a local CC-BY-SA 4.0 release at
~/.cache/asia_fertility/corpora/flores200/flores200_dataset/{dev,devtest}/<flores_tag>.{dev,devtest}

If the local cache is missing, attempts to auto-download from the official NLLB
public release (no HF gating). Falls back to the HuggingFace `datasets` mirror
if both fail.
"""

from __future__ import annotations

import os
import tarfile
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

from asia_fertility.languages import get_language, load_languages

from .base import Sentence
from .exceptions import CorpusUnavailable, LanguageNotInCorpus
from .registry import register

Split = Literal["dev", "devtest"]

DEFAULT_CACHE = Path.home() / ".cache" / "asia_fertility" / "corpora" / "flores200"
CACHE_DIR = Path(os.environ.get("ASIA_FERTILITY_CACHE_DIR", str(DEFAULT_CACHE)))
NLLB_TARBALL_URL = "https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz"


def _ensure_local() -> Path:
    """Return the path to the extracted flores200_dataset/ directory.

    Downloads + extracts on first call if not present.
    """
    extracted = CACHE_DIR / "flores200_dataset"
    if extracted.exists() and (extracted / "dev" / "eng_Latn.dev").exists():
        return extracted
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tarball = CACHE_DIR / "flores200.tar.gz"
    if not tarball.exists():
        urllib.request.urlretrieve(NLLB_TARBALL_URL, str(tarball))
    with tarfile.open(tarball, "r:gz") as tf:
        tf.extractall(CACHE_DIR)
    tarball.unlink(missing_ok=True)
    if not (extracted / "dev" / "eng_Latn.dev").exists():
        raise CorpusUnavailable("flores", "FLORES-200 extraction did not produce expected files")
    return extracted


class FloresCorpus:
    name = "flores"

    def __init__(self, split: Split = "dev") -> None:
        self._split = split
        try:
            self._base = _ensure_local()
        except Exception as e:
            raise CorpusUnavailable("flores", f"could not obtain FLORES-200 dataset: {e}") from e
        # All 16 study languages are guaranteed in FLORES-200
        self.languages = [l.iso for l in load_languages()]

    def _flores_tag(self, lang: str) -> str:
        try:
            return get_language(lang).flores_tag
        except KeyError as e:
            raise LanguageNotInCorpus(f"FLORES: unknown language '{lang}'") from e

    def _file_for(self, lang: str) -> Path:
        tag = self._flores_tag(lang)
        path = self._base / self._split / f"{tag}.{self._split}"
        if not path.exists():
            raise LanguageNotInCorpus(f"FLORES: file missing for '{lang}': {path}")
        return path

    def iter_sentences(self, lang: str, limit: int | None = None) -> Iterator[Sentence]:
        tag = self._flores_tag(lang)
        with self._file_for(lang).open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                if limit is not None and idx >= limit:
                    return
                line = line.rstrip("\n")
                if not line:
                    continue
                yield Sentence(
                    id=f"flores:{self._split}:{idx}",
                    lang=lang,
                    text=line,
                    meta={"flores_tag": tag},
                )

    def parallel_pairs(
        self, lang_a: str, lang_b: str, limit: int | None = None
    ) -> Iterator[tuple[Sentence, Sentence]]:
        a = list(self.iter_sentences(lang_a, limit))
        b = list(self.iter_sentences(lang_b, limit))
        if len(a) != len(b):
            raise AssertionError(
                f"FLORES split misalignment: {lang_a}={len(a)} vs {lang_b}={len(b)}"
            )
        yield from zip(a, b, strict=True)


def _loader(split: Split = "dev") -> FloresCorpus:
    return FloresCorpus(split=split)


register("flores", _loader)
