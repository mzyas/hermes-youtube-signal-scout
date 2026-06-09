"""Discovery-mode helpers for YouTube search.list."""

from __future__ import annotations

from .quota_guard import estimate_discovery

DEFAULT_MAX_QUERY_TERMS = 4
DEFAULT_MAX_QUERY_CHARS = 80


def _dedupe_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for term in terms or []:
        cleaned = str(term).strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def build_query(
    include_keywords: list[str],
    exclude_keywords: list[str] | None = None,
    max_terms: int = DEFAULT_MAX_QUERY_TERMS,
    max_chars: int = DEFAULT_MAX_QUERY_CHARS,
) -> str:
    """Build a short recall query for YouTube search.list.

    YouTube silently returns poor or empty results for long Boolean queries.
    Exclude keywords are intentionally ignored here; they belong to local
    filtering after hydration.
    """
    del exclude_keywords
    selected: list[str] = []
    for term in _dedupe_terms(include_keywords):
        if len(selected) >= max_terms:
            break
        candidate = "|".join([*selected, term]) if selected else term
        if selected and len(candidate) > max_chars:
            break
        selected.append(term)
        if len(term) >= max_chars:
            break
    return "|".join(selected)


def search_videos(client, config: dict) -> dict:
    max_pages = int(config.get("max_search_pages") or 1)
    max_results = min(50, int(config.get("max_results") or 25))
    query = config.get("search_query") or build_query(
        config.get("include_keywords") or [config.get("topic", "")],
        max_terms=int(config.get("max_query_terms") or DEFAULT_MAX_QUERY_TERMS),
        max_chars=int(config.get("max_query_chars") or DEFAULT_MAX_QUERY_CHARS),
    )
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