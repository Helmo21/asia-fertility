# Indic-specialized tokenizers (IndicSuperTokenizer + sarvam-1)

Status: pending (v0.4 optional)
Tags: `tokenizers`, `indic`, `sarvam`, `optional`
Depends on: #007
Blocks: None

## Scope

Add two purpose-built Indic tokenizers to the registry. These are the comparison point that makes Tamil/Hindi/Bengali/Telugu/Kannada/Malayalam users' switching decision concrete: Western tokenizers vs purpose-built Indic ones.

### Files to create

- `tests/golden/golden_counts_indic.json`
- `tests/golden/test_golden_counts_indic.py`

### Files to modify

- `src/fertiscope/tokenizers/hf_adapter.py` — add 2 entries.

### Interface and contract

Append to `_HF_TOKENIZERS` in `hf_adapter.py`:

```python
_HF_TOKENIZERS = {
    # ... existing entries ...
    "sarvam/sarvam-1":                ("sarvamai/sarvam-1",                "sarvam", False, "Indic-optimized Llama derivative"),
    "sarvam/indic-super-tokenizer":   ("sarvamai/indic-super-tokenizer",   "sarvam", False, "Standalone Indic tokenizer; 8k vocab focused on Indic scripts"),
}
```

Update `Family` Literal in `tokenizers/base.py`:

```python
Family = Literal["openai", "meta", "google", "mistral", "qwen", "deepseek",
                 "bigscience", "cohere", "anthropic", "sarvam"]
```

`tests/golden/golden_counts_indic.json`:

```json
{
  "schema_version": "1.0",
  "snapshots": [
    {"id": "sarvam/sarvam-1",              "text": "தமிழ் ஒரு செம்மொழி",    "count": null},
    {"id": "sarvam/sarvam-1",              "text": "नमस्ते दुनिया",          "count": null},
    {"id": "sarvam/sarvam-1",              "text": "বাংলা ভাষা",             "count": null},
    {"id": "sarvam/indic-super-tokenizer", "text": "தமிழ் ஒரு செம்மொழி",    "count": null},
    {"id": "sarvam/indic-super-tokenizer", "text": "नमस्ते दुनिया",          "count": null},
    {"id": "sarvam/indic-super-tokenizer", "text": "বাংলা ভাষা",             "count": null}
  ]
}
```

> Implementer downloads each tokenizer once (no HF_TOKEN required for sarvamai/ public repos), fills the `null` counts, commits the JSON. Tests then become drift detectors.

`tests/golden/test_golden_counts_indic.py`:

```python
import json, os, pathlib, pytest
from fertiscope.tokenizers import get_tokenizer

GOLDEN = json.loads(pathlib.Path(__file__).parent.joinpath("golden_counts_indic.json").read_text("utf-8"))

@pytest.mark.skipif(
    not os.environ.get("RUN_INDIC_GOLDEN", "") or os.environ.get("HF_TOKEN") is None,
    reason="Indic golden tests require HF cached models; set RUN_INDIC_GOLDEN=1 to run."
)
@pytest.mark.parametrize("snap", [s for s in GOLDEN["snapshots"] if s["count"] is not None])
def test_indic_count_matches_golden(snap: dict):
    tok = get_tokenizer(snap["id"])
    actual = tok.count(snap["text"])
    assert actual == snap["count"], f"Drift on {snap['id']}: text={snap['text']!r} expected={snap['count']} actual={actual}"
```

### Notes

- `sarvamai/sarvam-1` and `sarvamai/indic-super-tokenizer` are PUBLIC HF repos (no gating, no HF_TOKEN required). Verify before committing.
- IndicSuperTokenizer reportedly cuts Tamil tokens by ~75% vs cl100k. This is the headline finding for Indic users.
- Golden tests are opt-in via `RUN_INDIC_GOLDEN=1` — first run downloads ~500MB of HF assets which is slow for casual CI.
- The Sarvam team trains on Indic Wikipedia + literature, so the tokenizers cover scripts well; coverage of pan-Asian (Burmese, Khmer, Lao) is unknown — expect poor results there. Document.

## Acceptance Criteria

- [ ] `sarvam/sarvam-1` and `sarvam/indic-super-tokenizer` appear in `list_tokenizers()`.
- [ ] Both have `family="sarvam"`, `backend="hf"`, `gated=False`.
- [ ] With `[hf]` extra: `get_tokenizer("sarvam/sarvam-1").count("தமிழ்") > 0`.
- [ ] Without `[hf]`: clean `TokenizerUnavailable` with extra hint.
- [ ] Golden snapshots filled in for 6 (tokenizer, text) pairs.
- [ ] `Family` Literal extended to include `"sarvam"`.
- [ ] `mypy --strict` passes after the `Family` change.

## User Stories

### Story: Tamil deployer compares cl100k vs IndicSuperTokenizer

1. Runs `fertiscope measure --text "<Tamil sample>" --tokenizer openai/cl100k_base` → fertility 11×.
2. Runs `--tokenizer sarvam/indic-super-tokenizer` → fertility 2.4×.
3. Switches model for Tamil-heavy workloads, saves 75% on token bill.

### Story: Reviewer questions Sarvam coverage

1. Tests `sarvam/sarvam-1.count("မင်္ဂလာပါ ကမ္ဘာ")` (Burmese) → high fertility expected.
2. Confirms: sarvam doesn't help Burmese.
3. Documents in conclusion: "purpose-built Indic tokenizers help Indic scripts, not pan-Asian".

---

Blocked by: #007
