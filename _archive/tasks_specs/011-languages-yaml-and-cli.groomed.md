# Languages YAML registry + `languages list` CLI

Status: pending
Tags: `languages`, `iso-639-3`, `scripts`, `flores-tags`, `cli`
Depends on: #004
Blocks: #012, #017, #023

## Scope

Ship the 16-language registry as a typed YAML data file with ISO 639-3 codes, FLORES tags, script codes, language families, and a `spaceless` flag the segmenter consumes. Implement `fertiscope languages list`.

### Files to create

- `src/fertiscope/data/languages.yaml`
- `src/fertiscope/languages.py`
- `tests/unit/test_languages.py`
- `tests/unit/test_cli_languages_list.py`

### Files to modify

- `src/fertiscope/cli.py` — replace `languages_list` stub body.

### Interface and contract

`src/fertiscope/data/languages.yaml`:

```yaml
# 16 study languages: 1 baseline (English) + 15 lower-resource Asian languages.
# Source for FLORES tags: facebook/flores HF dataset.
# Source for script codes: ISO 15924.
schema_version: "1.0"
languages:
  # --- baseline ---
  - iso: eng
    name: English
    script: Latn
    family: Indo-European
    flores_tag: eng_Latn
    spaceless: false
    notes: "Baseline language. 1.26 tokens/word on FLORES."

  # --- Austronesian / Tai-Kadai (Latin script, well-served) ---
  - iso: vie
    name: Vietnamese
    script: Latn
    family: Austroasiatic
    flores_tag: vie_Latn
    spaceless: false
    notes: "Latin + diacritics. Six tones, monosyllabic, well-tokenized."

  - iso: ind
    name: Indonesian
    script: Latn
    family: Austronesian
    flores_tag: ind_Latn
    spaceless: false
    notes: "Closely related to Malay; uses ISO 639-3 'ind'."

  - iso: zsm
    name: Malay
    script: Latn
    family: Austronesian
    flores_tag: zsm_Latn
    spaceless: false
    notes: "Standard Malay; FLORES uses 'zsm_Latn'."

  - iso: tgl
    name: Filipino (Tagalog)
    script: Latn
    family: Austronesian
    flores_tag: tgl_Latn
    spaceless: false
    notes: "Tagalog is the basis of standard Filipino."

  - iso: tha
    name: Thai
    script: Thai
    family: Tai-Kadai
    flores_tag: tha_Thai
    spaceless: true
    notes: "Thai script. No word delimiters; pythainlp required for segmentation."

  # --- Indo-Aryan ---
  - iso: hin
    name: Hindi
    script: Deva
    family: Indo-Aryan
    flores_tag: hin_Deva
    spaceless: false
    notes: "Devanagari script."

  - iso: ben
    name: Bengali
    script: Beng
    family: Indo-Aryan
    flores_tag: ben_Beng
    spaceless: false
    notes: "Bengali script."

  - iso: sin
    name: Sinhala
    script: Sinh
    family: Indo-Aryan
    flores_tag: sin_Sinh
    spaceless: false
    notes: "Sinhala script; high tokenizer tax on cl100k."

  # --- Dravidian ---
  - iso: tam
    name: Tamil
    script: Taml
    family: Dravidian
    flores_tag: tam_Taml
    spaceless: false
    notes: "Spoken in India, Sri Lanka, Singapore, Malaysia."

  - iso: tel
    name: Telugu
    script: Telu
    family: Dravidian
    flores_tag: tel_Telu
    spaceless: false
    notes: ""

  - iso: kan
    name: Kannada
    script: Knda
    family: Dravidian
    flores_tag: kan_Knda
    spaceless: false
    notes: ""

  - iso: mal
    name: Malayalam
    script: Mlym
    family: Dravidian
    flores_tag: mal_Mlym
    spaceless: false
    notes: ""

  # --- Sino-Tibetan / Austroasiatic / Tai-Kadai (Brahmic-derived, spaceless) ---
  - iso: mya
    name: Burmese
    script: Mymr
    family: Sino-Tibetan
    flores_tag: mya_Mymr
    spaceless: true
    notes: "Worst-hit script on cl100k (~11x English)."

  - iso: khm
    name: Khmer
    script: Khmr
    family: Austroasiatic
    flores_tag: khm_Khmr
    spaceless: true
    notes: ""

  - iso: lao
    name: Lao
    script: Laoo
    family: Tai-Kadai
    flores_tag: lao_Laoo
    spaceless: true
    notes: ""
```

`src/fertiscope/languages.py`:

```python
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
    raw = yaml.safe_load(files("fertiscope.data").joinpath("languages.yaml").read_text("utf-8"))
    return [Language(**item) for item in raw["languages"]]


def get_language(iso: str) -> Language:
    for lang in load_languages():
        if lang.iso == iso:
            return lang
    raise KeyError(f"Unknown language iso '{iso}'. Known: {[l.iso for l in load_languages()]}")


def list_isos() -> list[str]:
    return [l.iso for l in load_languages()]
```

`cli.py`:

```python
@languages_app.command("list")
def languages_list() -> None:
    """List study languages with ISO codes, scripts, families."""
    from fertiscope.languages import load_languages
    from rich.console import Console
    from rich.table import Table

    langs = load_languages()
    table = Table(title=f"Study languages ({len(langs)})", title_style="bold")
    table.add_column("ISO",        style="cyan")
    table.add_column("Name",       style="bold")
    table.add_column("Script")
    table.add_column("Family")
    table.add_column("FLORES tag", style="dim")
    table.add_column("Spaceless",  justify="center")
    table.add_column("Notes",      overflow="fold")

    for l in langs:
        spaceless = "[yellow]✓[/yellow]" if l.spaceless else ""
        table.add_row(l.iso, l.name, l.script, l.family, l.flores_tag, spaceless, l.notes)
    Console().print(table)
```

`tests/unit/test_languages.py`:

```python
import pytest
from fertiscope.languages import load_languages, get_language, list_isos, Language

def test_load_returns_16():
    assert len(load_languages()) == 16

def test_baseline_first():
    assert load_languages()[0].iso == "eng"

def test_spaceless_set():
    spaceless = {l.iso for l in load_languages() if l.spaceless}
    assert spaceless == {"tha", "mya", "khm", "lao"}

def test_get_language():
    tam = get_language("tam")
    assert tam.script == "Taml"
    assert tam.flores_tag == "tam_Taml"
    assert tam.family == "Dravidian"

def test_get_language_unknown():
    with pytest.raises(KeyError):
        get_language("xyz")

def test_list_isos_returns_16():
    assert len(list_isos()) == 16
    assert "eng" in list_isos()
    assert "tam" in list_isos()

@pytest.mark.parametrize("iso", ["eng","vie","ind","zsm","tgl","tha","hin","ben","sin","tam","tel","kan","mal","mya","khm","lao"])
def test_each_lang_has_flores_tag(iso: str):
    assert get_language(iso).flores_tag.endswith(("Latn","Thai","Deva","Beng","Sinh","Taml","Telu","Knda","Mlym","Mymr","Khmr","Laoo"))
```

`tests/unit/test_cli_languages_list.py`:

```python
from typer.testing import CliRunner
from fertiscope.cli import app

def test_languages_list():
    r = CliRunner().invoke(app, ["languages", "list"])
    assert r.exit_code == 0
    for iso in ["eng","tam","mya","tha"]:
        assert iso in r.stdout
```

### Notes

- ISO 639-3 codes are the canonical identifiers. `msa` is sometimes used for Malay macro-language; FLORES uses `zsm` for the specific Standard Malay variety — match that.
- The `flores_tag` field is what gets passed to `datasets.load_dataset("facebook/flores", flores_tag)`. Do NOT use the ISO code directly; FLORES expects the `<iso>_<Script>` form.
- The `spaceless` flag drives segmentation (#017). Test that all four spaceless languages have the flag set.
- `importlib.resources.files(...)` is the modern way to read package-bundled data — works inside wheels.
- DO NOT hardcode the YAML in Python. Editing one source-of-truth YAML is what makes adding language #17 trivial.

## Acceptance Criteria

- [ ] `src/fertiscope/data/languages.yaml` exists with exactly 16 entries.
- [ ] `load_languages()` returns 16 `Language` objects.
- [ ] `get_language("tam").script == "Taml"`.
- [ ] All 4 spaceless languages (`tha`, `mya`, `khm`, `lao`) have `spaceless: true`.
- [ ] All 16 languages have a non-empty `flores_tag`.
- [ ] `fertiscope languages list` prints 16-row Rich table.
- [ ] All 8 unit tests in `test_languages.py` pass.
- [ ] CLI test passes.
- [ ] `mypy --strict src/fertiscope/languages.py` passes.
- [ ] YAML schema_version is `"1.0"`.

## User Stories

### Story: Adding language #17

1. User opens `languages.yaml`, adds:
   ```yaml
   - iso: jpn
     name: Japanese
     script: Jpan
     family: Japonic
     flores_tag: jpn_Jpan
     spaceless: true
     notes: "Mixed kanji/kana, requires MeCab."
   ```
2. `fertiscope languages list` now shows 17 rows.
3. No other code changes.

### Story: CLI orientation

1. New user runs `fertiscope languages list`.
2. Sees Tamil flagged as `Dravidian`, Burmese as `spaceless ✓`.
3. Reads notes column to learn each language has been pre-investigated.

---

Blocked by: #004
