"""Resolve YouTube channels and uploads playlists."""

from __future__ import annotations


def resolve_channel(client, channel_id_or_handle: str) -> dict:
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