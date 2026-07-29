"""Matching helpers. Never use these values as display text."""

from __future__ import annotations

import hashlib
import re
import unicodedata

_TRANSLATION = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        "–": "-",
        "—": "-",
        "―": "-",
        "…": "...",
    }
)


def normalize(value: str) -> str:
    """Return a stable matching key without modifying the submitted value."""
    normalized = unicodedata.normalize("NFC", value).translate(_TRANSLATION)
    punctuation_free = re.sub(r"[^\w\s]", " ", normalized)
    return re.sub(r"\s+", " ", punctuation_free).strip().casefold()


def fingerprint(value: str) -> str:
    return hashlib.sha256(normalize(value).encode("utf-8")).hexdigest()


def token_signature(value: str) -> frozenset[str]:
    return frozenset(re.findall(r"\w+", normalize(value)))
