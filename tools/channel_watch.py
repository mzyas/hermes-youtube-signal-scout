"""Channel-watch helpers using uploads playlists."""

from __future__ import annotations


def fetch_latest_uploads(client, uploads_playlist_id: str, max_results: int = 20) -> list[str]:
    payload = client.get(
        "playlistItems",
        {
            "part": "contentDetails",
            "playlistId": uploads_playlist_id,
            "maxResults": min(50, max_results),
        },
    )
    video_ids: list[str] = []
    for item in payload.get("items", []):
        video_id = (item.get("contentDetails") or {}).get("videoId")
        if video_id and video_id not in video_ids:
            video_ids.append(video_id)
    return video_ids