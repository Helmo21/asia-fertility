"""Custom JSONL/CSV loader + bundled offline reference suite path."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterator

from .base import Sentence
from .exceptions import LanguageNotInCorpus
from .registry import register


class CustomCorpus:
    name = "custom"

    def __init__(self, path: str | Path, format: str | None = None) -> None:
        self._path = Path(path)
        if not self._path.exists():
            raise FileNotFoundError(f"Corpus file not found: {self._path}")
        self._format = format or self._detect_format()
        self._index_by_lang: dict[str, list[Sentence]] = {}
        self._load()
        self.languages = sorted(self._index_by_lang)

    def _detect_format(self) -> str:
        suffix = self._path.suffix.lower()
        if suffix == ".jsonl":
            return "jsonl"
        if suffix == ".csv":
            return "csv"
        raise ValueError(f"Cannot detect format from suffix '{suffix}'.")

    def _load(self) -> None:
        if self._format == "jsonl":
            self._load_jsonl()
        else:
            self._load_csv()

    def _load_jsonl(self) -> None:
        with self._path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON at line {line_no}: {e}") from e
                self._validate_row(row, line_no)
                sid = row.get("id") or f"custom:{self._path.stem}:{line_no}"
                meta = {k: str(v) for k, v in row.items() if k not in {"id", "lang", "text"}}
                s = Sentence(id=sid, lang=row["lang"], text=row["text"], meta=meta)
                self._index_by_lang.setdefault(s.lang, []).append(s)

    def _load_csv(self) -> None:
        with self._path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, 1):
                self._validate_row(row, i)
                sid = row.get("id") or f"custom:{self._path.stem}:{i}"
                meta = {k: row[k] for k in row if k not in {"id", "lang", "text"} and row[k]}
                s = Sentence(id=sid, lang=row["lang"], text=row["text"], meta=meta)
                self._index_by_lang.setdefault(s.lang, []).append(s)

    @staticmethod
    def _validate_row(row: dict, line_no: int) -> None:
        for key in ("lang", "text"):
            if key not in row or row[key] in ("", None):
                raise ValueError(f"Row {line_no}: missing required field '{key}'")

    def iter_sentences(self, lang: str, limit: int | None = None) -> Iterator[Sentence]:
        if lang not in self._index_by_lang:
            raise LanguageNotInCorpus(
                f"Language '{lang}' not in {self._path}. Available: {self.languages}"
            )
        items = self._index_by_lang[lang]
        return iter(items if limit is None else items[:limit])

    def parallel_pairs(
        self, lang_a: str, lang_b: str, limit: int | None = None
    ) -> Iterator[tuple[Sentence, Sentence]]:
        a = list(self.iter_sentences(lang_a, limit))
        b = list(self.iter_sentences(lang_b, limit))
        if len(a) != len(b):
            a_by_id = {s.id: s for s in a}
            b_by_id = {s.id: s for s in b}
            common = sorted(set(a_by_id) & set(b_by_id))
            if not common:
                raise ValueError(
                    f"Custom corpus: counts differ ({len(a)} vs {len(b)}) and IDs do not align."
                )
            pairs = [(a_by_id[k], b_by_id[k]) for k in common]
            yield from (pairs[:limit] if limit else pairs)
            return
        yield from zip(a, b, strict=True)


def _loader(path: str | Path, format: str | None = None) -> CustomCorpus:
    return CustomCorpus(path=path, format=format)


register("custom", _loader)
