# SIB-200 + MAFAND-MT corpus loaders

Status: pending
Tags: `corpora`, `sib200`, `mafand`, `cross-corpus-validation`
Depends on: #010, #011, #012
Blocks: #024

## Scope

Add two secondary corpora so the study can demonstrate cross-corpus stability (the afri-fertility Pearson r=0.9998 trick). SIB-200 reuses FLORES sentences with topic labels; MAFAND-MT is included to **demonstrate handling of partial language coverage** even though most Asian languages aren't in it — the `LanguageNotInCorpus` path is what gets tested.

### Files to create

- `src/fertiscope/corpora/sib200.py`
- `src/fertiscope/corpora/mafand.py`
- `tests/unit/test_corpora_sib200.py`
- `tests/unit/test_corpora_mafand.py`
- `tests/integration/test_corpora_sib200_live.py`

### Files to modify

- `src/fertiscope/corpora/__init__.py` — import for registration side effects.

### Interface and contract

`sib200.py` (mirrors `flores.py` shape):

```python
from __future__ import annotations
from typing import Iterator
import os
from pathlib import Path
from .base import Sentence
from .registry import register
from .exceptions import LanguageNotInCorpus, CorpusUnavailable
from fertiscope.languages import get_language

CACHE_DIR = Path(os.environ.get("FERTISCOPE_CACHE_DIR", str(Path.home() / ".cache" / "fertiscope" / "corpora")))


class Sib200Corpus:
    name = "sib200"

    def __init__(self) -> None:
        try:
            from datasets import load_dataset, get_dataset_config_names    # type: ignore
        except ImportError as e:
            raise CorpusUnavailable("sib200", f"missing extra 'hf': {e}") from e
        self._load_dataset = load_dataset
        self._configs = set(get_dataset_config_names("Davlan/sib200"))
        from fertiscope.languages import load_languages
        self.languages = [l.iso for l in load_languages() if l.flores_tag in self._configs]

    def _tag(self, lang: str) -> str:
        try:
            tag = get_language(lang).flores_tag
        except KeyError as e:
            raise LanguageNotInCorpus(f"SIB-200 does not cover language '{lang}'") from e
        if tag not in self._configs:
            raise LanguageNotInCorpus(f"SIB-200 does not cover language '{lang}' (no config {tag})")
        return tag

    def iter_sentences(self, lang: str, limit: int | None = None) -> Iterator[Sentence]:
        tag = self._tag(lang)
        ds = self._load_dataset("Davlan/sib200", tag, split="test", cache_dir=str(CACHE_DIR))
        for idx, row in enumerate(ds):
            if limit is not None and idx >= limit:
                return
            yield Sentence(
                id=f"sib200:test:{idx}",
                lang=lang,
                text=row["text"],
                meta={"flores_tag": tag, "topic": str(row.get("category", ""))},
            )

    def parallel_pairs(self, lang_a: str, lang_b: str, limit: int | None = None):
        a = list(self.iter_sentences(lang_a, limit))
        b = list(self.iter_sentences(lang_b, limit))
        assert len(a) == len(b), "SIB-200 split misalignment"
        yield from zip(a, b, strict=True)


register("sib200", Sib200Corpus)
```

`mafand.py`:

```python
from __future__ import annotations
from typing import Iterator
import os
from pathlib import Path
from .base import Sentence
from .registry import register
from .exceptions import LanguageNotInCorpus, CorpusUnavailable

CACHE_DIR = Path(os.environ.get("FERTISCOPE_CACHE_DIR", str(Path.home() / ".cache" / "fertiscope" / "corpora")))

# MAFAND-MT pairs (en-X). None of the 15 Asian study languages are covered.
# We register the corpus so users can see it in `corpora list`, but every Asian iso raises LanguageNotInCorpus.
_MAFAND_AVAILABLE_PAIRS = {
    "en-hau", "en-ibo", "en-yor", "en-zul", "en-amh", "en-twi", "en-pcm",
    "en-lug", "en-bam", "en-ewe", "en-fon", "en-kin", "en-lin", "en-nya",
    "en-sna", "en-swh", "en-tsn", "en-wol", "en-xho",
}


class MafandCorpus:
    name = "mafand"
    languages: list[str] = []   # No Asian languages in scope; populated empty

    def __init__(self) -> None:
        try:
            from datasets import load_dataset    # type: ignore
        except ImportError as e:
            raise CorpusUnavailable("mafand", f"missing extra 'hf': {e}") from e
        self._load_dataset = load_dataset

    def iter_sentences(self, lang: str, limit: int | None = None) -> Iterator[Sentence]:
        raise LanguageNotInCorpus(
            f"MAFAND-MT covers African languages only; '{lang}' is not in coverage. "
            "Use 'flores' or 'sib200' for Asian languages."
        )

    def parallel_pairs(self, lang_a: str, lang_b: str, limit: int | None = None):
        raise LanguageNotInCorpus(
            f"MAFAND-MT covers African languages only; pair ('{lang_a}', '{lang_b}') not available."
        )


register("mafand", MafandCorpus)
```

`tests/unit/test_corpora_sib200.py`: same shape as the flores tests — mocked datasets, asserts registration + unknown-language error.

`tests/unit/test_corpora_mafand.py`:

```python
import pytest
from fertiscope.corpora import load_corpus, LanguageNotInCorpus

def test_mafand_registered():
    from fertiscope.corpora import list_corpora
    assert "mafand" in list_corpora()

def test_mafand_raises_for_asian_language():
    m = load_corpus("mafand")
    with pytest.raises(LanguageNotInCorpus, match="African languages only"):
        list(m.iter_sentences("tam"))

def test_mafand_raises_for_pair():
    m = load_corpus("mafand")
    with pytest.raises(LanguageNotInCorpus):
        list(m.parallel_pairs("eng", "tam"))
```

`tests/integration/test_corpora_sib200_live.py`:

```python
import pytest
from fertiscope.corpora import load_corpus

pytestmark = [pytest.mark.slow, pytest.mark.integration]

def test_sib200_loads_tamil():
    sib = load_corpus("sib200")
    sents = list(sib.iter_sentences("tam", limit=5))
    assert len(sents) == 5
    assert all(s.text for s in sents)
```

### Notes

- SIB-200 reuses FLORES sentences. The `text` field name differs (`text` vs FLORES's `sentence`) — that's a HF dataset convention difference, handled in the loader.
- The `topic` field (SIB-200's category label: science, travel, sports, …) is preserved in `meta` so future analysis can filter by topic.
- MAFAND-MT existing in the registry — even with zero Asian coverage — is the **honest** way to document the architecture's portability. The same package works for African languages; users just need the right corpus. The afri-fertility project would `register("mafand", ...)` with a real loader.
- Do NOT pretend MAFAND covers Asian languages by silently returning empty. The `LanguageNotInCorpus` raise IS the correct behavior.
- Cross-corpus validation (Pearson r between FLORES and SIB-200 leaderboards) is computed in #033 / report.

## Acceptance Criteria

- [ ] `"sib200" in list_corpora()` and `"mafand" in list_corpora()`.
- [ ] `Sib200Corpus.name == "sib200"`, `MafandCorpus.name == "mafand"`.
- [ ] `MafandCorpus().iter_sentences("tam")` raises `LanguageNotInCorpus`.
- [ ] `Sib200Corpus().iter_sentences("xyz")` raises `LanguageNotInCorpus`.
- [ ] Without `[hf]` extra: both raise `CorpusUnavailable` mentioning extra `'hf'`.
- [ ] Integration test loads ≥ 5 Tamil sentences from SIB-200 with a `topic` field in `meta`.
- [ ] Unit tests for both loaders pass without network.
- [ ] `mypy --strict src/fertiscope/corpora/sib200.py src/fertiscope/corpora/mafand.py` passes.

## User Stories

### Story: Cross-corpus validation in the v2 paper

1. Author runs `fertiscope run --config configs/study_main.yaml` with both `flores` and `sib200`.
2. Output rows include corpus column.
3. Author computes per-tokenizer Pearson `r` of premium between corpora → r > 0.99.
4. Adds to paper §4 as "results are corpus-independent".

### Story: Honest empty-set for African languages

1. African-language researcher tries `fertiscope run --config configs/study_african.yaml --corpora mafand`.
2. Runner catches `LanguageNotInCorpus` per row, emits skip rows.
3. Researcher knows clearly: "fertiscope doesn't ship African data; use afri-fertility for African coverage".

---

Blocked by: #010, #011, #012
