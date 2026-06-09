"""Keyword and tag matching helpers."""

from __future__ import annotations

from collections.abc import Iterable


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).casefold().strip()


def match_keywords(text: object, keywords: Iterable[str]) -> list[str]:
    haystack = normalize_text(text)
    matches: list[str] = []
    for keyword in keywords or []:
        needle = normalize_text(keyword)
        if needle and needle in haystack:
            matches.append(keyword)
    return matches


def match_list(values: Iterable[object], keywords: Iterable[str]) -> list[str]:
    found: list[str] = []
    for value in values or []:
        for match in match_keywords(value, keywords):
            if match not in found:
                found.append(match)
    return found


def collect_matches(video: dict, include_keywords: list[str], target_tags: list[str]) -> dict[str, list[str]]:
    tags = video.get("tags") or []
    topic_categories = video.get("topic_categories") or video.get("topicDetails", {}).get("topicCategories", [])
    tag_needles = list(dict.fromkeys([*(include_keywords or []), *(target_tags or [])]))
    return {
        "title": match_keywords(video.get("title", ""), include_keywords),
        "description": match_keywords(video.get("description", ""), include_keywords),
        "tags": match_list(tags, tag_needles),
        "channel_title": match_keywords(video.get("channel_title", ""), include_keywords),
        "topic_categories": match_list(topic_categories, include_keywords),
    }


def has_any_match(matches: dict[str, list[str]]) -> bool:
    return any(bool(values) for values in matches.values())