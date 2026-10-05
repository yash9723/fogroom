"""User-content sanitisation.

The API stores plain text only. Control characters are stripped and length is bounded;
HTML is never rendered by the frontend (React escapes text) and PDF output escapes markup.
"""

import re
import unicodedata

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(value: str | None, max_length: int = 4000) -> str | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFC", value)
    text = _CONTROL.sub("", text).strip()
    if not text:
        return None
    return text[:max_length]


def require_text(value: str, max_length: int = 4000) -> str:
    cleaned = clean_text(value, max_length)
    return cleaned or ""
