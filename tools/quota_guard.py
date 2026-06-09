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