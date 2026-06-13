"""Quota estimation helpers for YouTube Data API v3."""

from __future__ import annotations

QUOTA_COSTS = {
    "search.list": 100,
    "videos.list": 1,
    "channels.list": 1,
    "playlistItems.list": 1,
}


def estimate_cost(method: str, calls: int = 1) -> int:
    return QUOTA_COSTS.get(method, 1) * max(0, calls)


def estimate_discovery(search_pages: int, video_batches: int) -> dict:
    return {
        "search_list_calls": search_pages,
        "videos_list_calls": video_batches,
        "playlist_items_list_calls": 0,
        "estimated_quota_cost": estimate_cost("search.list", search_pages) + estimate_cost("videos.list", video_batches),
    }


def summarize_calls(calls: dict[str, int]) -> dict:
    search_calls = int(calls.get("search", 0))
    video_calls = int(calls.get("videos", 0))
    channel_calls = int(calls.get("channels", 0))
    playlist_calls = int(calls.get("playlistItems", 0))
    return {
        "search_list_calls": search_calls,
        "videos_list_calls": video_calls,
        "channels_list_calls": channel_calls,
        "playlist_items_list_calls": playlist_calls,
        "estimated_quota_cost": (
            estimate_cost("search.list", search_calls)
            + estimate_cost("videos.list", video_calls)
            + estimate_cost("channels.list", channel_calls)
            + estimate_cost("playlistItems.list", playlist_calls)
        ),
    }
