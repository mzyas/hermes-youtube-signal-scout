"""Discovery-mode helpers for YouTube search.list."""

from __future__ import annotations

DEFAULT_MAX_QUERY_TERMS = 4
DEFAULT_MAX_QUERY_CHARS = 80
ZONE_REGION_CODES = {
    "east_asia": ["JP", "KR", "TW", "HK"],
    "europe": ["GB", "DE", "FR"],
    "north_america": ["US", "CA"],
}
DEFAULT_REGION_TIERS = [
    ["US", "JP", "HK", "GB"],
    ["KR", "TW", "DE", "FR", "CA"],
]
REGION_SEARCH_LANGUAGES = {
    "US": "en",
    "JP": "ja",
    "HK": "zh-Hant",
    "GB": "en",
    "KR": "ko",
    "TW": "zh-Hant",
    "DE": "de",
    "FR": "fr",
    "CA": "en",
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


def resolve_region_tiers(config: dict) -> list[list[str | None]]:
    if config.get("region_codes") or config.get("region_code"):
        return [resolve_region_codes(config)]
    explicit_tiers = config.get("region_priority_tiers") or []
    if explicit_tiers:
        tiers = [_dedupe_terms(tier) for tier in explicit_tiers]
        return [tier for tier in tiers if tier]
    return [list(tier) for tier in DEFAULT_REGION_TIERS]


def query_for_region(config: dict, region_code: str | None) -> tuple[str, str | None]:
    """Return the localized query and search-language hint for one region."""
    language = REGION_SEARCH_LANGUAGES.get(region_code) if region_code else None
    localized_queries = config.get("localized_queries") or {}
    terms = localized_queries.get(language) if language and isinstance(localized_queries, dict) else None
    if not isinstance(terms, list):
        terms = None
    query = config.get("search_query") or build_query(
        terms or config.get("include_keywords") or [config.get("topic", "")],
        max_terms=int(config.get("max_query_terms") or DEFAULT_MAX_QUERY_TERMS),
        max_chars=int(config.get("max_query_chars") or DEFAULT_MAX_QUERY_CHARS),
    )
    return query, config.get("relevance_language") or language


def search_videos(
    client,
    config: dict,
    page_tokens: dict[str, str] | None = None,
    max_pages_override: int | None = None,
    region_codes_override: list[str | None] | None = None,
) -> dict:
    max_pages = (
        int(max_pages_override)
        if max_pages_override is not None
        else int(config.get("max_search_pages") or 1)
    )
    candidates_per_page = min(50, int(config.get("candidates_per_page") or 50))
    base_params = {
        "part": "snippet",
        "type": "video",
        "order": config.get("order", "relevance"),
        "maxResults": candidates_per_page,
        "safeSearch": config.get("safe_search", "moderate"),
    }
    for key in ["publishedAfter", "publishedBefore"]:
        snake = {
            "publishedAfter": "published_after",
            "publishedBefore": "published_before",
        }[key]
        if config.get(snake):
            base_params[key] = config[snake]
    video_ids: list[str] = []
    pages = 0
    region_codes = region_codes_override or resolve_region_codes(config)
    next_page_tokens: dict[str, str] = {}
    region_queries: list[dict] = []
    for region_code in region_codes:
        query, relevance_language = query_for_region(config, region_code)
        region_queries.append({
            "region_code": region_code,
            "language": relevance_language,
            "query": query,
        })
        token_key = region_code or "__global__"
        page_token = (page_tokens or {}).get(token_key)
        if page_tokens is not None and not page_token:
            continue
        region_pages = 0
        while region_pages < max_pages:
            request_params = dict(base_params)
            request_params["q"] = query
            if region_code:
                request_params["regionCode"] = region_code
            if relevance_language:
                request_params["relevanceLanguage"] = relevance_language
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
        if page_token:
            next_page_tokens[token_key] = page_token
    return {
        "video_ids": video_ids,
        "query_plan": {
            "search_queries": _dedupe_terms(
                [item["query"] for item in region_queries]
            ),
            "region_queries": region_queries,
            "region_codes": [code for code in region_codes if code],
            "zones": config.get("zones") or [],
            **base_params,
        },
        "page_count": pages,
        "next_page_tokens": next_page_tokens,
    }
