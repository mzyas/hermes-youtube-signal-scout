"""Strict-whitelist text sanitization for user-facing fields.

Used at the trust boundary in :mod:`tools.video_hydrator` to keep polluted or
adversarial input from leaking into Markdown / HTML reports.

The whitelist is **category-based** rather than a fixed character-class regex.
Any letter from any script (Unicode category starting with ``L``) and any
decimal digit (``Nd``) is allowed, plus an explicit allow-list of safe
punctuation. Everything else is replaced with a space. This covers Thai,
Korean Hangul, Devanagari, Cyrillic, Greek, Arabic, Vietnamese, Latin extended,
and every other script the YouTube channel name space has been observed to
produce, while still stripping ``<>``, control characters, and the
delimiter/UI pollution that the original issue reported.
"""

from __future__ import annotations

import re
import unicodedata

_MAX_CHANNEL_TITLE_LEN = 200
_MAX_TITLE_LEN = 200
_EMAIL_CHANNEL_TITLE_MAX_LEN = 60
_EMAIL_TITLE_MAX_LEN = 80

_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")
_CONTROL = re.compile(r"[\x00-\x1f\x7f\u2028\u2029\ufeff\ufffe\uffff]")
_ELLIPSIS = "\u2026"

# Symbols that are never safe inside a channel/title even if they pass the
# category check (XSS vectors and common UI-delimiter pollution).
_BLOCKED_SYMBOLS = frozenset("<>&|\u2022\u00b7\u30fb")


def _is_safe_char(c: str) -> bool:
    """Return True if ``c`` is a letter, mark, digit, space, or safe punctuation."""
    cat = unicodedata.category(c)
    if cat[0] in ("L", "M"):
        return True
    if cat == "Nd":
        return True
    if cat == "Zs":
        return True
    if cat == "Po" and c not in _BLOCKED_SYMBOLS:
        return True
    if cat in ("Pc", "Pd", "Ps", "Pe"):
        return True
    if c in ("_", " "):
        return True
    return False


def _sanitize(value: object, max_len: int) -> str:
    """Strict-whitelist-clean text with a single-char ``…`` ellipsis on truncation."""
    if value is None:
        return ""
    text = str(value)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ")
    text = _CONTROL.sub(" ", text)
    text = _HTML_TAG.sub(" ", text)
    text = "".join(c if _is_safe_char(c) else " " for c in text)
    text = _WHITESPACE.sub(" ", text).strip(" _.-")
    if not text:
        return ""
    if len(text) > max_len:
        text = text[: max_len - 1] + _ELLIPSIS
    return text


def sanitize_channel_title(value: object) -> str:
    """Strict-whitelist-cleaned channel title (max 200 chars)."""
    return _sanitize(value, _MAX_CHANNEL_TITLE_LEN)


def sanitize_title(value: object) -> str:
    """Strict-whitelist-cleaned video title (max 200 chars)."""
    return _sanitize(value, _MAX_TITLE_LEN)


def sanitize_channel_title_for_email(
    value: object, max_len: int = _EMAIL_CHANNEL_TITLE_MAX_LEN
) -> str:
    """Channel title for email cells (default 60 chars + ``…``)."""
    return _sanitize(value, max_len)


def sanitize_title_for_email(
    value: object, max_len: int = _EMAIL_TITLE_MAX_LEN
) -> str:
    """Video title for email cells (default 80 chars + ``…``)."""
    return _sanitize(value, max_len)
