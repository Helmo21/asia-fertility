"""Script-native marker phrases for NIAH.

Each script has 5 markers (one per position percentile). Markers are native to
the script (avoiding the Latin-needle-in-non-Latin-haystack bias caveat) and
designed to tokenize to ≥2 tokens to keep recall non-trivial.
"""
from __future__ import annotations

import logging
from typing import Final

_log = logging.getLogger(__name__)

SCRIPT_MARKERS: Final[dict[str, list[str]]] = {
    "Latn": [
        "MARKER-AURORA-9241",
        "MARKER-HORIZON-3358",
        "MARKER-ZENITH-7715",
        "MARKER-SOLSTICE-1604",
        "MARKER-APEX-5872",
    ],
    "Thai": [
        "เครื่องหมายอรุณรุ่ง-924",
        "เครื่องหมายขอบฟ้า-336",
        "เครื่องหมายจุดสูงสุด-771",
        "เครื่องหมายค่ำคืน-160",
        "เครื่องหมายยอดเขา-587",
    ],
    "Deva": [
        "चिन्ह-उषाकाल-924",
        "चिन्ह-क्षितिजरेखा-336",
        "चिन्ह-शिखरबिंदु-771",
        "चिन्ह-निशाकाल-160",
        "चिन्ह-पर्वतशीर्ष-587",
    ],
    "Beng": [
        "চিহ্ন-উষাকাল-924",
        "চিহ্ন-দিগন্তরেখা-336",
        "চিহ্ন-শীর্ষবিন্দু-771",
        "চিহ্ন-নিশীথকাল-160",
        "চিহ্ন-পর্বতচূড়া-587",
    ],
    "Sinh": [
        "සංකේත-අරුණෝදය-924",
        "සංකේත-ක්ෂිතිජය-336",
        "සංකේත-උච්චස්ථානය-771",
        "සංකේත-නිශීථය-160",
        "සංකේත-පර්වතශීර්ෂය-587",
    ],
    "Taml": [
        "குறி-உதயம்-924",
        "குறி-அடிவானம்-336",
        "குறி-உச்சம்-771",
        "குறி-நள்ளிரவு-160",
        "குறி-மலைச்சிகரம்-587",
    ],
    "Telu": [
        "గుర్తు-సూర్యోదయం-924",
        "గుర్తు-క్షితిజరేఖ-336",
        "గుర్తు-శిఖరం-771",
        "గుర్తు-అర్ధరాత్రి-160",
        "గుర్తు-పర్వతశిఖరం-587",
    ],
    "Knda": [
        "ಗುರುತು-ಸೂರ್ಯೋದಯ-924",
        "ಗುರುತು-ಕ್ಷಿತಿಜ-336",
        "ಗುರುತು-ಶಿಖರ-771",
        "ಗುರುತು-ಮಧ್ಯರಾತ್ರಿ-160",
        "ಗುರುತು-ಪರ್ವತಶಿಖರ-587",
    ],
    "Mlym": [
        "അടയാളം-സൂര്യോദയം-924",
        "അടയാളം-ചക്രവാളം-336",
        "അടയാളം-ശിഖരം-771",
        "അടയാളം-അർദ്ധരാത്രി-160",
        "അടയാളം-പർവ്വതാഗ്രം-587",
    ],
    "Mymr": [
        "အမှတ်-အရုဏ်ဦး-924",
        "အမှတ်-မိုးကုပ်စက်ဝိုင်း-336",
        "အမှတ်-ထိပ်ဆုံး-771",
        "အမှတ်-သန်းခေါင်-160",
        "အမှတ်-တောင်ထွတ်-587",
    ],
    "Khmr": [
        "សញ្ញាសម្គាល់-ព្រលឹម-924",
        "សញ្ញាសម្គាល់-មេឃផ្ដេក-336",
        "សញ្ញាសម្គាល់-កំពូល-771",
        "សញ្ញាសម្គាល់-អាធ្រាត្រ-160",
        "សញ្ញាសម្គាល់-កំពូលភ្នំ-587",
    ],
    "Laoo": [
        "ເຄື່ອງໝາຍ-ອາລຸນ-924",
        "ເຄື່ອງໝາຍ-ຂອບຟ້າ-336",
        "ເຄື່ອງໝາຍ-ຈຸດສູງສຸດ-771",
        "ເຄື່ອງໝາຍ-ທ່ຽງຄືນ-160",
        "ເຄື່ອງໝາຍ-ຍອດພູ-587",
    ],
}


def get_marker(script: str, position_idx: int) -> str:
    if position_idx not in range(5):
        raise IndexError(f"position_idx must be 0..4, got {position_idx}")
    if script not in SCRIPT_MARKERS:
        _log.warning(
            f"No script-native markers for '{script}', falling back to Latin."
        )
        return SCRIPT_MARKERS["Latn"][position_idx]
    return SCRIPT_MARKERS[script][position_idx]


def supported_scripts() -> list[str]:
    return sorted(SCRIPT_MARKERS)
