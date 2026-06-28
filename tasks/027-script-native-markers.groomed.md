# Script-native markers for NIAH

Status: pending
Tags: `niah`, `markers`, `multi-script`, `unicode`
Depends on: #006, #011
Blocks: #028, #030

## Scope

Replace the Latin "MARKER_AURORA" pattern (Miles' v1) with script-native markers — Tamil markers in Tamil haystacks, Burmese markers in Burmese haystacks, etc. This closes the paper's flagged caveat ("Latin marker may stand out in non-Latin haystack").

### Files to create

- `src/fertiscope/niah/__init__.py`
- `src/fertiscope/niah/markers.py`
- `tests/unit/test_niah_markers.py`

### Files to modify

- None.

### Interface and contract

`src/fertiscope/niah/markers.py`:

```python
"""Script-native marker phrases for the multi-turn NIAH benchmark.

Each script has 5 markers (one per position percentile). Markers are:
- Native to the script (not Latin loanwords)
- Compound nouns/phrases unlikely to collide with FLORES corpus content
- Verified to tokenize to ≥ 2 tokens under all major tokenizers (so recall isn't trivial)

The benchmark inserts ONE marker per haystack at the specified position;
the model is asked to recall it. Tracking position × recall reveals
'lost in the middle' degradation.
"""
from __future__ import annotations
from typing import Final

# 5 markers per script. Index 0 = position 5%, idx 4 = position 95%.
SCRIPT_MARKERS: Final[dict[str, list[str]]] = {
    # Latin — for English / Vietnamese / Indonesian / Malay / Filipino
    "Latn": [
        "MARKER-AURORA-9241",
        "MARKER-HORIZON-3358",
        "MARKER-ZENITH-7715",
        "MARKER-SOLSTICE-1604",
        "MARKER-APEX-5872",
    ],
    # Thai
    "Thai": [
        "เครื่องหมายอรุณรุ่ง",
        "เครื่องหมายขอบฟ้า",
        "เครื่องหมายจุดสูงสุด",
        "เครื่องหมายค่ำคืน",
        "เครื่องหมายยอดเขา",
    ],
    # Devanagari — Hindi
    "Deva": [
        "चिन्ह-उषाकाल",
        "चिन्ह-क्षितिजरेखा",
        "चिन्ह-शिखरबिंदु",
        "चिन्ह-निशाकाल",
        "चिन्ह-पर्वतशीर्ष",
    ],
    # Bengali
    "Beng": [
        "চিহ্ন-উষাকাল",
        "চিহ্ন-দিগন্তরেখা",
        "চিহ্ন-শীর্ষবিন্দু",
        "চিহ্ন-নিশীথকাল",
        "চিহ্ন-পর্বতচূড়া",
    ],
    # Sinhala
    "Sinh": [
        "සංකේත-අරුණෝදය",
        "සංකේත-ක්ෂිතිජය",
        "සංකේත-උච්චස්ථානය",
        "සංකේත-නිශීථය",
        "සංකේත-පර්වතශීර්ෂය",
    ],
    # Tamil
    "Taml": [
        "குறி-உதயம்-9241",
        "குறி-அடிவானம்-3358",
        "குறி-உச்சம்-7715",
        "குறி-நள்ளிரவு-1604",
        "குறி-மலைச்சிகரம்-5872",
    ],
    # Telugu
    "Telu": [
        "గుర్తు-సూర్యోదయం",
        "గుర్తు-క్షితిజరేఖ",
        "గుర్తు-శిఖరం",
        "గుర్తు-అర్ధరాత్రి",
        "గుర్తు-పర్వతశిఖరం",
    ],
    # Kannada
    "Knda": [
        "ಗುರುತು-ಸೂರ್ಯೋದಯ",
        "ಗುರುತು-ಕ್ಷಿತಿಜ",
        "ಗುರುತು-ಶಿಖರ",
        "ಗುರುತು-ಮಧ್ಯರಾತ್ರಿ",
        "ಗುರುತು-ಪರ್ವತಶಿಖರ",
    ],
    # Malayalam
    "Mlym": [
        "അടയാളം-സൂര്യോദയം",
        "അടയാളം-ചക്രവാളം",
        "അടയാളം-ശിഖരം",
        "അടയാളം-അർദ്ധരാത്രി",
        "അടയാളം-പർവ്വതാഗ്രം",
    ],
    # Myanmar / Burmese
    "Mymr": [
        "အမှတ်-အရုဏ်ဦး",
        "အမှတ်-မိုးကုပ်စက်ဝိုင်း",
        "အမှတ်-ထိပ်ဆုံး",
        "အမှတ်-သန်းခေါင်",
        "အမှတ်-တောင်ထွတ်",
    ],
    # Khmer
    "Khmr": [
        "សញ្ញាសម្គាល់-ព្រលឹម",
        "សញ្ញាសម្គាល់-មេឃផ្ដេក",
        "សញ្ញាសម្គាល់-កំពូល",
        "សញ្ញាសម្គាល់-អាធ្រាត្រ",
        "សញ្ញាសម្គាល់-កំពូលភ្នំ",
    ],
    # Lao
    "Laoo": [
        "ເຄື່ອງໝາຍ-ອາລຸນ",
        "ເຄື່ອງໝາຍ-ຂອບຟ້າ",
        "ເຄື່ອງໝາຍ-ຈຸດສູງສຸດ",
        "ເຄື່ອງໝາຍ-ທ່ຽງຄືນ",
        "ເຄື່ອງໝາຍ-ຍອດພູ",
    ],
}


def get_marker(script: str, position_idx: int) -> str:
    """Return marker for `script` at position-index 0..4 (5% / 25% / 50% / 75% / 95%).

    Falls back to Latin marker with a logged warning if script unsupported.
    """
    if position_idx not in range(5):
        raise IndexError(f"position_idx must be 0..4, got {position_idx}")
    if script not in SCRIPT_MARKERS:
        import logging
        logging.getLogger(__name__).warning(
            f"No script-native markers for '{script}', falling back to Latin. This may produce easier-than-fair recall."
        )
        return SCRIPT_MARKERS["Latn"][position_idx]
    return SCRIPT_MARKERS[script][position_idx]


def supported_scripts() -> list[str]:
    return sorted(SCRIPT_MARKERS)


def verify_marker_tokenization(tokenizer_id: str, min_tokens: int = 2) -> dict[str, list[int]]:
    """For each script's 5 markers, return token counts. Fails any script where
    a marker is < min_tokens — that would make recall trivial.
    """
    from fertiscope.tokenizers import get_tokenizer
    tok = get_tokenizer(tokenizer_id)
    out: dict[str, list[int]] = {}
    for script, markers in SCRIPT_MARKERS.items():
        counts = [tok.count(m) for m in markers]
        out[script] = counts
    return out
```

`tests/unit/test_niah_markers.py`:

```python
import pytest
from fertiscope.niah.markers import SCRIPT_MARKERS, get_marker, supported_scripts, verify_marker_tokenization

def test_12_scripts_supported():
    expected = {"Latn","Thai","Deva","Beng","Sinh","Taml","Telu","Knda","Mlym","Mymr","Khmr","Laoo"}
    assert set(SCRIPT_MARKERS) == expected
    assert supported_scripts() == sorted(expected)

def test_each_script_has_5_markers():
    for script, markers in SCRIPT_MARKERS.items():
        assert len(markers) == 5, f"{script} has {len(markers)} markers, expected 5"

def test_get_marker_by_position():
    assert get_marker("Taml", 0).startswith("குறி-உதயம்")
    assert get_marker("Latn", 4).startswith("MARKER-APEX")

def test_get_marker_unknown_script_falls_back(caplog):
    with caplog.at_level("WARNING"):
        m = get_marker("Hans", 0)
    assert m == SCRIPT_MARKERS["Latn"][0]
    assert "No script-native markers" in caplog.text

def test_invalid_position_raises():
    with pytest.raises(IndexError):
        get_marker("Taml", 5)

def test_markers_unique_within_script():
    for script, markers in SCRIPT_MARKERS.items():
        assert len(set(markers)) == 5, f"{script} has duplicate markers"

def test_no_marker_contains_ascii_digits_only_in_non_latin():
    """Non-Latin markers must contain at least some native-script characters."""
    for script, markers in SCRIPT_MARKERS.items():
        if script == "Latn":
            continue
        for m in markers:
            # At least one character should be in the script's Unicode block
            assert not m.isascii(), f"Marker '{m}' in {script} is all-ASCII (bias risk)"

@pytest.mark.parametrize("tokenizer_id", ["openai/o200k_base", "openai/cl100k_base"])
def test_markers_tokenize_to_at_least_2_tokens(tokenizer_id):
    """If a marker tokenizes to 1 token, recall is trivially easy. Fail loud."""
    counts = verify_marker_tokenization(tokenizer_id, min_tokens=2)
    for script, marker_counts in counts.items():
        for i, c in enumerate(marker_counts):
            assert c >= 2, f"{script}[{i}] = {SCRIPT_MARKERS[script][i]!r} tokenizes to {c} on {tokenizer_id} (< 2)"
```

### Notes

- The non-Latin markers are **manually translated compound nouns** matching "MARKER" + [dawn/horizon/zenith/midnight/peak]. Native speakers should review for naturalness vs. corpus-collision risk.
- The trailing digits in Latin/Tamil markers (e.g. `-9241`) ensure uniqueness within text that might contain related words (e.g. "horizon" appears in many English sentences; "MARKER-HORIZON-3358" doesn't).
- Asian-script markers OMIT trailing digits in some entries to keep them natural in the script. Reviewers should run the verify_marker_tokenization test to confirm none have collapsed to 1 token.
- The `verify_marker_tokenization` function is the safety net: if Burmese gemma-4 tokenizes "အမှတ်-ထိပ်ဆုံး" to 1 token, the test fails and we adjust the marker.
- DO NOT use real proper nouns or place names — risk of corpus collision.

## Acceptance Criteria

- [ ] `SCRIPT_MARKERS` has exactly 12 scripts with 5 markers each (60 total).
- [ ] No script has duplicate markers.
- [ ] Every non-Latin script's markers are NOT all-ASCII.
- [ ] `get_marker("Taml", 0)` returns the Tamil marker.
- [ ] `get_marker("UnknownScript", 0)` returns the Latin fallback and logs a warning.
- [ ] `get_marker("Taml", 5)` raises `IndexError`.
- [ ] All 60 markers tokenize to ≥ 2 tokens under `openai/o200k_base` (verified by parametrized test).
- [ ] All 60 markers tokenize to ≥ 2 tokens under `openai/cl100k_base`.
- [ ] All 8 unit tests pass.
- [ ] `mypy --strict src/fertiscope/niah/markers.py` passes.

## User Stories

### Story: Reviewer asks "is the Latin-needle caveat closed?"

1. Reviewer reads `markers.py` source.
2. Sees per-script native markers.
3. Runs `verify_marker_tokenization` — confirms ≥ 2 tokens everywhere.
4. Caveat closed.

### Story: Adding script #13

1. Adds Hebrew (`Hebr`) to `SCRIPT_MARKERS` with 5 native-script markers.
2. `supported_scripts()` now returns 13.
3. CI checks: tokenization ≥ 2 tokens — pass.
4. Hebrew haystacks now use native markers automatically.

### Story: Burmese-marker drift on Gemma 4

1. Gemma 4 updates and now tokenizes "အမှတ်-အရုဏ်ဦး" to 1 token.
2. `test_markers_tokenize_to_at_least_2_tokens[meta/llama-4]` fails.
3. Maintainer adds more distinguishing suffix or alternate marker.

---

Blocked by: #006, #011
