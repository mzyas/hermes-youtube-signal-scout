"""Utilities for YouTube ISO 8601 duration values."""

from __future__ import annotations

import re

_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


def parse_youtube_duration(duration: str) -> int:
    """Convert a YouTube ISO 8601 duration such as PT12M35S to seconds."""
    if not duration or not isinstance(duration, str):
        raise ValueError("duration must be a non-empty string")
    match = _DURATION_RE.match(duration)
    if not match:
        raise ValueError(f"invalid YouTube duration: {duration}")
    parts = {name: int(value or 0) for name, value in match.groupdict().items()}
    return (
        parts["days"] * 86400
        + parts["hours"] * 3600
        + parts["minutes"] * 60
        + parts["seconds"]
    )