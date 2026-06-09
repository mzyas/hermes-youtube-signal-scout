"""Discovery-mode helpers for YouTube search.list."""

from __future__ import annotations

from .quota_guard import estimate_discovery


def build_query(include_keywords: list[str], exclude_keywords: list[str] | None = None) -> str:
    include = [item.strip() for item in include_keywords or [] if item and item.strip()]
    exclude = [item.strip() for item in exclude_keywords or [] if item and item.strip()]
    include_part = "|".join(include)
    exclude_part = " ".join(f"-{term}" for term in exclude)
    return " ".join(part for part in [include_part, exclude_part] if part).strip()


def search_videos(client, config: dict) -> dict:
    max_pages = int(config.get("max_search_pages") or 1)
    max_results = min(50, int(config.get("max_results") or 25))
    query = build_query(config.get("include_keywords") or [config.get("topic", "")], config.get("exclude_keywords") or [])
    params = {
        "part": "snippet",
        "type": "video",
        "q": query,
        "order": config.get("order", "date"),
        "maxResults": max_results,
        "safeSearch": config.get("safe_search", "moderate"),
    }
    for key in ["publishedAfter", "publishedBefore", "regionCode", "relevanceLanguage"]:
        snake = {
            "publishedAfter": "published_after",
            "publishedBefore": "published_before",
            "regionCode": "region_code",
            "relevanceLanguage": "relevance_language",
        }[key]
        if config.get(snake):
            params[key] = config[snake]
    video_ids: list[str] = []
    page_token = None
    pages = 0
    while pages < max_pages:
        request_params = dict(params)
        if page_token:
            request_params["pageToken"] = page_token
        payload = client.get("search", request_params)
        pages += 1
        for item in payload.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if video_id and video_id not in video_ids:
                video_ids.append(video_id)
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    batches = 1 if video_ids else 0
    return {
        "video_ids": video_ids,
        "query_plan": {"search_queries": [query], **params},
        "quota_usage_estimate": estimate_discovery(pages, batches),
    }