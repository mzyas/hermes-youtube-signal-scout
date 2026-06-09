"""Hydrate YouTube video IDs into normalized video dictionaries."""

from __future__ import annotations

from .duration import parse_youtube_duration


def chunks(values: list[str], size: int = 50):
    for index in range(0, len(values), size):
        yield values[index : index + size]


def parse_video_resource(item: dict) -> dict:
    snippet = item.get("snippet") or {}
    content = item.get("contentDetails") or {}
    statistics = item.get("statistics") or {}
    video_id = item.get("id")
    duration_seconds = parse_youtube_duration(content.get("duration", "PT0S"))
    return {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
        "title": snippet.get("title", ""),
        "channel_id": snippet.get("channelId", ""),
        "channel_title": snippet.get("channelTitle", ""),
        "published_at": snippet.get("publishedAt", ""),
        "description": snippet.get("description", ""),
        "tags": snippet.get("tags", []),
        "category_id": snippet.get("categoryId"),
        "duration_seconds": duration_seconds,
        "statistics": {
            "view_count": int(statistics.get("viewCount", 0)),
            "like_count": int(statistics.get("likeCount", 0)),
            "comment_count": int(statistics.get("commentCount", 0)),
        },
        "topic_categories": (item.get("topicDetails") or {}).get("topicCategories", []),
        "raw_json": item,
    }


def hydrate_videos(client, video_ids: list[str], batch_size: int = 50) -> list[dict]:
    hydrated: list[dict] = []
    for batch in chunks(video_ids, batch_size):
        payload = client.get(
            "videos",
            {
                "part": "snippet,contentDetails,statistics,topicDetails",
                "id": ",".join(batch),
                "maxResults": len(batch),
            },
        )
        hydrated.extend(parse_video_resource(item) for item in payload.get("items", []))
    return hydrated