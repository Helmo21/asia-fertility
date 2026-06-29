"""NIAH recall scoring."""

from __future__ import annotations

import unicodedata


def recall_score(response: str, marker: str) -> bool:
    """True if marker appears as exact substring in NFC-normalized response."""
    r = unicodedata.normalize("NFC", response)
    m = unicodedata.normalize("NFC", marker)
    return m in r
