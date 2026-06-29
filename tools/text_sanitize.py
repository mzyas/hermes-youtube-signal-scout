"""Strict-whitelist text sanitization for user-facing fields.

Used at the trust boundary in :mod:`tools.video_hydrator` to keep polluted or
adversarial input from leaking into Markdown / HTML reports.
"""

from __future__ import annotations

import re
import unicodedata

_MAX_CHANNEL_TITLE_LEN = 200
_MAX_TITLE_LEN = 200
_EMAIL_CHANNEL_TITLE_MAX_LEN = 60
_EMAIL_TITLE_MAX_LEN = 80

_DISALLOWED_TITLE = re.compile(
    r"[^\w \t\u3000\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff"
    r"\uff00-\uffef\-_().,&\[\]'\"!?+#@/]+"
)
_DISALLOWED_CHANNEL = re.compile(
    r"[^\w \t\u3000\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff"
    r"\uff00-\uffef\-_().,&\[\]'\"!?+#@/]+"
)
_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")
_CONTROL = re.compile(r"[\x00-\x1f\x7f\u2028\u2029\ufeff\ufffe\uffff]")


def _apply_strict_whitelist(value: object, disallowed: re.Pattern, max_len: int) -> str:
    if value is None:
        return ""
    text = str(value)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ")
    text = _CONTROL.sub(" ", text)
    text = disallowed.sub(" ", text)
    text = _WHITESPACE.sub(" ", text).strip(" _.-")
    if not text:
        return ""
    if len(text) > max_len:
        text = text[:max_len].rstrip(" _.-")
    return text


def sanitize_channel_title(value: object) -> str:
    """Return a strict-whitelist-cleaned channel title (max 200 chars)."""
    return _apply_strict_whitelist(value, _DISALLOWED_CHANNEL, _MAX_CHANNEL_TITLE_LEN)


def sanitize_title(value: object) -> str:
    """Return a strict-whitelist-cleaned video title (max 200 chars)."""
    return _apply_strict_whitelist(value, _DISALLOWED_TITLE, _MAX_TITLE_LEN)


def sanitize_channel_title_for_email(
    value: object, max_len: int = _EMAIL_CHANNEL_TITLE_MAX_LEN
) -> str:
    """Channel title for email cells (default 60 chars).

    60 is the lower bound of the 60-80 range recommended for email table cells
    so that long CJK / multi-word channel names wrap to 1-2 lines inside the
    220px-wide channel column without inflating the row height.
    """
    return _apply_strict_whitelist(value, _DISALLOWED_CHANNEL, max_len)


def sanitize_title_for_email(
    value: object, max_len: int = _EMAIL_TITLE_MAX_LEN
) -> str:
    """Video title for email cells (default 80 chars).

    80 is the upper bound of the 60-80 range, fitting the 400px-wide title
    column with 1-3 wrapped lines. Also strips HTML tags defensively.
    """
    if value is None:
        return ""
    text = str(value)
    text = _HTML_TAG.sub(" ", text)
    return _apply_strict_whitelist(text, _DISALLOWED_TITLE, max_len)
