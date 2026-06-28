# Corpus Protocol + Sentence dataclass + registry

Status: pending
Tags: `corpora`, `protocol`, `registry`, `architecture`
Depends on: #004
Blocks: #012, #013, #014

## Scope

Define the `ParallelCorpus` Protocol, `Sentence` dataclass, exceptions, and the `load_corpus` registry function. Mirror the pattern of #005 — base + registry + exceptions, no real corpus wired here (those come in #012–#014). Implement the `corpora list` CLI as part of this task because it has no real dependencies beyond the registry.

### Files to create

- `src/fertiscope/corpora/__init__.py`
- `src/fertiscope/corpora/base.py`
- `src/fertiscope/corpora/registry.py`
- `src/fertiscope/corpora/exceptions.py`
- `tests/unit/test_corpora_registry.py`
- `tests/unit/_mock_corpus.py`

### Files to modify

- `src/fertiscope/cli.py` — replace `corpora_list` stub body.

### Interface and contract

`exceptions.py`:

```python
class CorpusError(Exception):
    """Base class for corpus errors."""

class CorpusNotFound(CorpusError):
    """Corpus name not in registry."""

class CorpusUnavailable(CorpusError):
    """Corpus is registered but cannot be loaded (missing extra, missing data file, network failure)."""
    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        self.reason = reason
        super().__init__(f"Corpus '{name}' unavailable: {reason}")

class LanguageNotInCorpus(CorpusError):
    """The requested language is not present in this corpus."""
```

`base.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterator, Protocol, runtime_checkable

@dataclass(frozen=True)
class Sentence:
    id: str                              # corpus-stable, e.g. "flores:dev:42"
    lang: str                            # ISO 639-3, e.g. "tam"
    text: str
    meta: dict[str, str] = field(default_factory=dict)

@runtime_checkable
class ParallelCorpus(Protocol):
    name: str
    languages: list[str]
    def iter_sentences(self, lang: str, limit: int | None = None) -> Iterator[Sentence]: ...
    def parallel_pairs(self, lang_a: str, lang_b: str, limit: int | None = None) -> Iterator[tuple[Sentence, Sentence]]: ...
```

`registry.py`:

```python
from __future__ import annotations
from typing import Callable
from .base import ParallelCorpus
from .exceptions import CorpusNotFound, CorpusUnavailable

_CORPORA: dict[str, Callable[..., ParallelCorpus]] = {}

def register(name: str, loader: Callable[..., ParallelCorpus]) -> None:
    if name in _CORPORA:
        raise ValueError(f"Corpus '{name}' already registered")
    _CORPORA[name] = loader

def load_corpus(name: str, **kwargs) -> ParallelCorpus:
    if name not in _CORPORA:
        raise CorpusNotFound(f"Unknown corpus '{name}'. Registered: {sorted(_CORPORA)}")
    try:
        return _CORPORA[name](**kwargs)
    except ImportError as e:
        raise CorpusUnavailable(name, f"missing extra: {e}") from e

def list_corpora() -> list[str]:
    return sorted(_CORPORA)

def _reset_for_testing() -> None:
    _CORPORA.clear()
```

`__init__.py`:

```python
from .base import Sentence, ParallelCorpus
from .registry import register, load_corpus, list_corpora
from .exceptions import CorpusError, CorpusNotFound, CorpusUnavailable, LanguageNotInCorpus

__all__ = [
    "Sentence", "ParallelCorpus",
    "register", "load_corpus", "list_corpora",
    "CorpusError", "CorpusNotFound", "CorpusUnavailable", "LanguageNotInCorpus",
]
```

`tests/unit/_mock_corpus.py`:

```python
from fertiscope.corpora import Sentence

class MockCorpus:
    name = "mock"
    languages = ["eng", "vie"]
    def __init__(self):
        self._data = {
            "eng": [Sentence(id=f"mock:{i}", lang="eng", text=f"sentence {i}") for i in range(5)],
            "vie": [Sentence(id=f"mock:{i}", lang="vie", text=f"câu {i}")     for i in range(5)],
        }
    def iter_sentences(self, lang, limit=None):
        items = self._data.get(lang, [])
        return iter(items if limit is None else items[:limit])
    def parallel_pairs(self, a, b, limit=None):
        a_list = list(self.iter_sentences(a, limit))
        b_list = list(self.iter_sentences(b, limit))
        return iter(zip(a_list, b_list, strict=False))
```

`tests/unit/test_corpora_registry.py` covers:

- `register("mock", MockCorpus)` then `load_corpus("mock")` returns a `MockCorpus`.
- `list_corpora()` returns `["mock"]`.
- `load_corpus("nope")` raises `CorpusNotFound` listing registered names.
- A loader raising `ImportError("datasets")` produces `CorpusUnavailable`.
- `Sentence` is frozen (mutating raises `FrozenInstanceError`).
- `isinstance(MockCorpus(), ParallelCorpus)` is `True`.
- `iter_sentences("eng", limit=2)` yields exactly 2.
- `parallel_pairs("eng", "vie", limit=3)` yields 3 aligned tuples.

`cli.py` change (`corpora_list`):

```python
@corpora_app.command("list")
def corpora_list() -> None:
    """List registered corpora."""
    from fertiscope.corpora import list_corpora
    from rich.console import Console
    from rich.table import Table

    names = list_corpora()
    table = Table(title=f"Registered corpora ({len(names)})", title_style="bold")
    table.add_column("Name", style="cyan")
    for n in names:
        table.add_row(n)
    Console().print(table)
```

### Notes

- `parallel_pairs` returns tuples — order is significant. Sentence at index `i` in `lang_a` corresponds to sentence at index `i` in `lang_b`. FLORES guarantees this.
- The Sentence ID format `"<corpus>:<split>:<idx>"` is a convention, not enforced. Document it in `docs/methodology.md`.
- `LanguageNotInCorpus` is meant for the MAFAND-MT loader (#013) where many Asian languages are absent.
- The `Protocol`-based design lets users register their own corpus class without subclassing — duck-typing all the way down.
- Skip the `corpora list` Rich table flair until more loaders exist; current output is just a single column.

## Acceptance Criteria

- [ ] `from fertiscope.corpora import Sentence, ParallelCorpus, load_corpus, list_corpora` works.
- [ ] `list_corpora()` returns `[]` on a fresh import.
- [ ] All 8 unit tests in `test_corpora_registry.py` pass.
- [ ] `Sentence(id="a", lang="eng", text="x")` is hashable and frozen.
- [ ] `load_corpus("unknown")` raises `CorpusNotFound` with a message listing registered names.
- [ ] `fertiscope corpora list` exits 0 and prints a Rich table (empty rows expected at this stage).
- [ ] `mypy --strict src/fertiscope/corpora/` passes.

## User Stories

### Story: Adapter author writes a new corpus

1. Writes `MyCorpus` class with `name`, `languages`, `iter_sentences`, `parallel_pairs`.
2. Calls `register("mine", MyCorpus)` at module load.
3. Users call `load_corpus("mine")` — done. No subclassing required.

### Story: User lists what's available

1. Runs `fertiscope corpora list` after #012–#014 land.
2. Sees `flores`, `sib200`, `mafand`, `custom`.
3. Knows the full set of options.

---

Blocked by: #004
