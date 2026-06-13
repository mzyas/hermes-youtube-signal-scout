"""Resolve YouTube channels and uploads playlists."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from .errors import ConfigurationError

_CHANNEL_ID_RE = re.compile(r"^UC[0-9A-Za-z_-]{20,}$")


def parse_channel_reference(value: str) -> str:
    reference = str(value or "").strip()
    if not reference:
        raise ConfigurationError("channel reference must not be empty")
    if reference.startswith("@") or _CHANNEL_ID_RE.match(reference):
        return reference
    parsed = urlparse(reference)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.casefold() not in {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
    }:
        raise ConfigurationError(f"unsupported YouTube channel reference: {reference}")
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        raise ConfigurationError(f"invalid YouTube channel URL: {reference}")
    if parts[0].startswith("@"):
        return parts[0]
    if len(parts) >= 2 and parts[0] == "channel" and _CHANNEL_ID_RE.match(parts[1]):
        return parts[1]
    raise ConfigurationError(
        "channel URLs must use /channel/UC... or /@handle; custom /c/ and /user/ URLs are unsupported"
    )


def resolve_channel(client, channel_id_or_handle: str) -> dict:
    channel_id_or_handle = parse_channel_reference(channel_id_or_handle)
    params = {"part": "snippet,contentDetails,statistics"}
    if channel_id_or_handle.startswith("@"):
        params["forHandle"] = channel_id_or_handle
    else:
        params["id"] = channel_id_or_handle
    payload = client.get("channels", params)
    items = payload.get("items", [])
    if not items:
        raise ValueError(f"channel not found: {channel_id_or_handle}")
    item = items[0]
    snippet = item.get("snippet") or {}
    uploads = (item.get("contentDetails") or {}).get("relatedPlaylists", {}).get("uploads")
    return {
        "channel_id": item.get("id"),
        "channel_title": snippet.get("title", ""),
        "uploads_playlist_id": uploads,
        "raw_json": item,
    }
