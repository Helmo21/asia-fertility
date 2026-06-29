# Custom JSONL/CSV loader + bundled offline reference suite

Status: pending
Tags: `corpora`, `custom`, `jsonl`, `csv`, `offline`, `reference-suite`
Depends on: #010, #011
Blocks: #026

## Scope

Two deliverables tied at the hip:

1. A `custom` corpus loader that accepts user-supplied JSONL or CSV files (their own product copy, scraped news, etc.).
2. A bundled **`data/reference_suite/reference.jsonl`** of 10 parallel sentences × 7 languages that `fertiscope reproduce` (#026) uses for the no-network credibility demo.

### Files to create

- `src/fertiscope/corpora/custom.py`
- `src/fertiscope/data/reference_suite/reference.jsonl` — **bundled with the package**.
- `src/fertiscope/data/reference_suite/README.md` — describes provenance and license.
- `tests/unit/test_corpora_custom.py`
- `tests/unit/fixtures/sample.jsonl`
- `tests/unit/fixtures/sample.csv`

### Files to modify

- `src/fertiscope/corpora/__init__.py` — import for registration.
- `pyproject.toml` `[tool.hatch.build.targets.wheel]` — confirm `data/reference_suite/` is included.

### Interface and contract

`src/fertiscope/corpora/custom.py`:

```python
from __future__ import annotations
import csv, json
from pathlib import Path
from typing import Iterator
from .base import Sentence
from .registry import register
from .exceptions import LanguageNotInCorpus


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
        raise ValueError(f"Cannot detect format from suffix '{suffix}'. Pass format='jsonl' or 'csv' explicitly.")

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
                    raise ValueError(f"Invalid JSON at line {line_no} of {self._path}: {e}") from e
                self._validate_row(row, line_no)
                sid = row.get("id") or f"custom:{self._path.stem}:{line_no}"
                s = Sentence(id=sid, lang=row["lang"], text=row["text"], meta={k: str(v) for k, v in row.items() if k not in {"id", "lang", "text"}})
                self._index_by_lang.setdefault(s.lang, []).append(s)

    def _load_csv(self) -> None:
        with self._path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, 1):
                self._validate_row(row, i)
                sid = row.get("id") or f"custom:{self._path.stem}:{i}"
                s = Sentence(id=sid, lang=row["lang"], text=row["text"], meta={k: row[k] for k in row if k not in {"id", "lang", "text"}})
                self._index_by_lang.setdefault(s.lang, []).append(s)

    def _validate_row(self, row: dict, line_no: int) -> None:
        for key in ("lang", "text"):
            if key not in row or row[key] in ("", None):
                raise ValueError(f"Row {line_no}: missing required field '{key}'")

    def iter_sentences(self, lang: str, limit: int | None = None) -> Iterator[Sentence]:
        if lang not in self._index_by_lang:
            raise LanguageNotInCorpus(f"Language '{lang}' not in {self._path}. Available: {self.languages}")
        items = self._index_by_lang[lang]
        return iter(items if limit is None else items[:limit])

    def parallel_pairs(self, lang_a: str, lang_b: str, limit: int | None = None):
        a = list(self.iter_sentences(lang_a, limit))
        b = list(self.iter_sentences(lang_b, limit))
        if len(a) != len(b):
            # Try to align by ID if present
            a_by_id = {s.id: s for s in a}
            b_by_id = {s.id: s for s in b}
            common = sorted(set(a_by_id) & set(b_by_id))
            if len(common) >= max(1, (limit or 0)):
                yield from ((a_by_id[k], b_by_id[k]) for k in common[:limit])
                return
            raise ValueError(f"Custom corpus: lang counts differ ({len(a)} vs {len(b)}) and IDs do not align.")
        yield from zip(a, b, strict=True)


def _loader(path: str | Path, format: str | None = None) -> CustomCorpus:
    return CustomCorpus(path=path, format=format)


register("custom", _loader)
```

`src/fertiscope/data/reference_suite/reference.jsonl` — 10 sentences × 7 languages = 70 entries. Languages: `eng`, `vie`, `ind`, `tha`, `hin`, `tam`, `mya`. Use **FLORES-200 dev** sentences indices 0-9 (CC-BY-SA 4.0; preserve attribution in README). One line per row:

```jsonl
{"id":"ref:0","lang":"eng","text":"<flores eng_Latn dev sentence 0>"}
{"id":"ref:0","lang":"vie","text":"<flores vie_Latn dev sentence 0>"}
{"id":"ref:0","lang":"ind","text":"<flores ind_Latn dev sentence 0>"}
{"id":"ref:0","lang":"tha","text":"<flores tha_Thai dev sentence 0>"}
{"id":"ref:0","lang":"hin","text":"<flores hin_Deva dev sentence 0>"}
{"id":"ref:0","lang":"tam","text":"<flores tam_Taml dev sentence 0>"}
{"id":"ref:0","lang":"mya","text":"<flores mya_Mymr dev sentence 0>"}
{"id":"ref:1","lang":"eng","text":"..."}
...
```

Implementer pulls the actual text from FLORES once with `[hf]` extra installed, then commits the bundled JSONL. After that, `fertiscope reproduce` works **completely offline**.

`src/fertiscope/data/reference_suite/README.md`:

```markdown
# Reference Suite

10 parallel sentences (FLORES-200 dev split, indices 0–9) in 7 languages:
English, Vietnamese, Indonesian, Thai, Hindi, Tamil, Burmese.

**Source**: FLORES-200, Meta NLLB project, https://huggingface.co/datasets/facebook/flores
**License**: CC-BY-SA 4.0
**Used for**: `fertiscope reproduce` — the no-network credibility demo.

To regenerate: `python scripts/regenerate_reference_suite.py` (requires `[hf]` extra).
```

`tests/unit/test_corpora_custom.py`:

```python
import json, pytest
from pathlib import Path
from fertiscope.corpora import load_corpus, LanguageNotInCorpus

FIXTURES = Path(__file__).parent / "fixtures"

def test_jsonl_loads():
    corpus = load_corpus("custom", path=FIXTURES / "sample.jsonl")
    assert "eng" in corpus.languages and "vie" in corpus.languages
    sents = list(corpus.iter_sentences("eng"))
    assert len(sents) >= 1
    assert sents[0].lang == "eng"

def test_csv_loads():
    corpus = load_corpus("custom", path=FIXTURES / "sample.csv")
    assert "vie" in corpus.languages

def test_missing_field_rejected(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"text": "no lang"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="missing required field 'lang'"):
        load_corpus("custom", path=bad)

def test_unknown_lang(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text('{"lang":"eng","text":"hi"}\n', encoding="utf-8")
    corpus = load_corpus("custom", path=p)
    with pytest.raises(LanguageNotInCorpus):
        list(corpus.iter_sentences("xyz"))

def test_parallel_pairs_by_id_alignment(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text(
        '{"id":"a1","lang":"eng","text":"hi"}\n'
        '{"id":"a1","lang":"vie","text":"chào"}\n'
        '{"id":"a2","lang":"eng","text":"bye"}\n'
        '{"id":"a2","lang":"vie","text":"tạm biệt"}\n',
        encoding="utf-8",
    )
    corpus = load_corpus("custom", path=p)
    pairs = list(corpus.parallel_pairs("eng", "vie"))
    assert len(pairs) == 2

def test_reference_suite_bundled():
    """The bundled reference suite must load offline via importlib.resources."""
    from importlib.resources import files
    path = files("fertiscope.data.reference_suite").joinpath("reference.jsonl")
    text = path.read_text("utf-8")
    rows = [json.loads(l) for l in text.splitlines() if l.strip()]
    assert len(rows) == 70   # 10 sentences × 7 languages
    langs = {r["lang"] for r in rows}
    assert langs == {"eng", "vie", "ind", "tha", "hin", "tam", "mya"}
```

`tests/unit/fixtures/sample.jsonl`:

```jsonl
{"id":"s1","lang":"eng","text":"hello world"}
{"id":"s1","lang":"vie","text":"chào thế giới"}
{"id":"s2","lang":"eng","text":"good night"}
{"id":"s2","lang":"vie","text":"chúc ngủ ngon"}
```

`tests/unit/fixtures/sample.csv`:

```csv
id,lang,text
s1,vie,chào thế giới
s2,vie,chúc ngủ ngon
```

### Notes

- JSONL is the canonical format. CSV is for users coming from spreadsheets; convert to JSONL internally where useful.
- Parallel-pairs ID-alignment is a UX nicety: if counts differ but IDs match, we align by ID. This handles "user dropped a few sentences from one language" gracefully.
- The bundled reference suite is **70 short sentences ≈ 30KB** — small enough to bundle, large enough to compute meaningful fertility numbers.
- DO commit the actual sentences. DO NOT leave placeholders.
- `importlib.resources.files(...)` ensures the bundled JSONL is readable from a wheel install too (not just editable installs).

## Acceptance Criteria

- [ ] `load_corpus("custom", path="x.jsonl")` and `load_corpus("custom", path="x.csv")` both work on the fixtures.
- [ ] `load_corpus("custom", path="missing.jsonl")` raises `FileNotFoundError`.
- [ ] A row missing `lang` or `text` raises `ValueError` with line number.
- [ ] `iter_sentences("unknown_lang")` raises `LanguageNotInCorpus` listing available languages.
- [ ] `parallel_pairs` falls back to ID-alignment when counts differ but IDs match.
- [ ] `src/fertiscope/data/reference_suite/reference.jsonl` exists with **exactly 70 lines** (10 × 7).
- [ ] All 7 unit tests in `test_corpora_custom.py` pass.
- [ ] The bundled JSONL is readable via `importlib.resources` (works in a wheel install).
- [ ] The wheel built by #002 includes `data/reference_suite/reference.jsonl` (verify with `unzip -l dist/*.whl | grep reference`).
- [ ] `mypy --strict src/fertiscope/corpora/custom.py` passes.

## User Stories

### Story: Vietnamese SaaS team measures their own copy

1. Team exports product strings: `vi_strings.jsonl` with `{"lang":"vie","text":"..."}` per line.
2. Runs `fertiscope measure --corpus custom --path vi_strings.jsonl --tokenizer openai/o200k_base`.
3. Sees fertility on their actual content.

### Story: Reproduce demo runs offline

1. CI box has no internet.
2. `fertiscope reproduce` reads `importlib.resources` → bundled JSONL.
3. Computes fertility/cost on 70 sentences across 7 languages.
4. Outputs in 20 seconds. No flakes.

### Story: ID-aligned parallel custom corpus

1. User has `en.jsonl` and `vi.jsonl` with matching IDs.
2. Concatenates them, runs `fertiscope measure --corpus custom`.
3. Pairs are aligned by ID.

---

Blocked by: #010, #011
