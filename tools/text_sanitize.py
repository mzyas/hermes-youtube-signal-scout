"""Strict-whitelist text sanitization for user-facing fields.

Used at the trust boundary in :mod:`tools.video_hydrator` to keep polluted or
adversarial input from leaking into Markdown / HTML reports.
"""

from __future__ import annotations

import re
import unicodedata

_MAX_CHANNEL_TITLE_LEN = 200

_DISALLOWED = re.compile(
    r"[^\w \t\u3000\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff"
    r"\uff00-\uffef\-_().,&\[\]'\"!?+#@/]+"
)
_WHITESPACE = re.compile(r"\s+")
_CONTROL = re.compile(r"[\x00-\x1f\x7f\u2028\u2029\ufeff\ufffe\uffff]")


def sanitize_channel_title(value: object) -> str:
    """Return a strict-whitelist-cleaned channel title.

    Rules:
    - ``None`` and empty input become ``""``.
    - NFKC normalize, drop control/private-use code points.
    - Anything outside the whitelist is replaced with a single space.
    - Whitespace is collapsed and leading/trailing `` _.-`` are stripped.
    - Result is truncated to ``_MAX_CHANNEL_TITLE_LEN`` characters.
    """
    if value is None:
        return ""
    text = str(value)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ")
    text = _CONTROL.sub(" ", text)
    text = _DISALLOWED.sub(" ", text)
    text = _WHITESPACE.sub(" ", text).strip(" _.-")
    if not text:
        return ""
    if len(text) > _MAX_CHANNEL_TITLE_LEN:
        text = text[:_MAX_CHANNEL_TITLE_LEN].rstrip(" _.-")
    return text
