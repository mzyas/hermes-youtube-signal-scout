"""Discovery-mode helpers for YouTube search.list."""

from __future__ import annotations

DEFAULT_MAX_QUERY_TERMS = 4
DEFAULT_MAX_QUERY_CHARS = 80
ZONE_REGION_CODES = {
    "east_asia": ["JP", "KR", "TW", "HK"],
    "europe": ["GB", "DE", "FR"],
    "north_america": ["US", "CA"],
}


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


def resolve_region_codes(config: dict) -> list[str | None]:
    explicit = config.get("region_codes") or []
    if explicit:
        return _dedupe_terms(explicit)
    if config.get("region_code"):
        return [str(config["region_code"])]
    zones = config.get("zones") or []
    codes: list[str] = []
    for zone in zones:
        codes.extend(ZONE_REGION_CODES.get(str(zone), []))
    return _dedupe_terms(codes) or [None]


def search_videos(client, config: dict) -> dict:
    max_pages = int(config.get("max_search_pages") or 1)
    candidates_per_page = min(50, int(config.get("candidates_per_page") or 50))
    query = config.get("search_query") or build_query(
        config.get("include_keywords") or [config.get("topic", "")],
        max_terms=int(config.get("max_query_terms") or DEFAULT_MAX_QUERY_TERMS),
        max_chars=int(config.get("max_query_chars") or DEFAULT_MAX_QUERY_CHARS),
    )
    base_params = {
        "part": "snippet",
        "type": "video",
        "q": query,
        "order": config.get("order", "date"),
        "maxResults": candidates_per_page,
        "safeSearch": config.get("safe_search", "moderate"),
    }
    for key in ["publishedAfter", "publishedBefore", "relevanceLanguage"]:
        snake = {
            "publishedAfter": "published_after",
            "publishedBefore": "published_before",
            "relevanceLanguage": "relevance_language",
        }[key]
        if config.get(snake):
            base_params[key] = config[snake]
    video_ids: list[str] = []
    pages = 0
    region_codes = resolve_region_codes(config)
    for region_code in region_codes:
        page_token = None
        region_pages = 0
        while region_pages < max_pages:
            request_params = dict(base_params)
            if region_code:
                request_params["regionCode"] = region_code
            if page_token:
                request_params["pageToken"] = page_token
            payload = client.get("search", request_params)
            pages += 1
            region_pages += 1
            for item in payload.get("items", []):
                video_id = item.get("id", {}).get("videoId")
                if video_id and video_id not in video_ids:
                    video_ids.append(video_id)
            page_token = payload.get("nextPageToken")
            if not page_token:
                break
    return {
        "video_ids": video_ids,
        "query_plan": {
            "search_queries": [query],
            "region_codes": [code for code in region_codes if code],
            "zones": config.get("zones") or [],
            **base_params,
        },
        "page_count": pages,
    }
