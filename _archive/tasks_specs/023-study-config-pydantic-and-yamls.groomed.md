# StudyConfig pydantic model + 3 YAML configs

Status: pending
Tags: `study`, `config`, `pydantic`, `yaml`
Depends on: #011, #020, #021
Blocks: #024, #026

## Scope

Define the typed `StudyConfig` schema (pydantic v2) and ship three pre-baked YAMLs: `study_main.yaml` (the headline 16×11×2 grid), `study_test.yaml` (3×2×1 smoke study for CI), and `study_reproduce.yaml` (7×3×bundled-suite for the offline demo). No runner logic yet — just config validation + parsing.

### Files to create

- `src/fertiscope/config.py`
- `configs/study_main.yaml`
- `configs/study_test.yaml`
- `configs/study_reproduce.yaml`
- `tests/unit/test_config.py`
- `tests/unit/fixtures/study_invalid.yaml`

### Files to modify

- None.

### Interface and contract

`src/fertiscope/config.py`:

```python
"""StudyConfig — the YAML schema consumed by `fertiscope run`.

Every field is required except defaults specified explicitly. `extra="forbid"`
means a typo in a YAML field fails loud at load time rather than being silently ignored.
"""
from __future__ import annotations
from datetime import date
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator
import yaml


class StudyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, description="Used to derive output_dir")
    description: str = ""
    languages: list[str] = Field(min_length=1)
    tokenizers: list[str] = Field(min_length=1)
    corpora: list[str] = Field(default_factory=lambda: ["flores"], min_length=1)
    baseline_language: str = "eng"
    n_sentences: int | None = Field(default=None, gt=0, description="None = all available")
    split: Literal["dev", "devtest"] = "dev"
    n_bootstrap: int = Field(default=1000, ge=100, le=10000)
    rng_seed: int = 42
    windows: list[int] = Field(default_factory=lambda: [4096, 8192, 32768, 131072])
    prices_snapshot: str = "_defaults/prices_2026-06.yaml"
    fx_snapshot:     str = "_defaults/fx_2026-06.yaml"
    output_dir: str = "runs/{name}"

    @model_validator(mode="after")
    def _validate_baseline_in_languages(self):
        if self.baseline_language not in self.languages:
            raise ValueError(
                f"baseline_language '{self.baseline_language}' must appear in languages list {self.languages}"
            )
        return self

    @model_validator(mode="after")
    def _validate_windows_positive(self):
        if not all(w > 0 for w in self.windows):
            raise ValueError("All windows must be > 0")
        return self

    @classmethod
    def from_yaml(cls, path: str | Path) -> "StudyConfig":
        text = Path(path).read_text("utf-8")
        raw = yaml.safe_load(text)
        return cls.model_validate(raw)

    def resolve_output_dir(self) -> Path:
        return Path(self.output_dir.format(name=self.name))
```

`configs/study_main.yaml`:

```yaml
name: main
description: "16 Asian languages × 11 tokenizers × 2 corpora — main study for the v2 paper."
languages:
  - eng
  - vie
  - ind
  - zsm
  - tgl
  - tha
  - hin
  - ben
  - sin
  - tam
  - tel
  - kan
  - mal
  - mya
  - khm
  - lao
tokenizers:
  - openai/o200k_base
  - openai/cl100k_base
  - openai/o200k_harmony
  - meta/llama-3.1
  - meta/llama-4
  - google/gemma-4
  - mistral/tekken
  - qwen/qwen3
  - deepseek/v3
  - bigscience/bloom
  - cohere/aya-expanse
corpora: [flores, sib200]
baseline_language: eng
n_sentences: null
split: dev
n_bootstrap: 1000
rng_seed: 42
windows: [4096, 8192, 32768, 131072]
prices_snapshot: _defaults/prices_2026-06.yaml
fx_snapshot: _defaults/fx_2026-06.yaml
output_dir: runs/main
```

`configs/study_test.yaml`:

```yaml
name: test
description: "CI smoke study — 3 languages × 2 tokenizers × FLORES dev[0:10]."
languages: [eng, vie, tam]
tokenizers: [openai/o200k_base, openai/cl100k_base]
corpora: [flores]
baseline_language: eng
n_sentences: 10
split: dev
n_bootstrap: 100
rng_seed: 42
windows: [4096, 8192]
prices_snapshot: _defaults/prices_2026-06.yaml
fx_snapshot: _defaults/fx_2026-06.yaml
output_dir: runs/test
```

`configs/study_reproduce.yaml`:

```yaml
name: reproduce
description: "Offline credibility demo — 7 languages × 3 tiktoken encodings × bundled reference suite."
languages: [eng, vie, ind, tha, hin, tam, mya]
tokenizers: [openai/o200k_base, openai/cl100k_base, openai/o200k_harmony]
corpora: [custom]
baseline_language: eng
n_sentences: null
split: dev
n_bootstrap: 200
rng_seed: 42
windows: [4096, 8192, 32768]
prices_snapshot: _defaults/prices_2026-06.yaml
fx_snapshot: _defaults/fx_2026-06.yaml
output_dir: runs/reproduce
```

> Note: `study_reproduce.yaml` uses `custom` corpus → the runner (#024) detects `name=reproduce` and points the custom loader at the bundled `data/reference_suite/reference.jsonl`. See #026 for the wiring.

`tests/unit/test_config.py`:

```python
import pytest
from pathlib import Path
from fertiscope.config import StudyConfig

ROOT = Path(__file__).resolve().parents[2]    # repo root

def test_main_config_loads():
    cfg = StudyConfig.from_yaml(ROOT / "configs" / "study_main.yaml")
    assert cfg.name == "main"
    assert len(cfg.languages) == 16
    assert len(cfg.tokenizers) == 11
    assert cfg.baseline_language == "eng"

def test_test_config_loads():
    cfg = StudyConfig.from_yaml(ROOT / "configs" / "study_test.yaml")
    assert cfg.n_sentences == 10
    assert "tam" in cfg.languages

def test_reproduce_config_loads():
    cfg = StudyConfig.from_yaml(ROOT / "configs" / "study_reproduce.yaml")
    assert cfg.corpora == ["custom"]
    assert "mya" in cfg.languages

def test_resolve_output_dir():
    cfg = StudyConfig.from_yaml(ROOT / "configs" / "study_test.yaml")
    assert cfg.resolve_output_dir() == Path("runs/test")

def test_baseline_not_in_languages_raises():
    with pytest.raises(ValueError, match="baseline_language"):
        StudyConfig.model_validate({
            "name": "x", "languages": ["tam"], "tokenizers": ["t"],
            "baseline_language": "eng",
        })

def test_extra_field_rejected():
    with pytest.raises(Exception):
        StudyConfig.model_validate({
            "name": "x", "languages": ["eng"], "tokenizers": ["t"],
            "baseline_language": "eng", "weird_field": 1,
        })

def test_n_sentences_must_be_positive_or_none():
    with pytest.raises(Exception):
        StudyConfig.model_validate({
            "name": "x", "languages": ["eng"], "tokenizers": ["t"],
            "baseline_language": "eng", "n_sentences": 0,
        })

def test_model_dump_roundtrip():
    cfg = StudyConfig.from_yaml(ROOT / "configs" / "study_test.yaml")
    dumped = cfg.model_dump_json(indent=2)
    re_loaded = StudyConfig.model_validate_json(dumped)
    assert re_loaded == cfg

def test_frozen():
    cfg = StudyConfig.from_yaml(ROOT / "configs" / "study_test.yaml")
    with pytest.raises(Exception):
        cfg.name = "different"    # frozen
```

`tests/unit/fixtures/study_invalid.yaml`:

```yaml
name: bad
languages: [eng]
tokenizers: []      # min_length=1 violation
baseline_language: eng
```

### Notes

- `frozen=True` makes `StudyConfig` hashable → `config_sha256` in #025 can hash the canonical JSON dump.
- The `prices_snapshot` and `fx_snapshot` fields hold paths-as-strings. The runner resolves them relative to repo root OR uses `_defaults/` if the path starts with `_defaults/`.
- `n_sentences: null` in YAML → `None` in Python → "use all available". Document this.
- `windows` defaults to `[4096, 8192, 32768, 131072]` — these are the standard advertised model windows. Custom configs can override.
- DO NOT add a `tokenizers_optional` list. Either a tokenizer is in the study or it isn't; the runner handles unavailability via skip-rows (#024).

## Acceptance Criteria

- [ ] `from fertiscope.config import StudyConfig` works.
- [ ] `StudyConfig.from_yaml("configs/study_main.yaml")` loads and produces 16 languages, 11 tokenizers, 2 corpora.
- [ ] `StudyConfig.from_yaml("configs/study_test.yaml")` loads with `n_sentences=10`.
- [ ] `StudyConfig.from_yaml("configs/study_reproduce.yaml")` loads with `corpora=["custom"]`.
- [ ] `resolve_output_dir()` interpolates `{name}` correctly.
- [ ] `baseline_language` not in `languages` → ValueError.
- [ ] Extra YAML field → pydantic ValidationError.
- [ ] `n_sentences=0` → ValidationError.
- [ ] `model_dump_json` round-trips identically.
- [ ] `frozen=True` enforced.
- [ ] All 9 unit tests pass.
- [ ] `mypy --strict src/fertiscope/config.py` passes.

## User Stories

### Story: Researcher writes a custom study

1. Copies `study_main.yaml` to `configs/study_indic_only.yaml`.
2. Trims languages to `[eng, hin, ben, tam, tel, kan, mal]`.
3. Trims tokenizers to `[openai/o200k_base, sarvam/indic-super-tokenizer]` (once #040 lands).
4. `fertiscope run --config configs/study_indic_only.yaml` works.

### Story: CI runs the test study

1. CI uses `study_test.yaml` (small footprint).
2. Expected runtime < 30s.
3. CI assertions check that 6 result rows are produced (3 langs × 2 tokenizers).

### Story: Reviewer audits the main study

1. Opens `configs/study_main.yaml` in GitHub.
2. Sees exactly the parameters used. Languages, tokenizers, seeds — all visible, all version-controlled.

---

Blocked by: #011, #020, #021
