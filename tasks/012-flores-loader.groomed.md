# FLORES-200 corpus loader

Status: pending
Tags: `corpora`, `flores`, `huggingface-datasets`, `parallel-corpus`
Depends on: #010, #011
Blocks: #019, #024

## Scope

Wire FLORES-200 (Meta NLLB) as the primary parallel corpus via HuggingFace `datasets`. Cache to `~/.cache/fertiscope/corpora/`, expose `dev` (997 sentences) and `devtest` (1012 sentences) splits, and return `Sentence` objects whose IDs match the documented schema.

### Files to create

- `src/fertiscope/corpora/flores.py`
- `tests/unit/test_corpora_flores.py`
- `tests/integration/test_corpora_flores_live.py` (marked `slow + integration`)

### Files to modify

- `src/fertiscope/corpora/__init__.py` — import flores module for registration side effect.

### Interface and contract

`src/fertiscope/corpora/flores.py`:

```python
from __future__ import annotations
from typing import Iterator, Literal
from pathlib import Path
import os

from .base import Sentence
from .registry import register
from .exceptions import LanguageNotInCorpus, CorpusUnavailable
from fertiscope.languages import get_language

Split = Literal["dev", "devtest"]

CACHE_DIR = Path(os.environ.get("FERTISCOPE_CACHE_DIR", str(Path.home() / ".cache" / "fertiscope" / "corpora")))


class FloresCorpus:
    name = "flores"

    def __init__(self, split: Split = "dev") -> None:
        try:
            from datasets import load_dataset, get_dataset_config_names    # type: ignore
        except ImportError as e:
            raise CorpusUnavailable("flores", f"missing extra 'hf': {e}") from e
        self._split = split
        self._load_dataset = load_dataset
        self._configs = set(get_dataset_config_names("facebook/flores"))
        # languages property is derived from the 16-language registry
        self.languages = [l.iso for l in self._available_languages()]

    def _available_languages(self):
        from fertiscope.languages import load_languages
        return [l for l in load_languages() if l.flores_tag in self._configs]

    def _flores_tag(self, lang: str) -> str:
        try:
            return get_language(lang).flores_tag
        except KeyError as e:
            raise LanguageNotInCorpus(f"FLORES does not cover language '{lang}'") from e

    def iter_sentences(self, lang: str, limit: int | None = None) -> Iterator[Sentence]:
        tag = self._flores_tag(lang)
        ds = self._load_dataset(
            "facebook/flores", tag, split=self._split,
            cache_dir=str(CACHE_DIR),
        )
        for idx, row in enumerate(ds):
            if limit is not None and idx >= limit:
                return
            yield Sentence(
                id=f"flores:{self._split}:{idx}",
                lang=lang,
                text=row["sentence"],
                meta={"flores_tag": tag},
            )

    def parallel_pairs(self, lang_a: str, lang_b: str, limit: int | None = None):
        a = list(self.iter_sentences(lang_a, limit))
        b = list(self.iter_sentences(lang_b, limit))
        assert len(a) == len(b), "FLORES split misalignment — datasets bug or stale cache"
        yield from zip(a, b, strict=True)


def _loader(split: Split = "dev") -> FloresCorpus:
    return FloresCorpus(split=split)


register("flores", _loader)
```

`tests/unit/test_corpora_flores.py` (mocked, no network):

```python
import pytest
from fertiscope.corpora import load_corpus, LanguageNotInCorpus

def test_flores_registered():
    from fertiscope.corpora import list_corpora
    assert "flores" in list_corpora()

def test_flores_unknown_language(monkeypatch):
    # Mock datasets to return empty configs
    import sys
    fake_datasets = type(sys)("datasets")
    fake_datasets.get_dataset_config_names = lambda repo: ["eng_Latn", "tam_Taml"]
    fake_datasets.load_dataset = lambda *a, **kw: []
    monkeypatch.setitem(sys.modules, "datasets", fake_datasets)
    flores = load_corpus("flores")
    with pytest.raises(LanguageNotInCorpus):
        list(flores.iter_sentences("xyz"))
```

`tests/integration/test_corpora_flores_live.py`:

```python
import pytest
from fertiscope.corpora import load_corpus

pytestmark = [pytest.mark.slow, pytest.mark.integration]

def test_flores_loads_tamil_dev():
    flores = load_corpus("flores", split="dev")
    sents = list(flores.iter_sentences("tam", limit=10))
    assert len(sents) == 10
    assert all(s.lang == "tam" for s in sents)
    assert all(s.id.startswith("flores:dev:") for s in sents)
    assert all(s.text for s in sents)            # no empty strings

def test_flores_parallel_alignment():
    flores = load_corpus("flores", split="dev")
    pairs = list(flores.parallel_pairs("eng", "tam", limit=5))
    assert len(pairs) == 5
    for eng_s, tam_s in pairs:
        assert eng_s.lang == "eng"
        assert tam_s.lang == "tam"
        # IDs share the same trailing index
        assert eng_s.id.split(":")[-1] == tam_s.id.split(":")[-1]
```

### Notes

- **HuggingFace caches datasets at `cache_dir`** — we override to keep them under `~/.cache/fertiscope/` so users can clear them independently.
- The `facebook/flores` config names are `<iso>_<Script>` (e.g. `eng_Latn`, `tam_Taml`). This is the `flores_tag` field from `languages.yaml`.
- FLORES is **deterministic** — sentence at index N is always the same meaning across configs. This is what makes parallel pairs work.
- `parallel_pairs` uses `strict=True` because misalignment is a serious bug, not something to silently skip.
- The integration test marker means CI skips it by default; release scripts run it explicitly.
- `streaming=True` is NOT used for FLORES because the dev split is small (< 200KB) and seekable downloads beat streaming for small data.

## Acceptance Criteria

- [ ] `from fertiscope.corpora import load_corpus; load_corpus("flores")` returns a `FloresCorpus`.
- [ ] `"flores" in list_corpora()` is True.
- [ ] `FloresCorpus.name == "flores"`.
- [ ] Without `[hf]` extra: `load_corpus("flores")` raises `CorpusUnavailable` mentioning extra `'hf'`.
- [ ] `iter_sentences("xyz")` (unknown lang) raises `LanguageNotInCorpus`.
- [ ] Mocked-datasets unit test passes.
- [ ] Integration test (with `[hf]` + network) loads 10 Tamil dev sentences and 5 parallel eng↔tam pairs with aligned indices.
- [ ] Cache directory respects `FERTISCOPE_CACHE_DIR` env var.
- [ ] `mypy --strict src/fertiscope/corpora/flores.py` passes.

## User Stories

### Story: Researcher iterates over Tamil FLORES

1. `flores = load_corpus("flores")`.
2. `for s in flores.iter_sentences("tam", limit=50): print(s.text)`.
3. Gets 50 Tamil sentences with stable IDs `flores:dev:0` … `flores:dev:49`.

### Story: Researcher pairs English with Tamil

1. `pairs = flores.parallel_pairs("eng", "tam", limit=997)`.
2. Iterates `(eng, tam)` tuples, same content, different language.
3. Uses the pairs to compute the premium.

### Story: Cache survives reinstall

1. User runs Flores once, downloads ~1MB to `~/.cache/fertiscope/corpora/`.
2. Uninstalls and reinstalls fertiscope.
3. Reruns; uses cache. Zero network on second run.

---

Blocked by: #010, #011
