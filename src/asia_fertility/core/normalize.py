"""Unicode NFC normalization."""

from __future__ import annotations

import unicodedata


def nfc(text: str) -> str:
    """Return NFC-normalized text."""
    return unicodedata.normalize("NFC", text)


def is_nfc(text: str) -> bool:
    return unicodedata.is_normalized("NFC", text)
