"""Local filtering and ranking for hydrated YouTube video metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .text_matcher import collect_matches, has_any_match, match_keywords

LOW_QUALITY_TERMS = [
    "sponsored",
    "promo",
    "affiliate",
    "限时优惠",
    "免费领取",
    "暴富",
    "副業で月収",
    "稼げる",
    "案件紹介だけ",
]


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _stat(video: dict, name: str) -> int:
    stats = video.get("statistics") or {}
    if name in video:
        return int(video.get(name) or 0)
    return int(stats.get(name) or stats.get(name.replace("_count", "Count")) or 0)


def _is_short(video: dict) -> bool:
    text = " ".join(
        [
            str(video.get("title", "")),
            str(video.get("description", "")),
            " ".join(video.get("tags") or []),
        ]
    ).casefold()
    return int(video.get("duration_seconds") or 0) <= 60 or "#shorts" in text


def _quality_flags(video: dict) -> dict[str, bool]:
    text = f"{video.get('title', '')} {video.get('description', '')}".casefold()
    possible_ad = bool(match_keywords(text, LOW_QUALITY_TERMS))
    return {
        "is_short": _is_short(video),
        "possible_ad": possible_ad,
        "low_signal": possible_ad,
    }


def _hard_reject_reason(video: dict, config: dict, flags: dict[str, bool]) -> str | None:
    if not video.get("video_id"):
        return "缺少 videoId。"
    if not video.get("title") or not video.get("published_at"):
        return "缺少必要 snippet 字段。"
    if video.get("channel_id") in set(config.get("blocklisted_channel_ids") or []):
        return "频道在 blocklist。"
    published_at = _parse_dt(video.get("published_at"))
    after = _parse_dt(config.get("published_after"))
    before = _parse_dt(config.get("published_before"))
    if published_at and after and published_at < after:
        return "不在发布时间窗口内。"
    if published_at and before and published_at > before:
        return "不在发布时间窗口内。"
    min_views = int(config.get("min_views") or 0)
    if _stat(video, "view_count") < min_views:
        return f"播放量低于 min_views：{min_views}。"
    max_duration = config.get("max_duration_seconds")
    if max_duration and int(video.get("duration_seconds") or 0) > int(max_duration):
        return f"时长超过 max_duration_seconds：{max_duration}。"
    if not config.get("include_shorts", False) and flags["is_short"]:
        return "include_shorts=false，剔除 Shorts。"
    exclude_keywords = config.get("exclude_keywords") or []
    exclude_text = " ".join(
        [
            str(video.get("title", "")),
            str(video.get("description", "")),
            " ".join(video.get("tags") or []),
        ]
    )
    excluded = match_keywords(exclude_text, exclude_keywords)
    if excluded:
        return f"命中排除词：{', '.join(excluded)}。"
    return None


def _component_score(matches: list[str], match_cap: int = 3) -> float:
    if match_cap <= 0:
        return 0.0
    return min(1.0, len(set(matches)) / match_cap)


def _freshness_score(video: dict, now: datetime) -> float:
    published_at = _parse_dt(video.get("published_at"))
    if not published_at:
        return 0.0
    days = max(0.0, (now - published_at.astimezone(timezone.utc)).total_seconds() / 86400)
    if days <= 1:
        return 1.0
    if days >= 30:
        return 0.0
    return max(0.0, 1.0 - (days / 30.0))


def _engagement_score(video: dict) -> float:
    views = _stat(video, "view_count")
    likes = _stat(video, "like_count")
    comments = _stat(video, "comment_count")
    if views <= 0:
        return 0.0
    ratio = (likes + comments * 2) / views
    return max(0.0, min(1.0, ratio * 20))


def _topic_score(video: dict, matches: dict[str, list[str]], config: dict, now: datetime) -> float:
    match_cap = int(config.get("score_match_cap") or 3)
    channel_score = 1.0 if matches.get("channel_title") else 0.5
    score = (
        0.30 * _component_score(matches.get("title", []), match_cap)
        + 0.25 * _component_score(matches.get("tags", []), match_cap)
        + 0.20 * _component_score(matches.get("description", []), match_cap)
        + 0.10 * channel_score
        + 0.10 * _freshness_score(video, now)
        + 0.05 * _engagement_score(video)
    )
    return round(max(0.0, min(1.0, score)), 4)


def _accepted_video(video: dict, matches: dict[str, list[str]], score: float, flags: dict[str, bool]) -> dict:
    video_id = video["video_id"]
    return {
        "video_id": video_id,
        "url": video.get("url") or f"https://www.youtube.com/watch?v={video_id}",
        "title": video.get("title", ""),
        "channel_id": video.get("channel_id", ""),
        "channel_title": video.get("channel_title", ""),
        "published_at": video.get("published_at", ""),
        "description_excerpt": (video.get("description") or "")[:300],
        "tags": video.get("tags") or [],
        "category_id": video.get("category_id"),
        "duration_seconds": int(video.get("duration_seconds") or 0),
        "statistics": video.get("statistics") or {},
        "matched_fields": matches,
        "topic_score": score,
        "quality_flags": flags,
        "reason": "命中主题字段并通过硬过滤，topic_score 达到阈值。",
    }


def filter_and_rank(videos: list[dict], config: dict) -> dict:
    now = datetime.now(timezone.utc)
    accepted: list[dict] = []
    rejected: list[dict] = []
    threshold_value = config.get("topic_score_threshold", 0.55)
    threshold = 0.55 if threshold_value is None else float(threshold_value)
    for video in videos:
        flags = _quality_flags(video)
        reason = _hard_reject_reason(video, config, flags)
        if reason:
            rejected.append({"video_id": video.get("video_id"), "title": video.get("title", ""), "reason": reason})
            continue
        matches = collect_matches(video, config.get("include_keywords") or [], config.get("target_tags") or [])
        if not has_any_match(matches):
            rejected.append({"video_id": video.get("video_id"), "title": video.get("title", ""), "reason": "未命中 include_keywords 或 target_tags。"})
            continue
        score = _topic_score(video, matches, config, now)
        if score < threshold:
            rejected.append({"video_id": video.get("video_id"), "title": video.get("title", ""), "reason": f"topic_score {score} 低于阈值 {threshold}。"})
            continue
        accepted.append(_accepted_video(video, matches, score, flags))
    accepted.sort(key=lambda item: item["topic_score"], reverse=True)
    limit = int(config.get("max_results") or len(accepted) or 1)
    result = {
        "run_id": f"ytss_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}",
        "skill": "hermes-youtube-signal-scout",
        "topic": config.get("topic", ""),
        "mode": config.get("mode", "discovery"),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "query_plan": {
            "search_queries": config.get("search_queries", []),
            "published_after": config.get("published_after"),
            "published_before": config.get("published_before"),
            "region_code": config.get("region_code"),
            "relevance_language": config.get("relevance_language"),
            "order": config.get("order", "date"),
        },
        "quota_usage_estimate": config.get("quota_usage_estimate", {}),
        "videos": accepted[:limit],
        "rejected": rejected,
    }
    output_dir = config.get("output_dir")
    if output_dir:
        from .md_writer import write_markdown_report

        write_markdown_report(result, str(output_dir), config)
    return result
