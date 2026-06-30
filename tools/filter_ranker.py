"""Local filtering and ranking for hydrated YouTube video metadata."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
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
ENTERTAINMENT_TERMS = [
    "娱乐",
    "娛樂",
    "综艺",
    "綜藝",
    "搞笑",
    "reaction",
    "prank",
    "celebrity gossip",
    "切り抜き",
    "お笑い",
    "バラエティ",
]
EXAM_TRAINING_CHANNEL_TERMS = [
    "academy",
    "coaching",
    "exam prep",
    "test prep",
    "公考",
    "公务员考试",
    "公務員試験",
    "考公",
    "考研",
    "备考",
    "備考",
    "培训学校",
    "培訓學校",
    "培训机构",
    "培訓機構",
    "考试院",
    "考試院",
    "补习班",
    "補習班",
    "学習塾",
    "予備校",
    "수험",
    "공무원 시험",
]
EXAM_TRAINING_CONTENT_TERMS = [
    "公务员考试",
    "公務員試験",
    "考公",
    "国考",
    "省考",
    "行测",
    "申论",
    "考研培训",
    "考研课程",
    "备考课程",
    "考试培训",
    "exam preparation course",
    "competitive exam coaching",
    "civil service exam",
    "公務員試験対策",
    "試験対策講座",
    "공무원 시험 준비",
]
EXAM_ABBREVIATIONS = ["upsc", "ias", "cse"]
EXAM_COACHING_QUALIFIERS = [
    "coaching",
    "preparation",
    "prep",
    "course",
    "batch",
    "classes",
    "test series",
    "mains",
    "prelims",
    "optional",
    "answer writing",
]


def _has_token_phrase(text: str, term: str) -> bool:
    return bool(
        re.search(
            rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])",
            text,
        )
    )


def _is_exam_training(
    video: dict,
    text: str,
    channel_title: str,
    config: dict,
) -> bool:
    known_institutions = config.get("blocked_exam_training_channel_names") or []
    if match_keywords(channel_title, known_institutions):
        return True
    if match_keywords(channel_title, EXAM_TRAINING_CHANNEL_TERMS):
        return True
    if match_keywords(text, EXAM_TRAINING_CONTENT_TERMS):
        return True
    combined_text = f"{channel_title} {text}"
    has_exam_abbreviation = any(
        _has_token_phrase(combined_text, term)
        for term in EXAM_ABBREVIATIONS
    )
    has_coaching_qualifier = any(
        _has_token_phrase(combined_text, term)
        for term in EXAM_COACHING_QUALIFIERS
    )
    return has_exam_abbreviation and has_coaching_qualifier


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


def _is_short(video: dict, max_duration_seconds: int = 60) -> bool:
    text = " ".join(
        [
            str(video.get("title", "")),
            str(video.get("description", "")),
            " ".join(video.get("tags") or []),
        ]
    ).casefold()
    return int(video.get("duration_seconds") or 0) <= max_duration_seconds or "#shorts" in text


def _quality_flags(video: dict, config: dict) -> dict[str, bool]:
    text = " ".join([
        str(video.get("title", "")),
        str(video.get("description", "")),
        " ".join(video.get("tags") or []),
    ]).casefold()
    channel_title = str(video.get("channel_title") or "").casefold()
    possible_ad = bool(match_keywords(text, LOW_QUALITY_TERMS))
    possible_entertainment = bool(match_keywords(text, ENTERTAINMENT_TERMS))
    possible_exam_training = _is_exam_training(video, text, channel_title, config)
    return {
        "is_short": _is_short(video, int(config.get("shorts_max_duration_seconds") or 60)),
        "possible_ad": possible_ad,
        "possible_entertainment": possible_entertainment,
        "possible_exam_training": possible_exam_training,
        "low_signal": possible_ad or possible_entertainment or possible_exam_training,
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
    if published_at and published_at > datetime.now(timezone.utc):
        return "发布时间在未来。"
    min_views = int(config.get("min_views") or 0)
    if _stat(video, "view_count") < min_views:
        return f"播放量低于 min_views：{min_views}。"
    max_duration = config.get("max_duration_seconds")
    if max_duration and int(video.get("duration_seconds") or 0) > int(max_duration):
        return f"时长超过 max_duration_seconds：{max_duration}。"
    if not config.get("include_shorts", False) and flags["is_short"]:
        return "include_shorts=false，剔除 Shorts。"
    if config.get("reject_possible_ads", False) and flags["possible_ad"]:
        return "疑似广告或推广内容。"
    if config.get("reject_entertainment", False) and flags["possible_entertainment"]:
        return "疑似娱乐或低信息密度内容。"
    if config.get("reject_exam_training", False) and flags["possible_exam_training"]:
        return "疑似考试培训、考公备考或培训机构内容。"
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


def _topic_relevance_score(matches: dict[str, list[str]], match_cap: int) -> float:
    return max(0.0, min(1.0, (
        0.40 * _component_score(matches.get("title", []), match_cap)
        + 0.25 * _component_score(matches.get("tags", []), match_cap)
        + 0.20 * _component_score(matches.get("description", []), match_cap)
        + 0.10 * _component_score(matches.get("topic_categories", []), match_cap)
        + 0.05 * _component_score(matches.get("channel_title", []), match_cap)
    )))


def _freshness_score(video: dict, config: dict, now: datetime) -> float:
    published_at = _parse_dt(video.get("published_at"))
    if not published_at:
        return 0.0
    published_at = published_at.astimezone(timezone.utc)
    window_end = _parse_dt(config.get("published_before")) or now
    window_end = min(window_end.astimezone(timezone.utc), now)
    window_start = _parse_dt(config.get("published_after"))
    if window_start:
        window_start = window_start.astimezone(timezone.utc)
        window_seconds = max(1.0, (window_end - window_start).total_seconds())
        seven_days_seconds = timedelta(days=7).total_seconds()
        if window_seconds <= seven_days_seconds:
            return 1.0
        age_seconds = max(0.0, (window_end - published_at).total_seconds())
        if age_seconds <= seven_days_seconds:
            return 1.0
        decay_span = window_seconds - seven_days_seconds
        decay_position = min(1.0, (age_seconds - seven_days_seconds) / decay_span)
        return 1.0 - 0.50 * decay_position
    window_start = window_end.replace() - timedelta(days=30)
    window_seconds = max(1.0, (window_end - window_start).total_seconds())
    position = (published_at - window_start).total_seconds() / window_seconds
    position = max(0.0, min(1.0, position))
    return position


def _view_velocity(video: dict, now: datetime) -> tuple[float, str]:
    views = _stat(video, "view_count")
    previous = video.get("previous_statistics") or {}
    captured_at = _parse_dt(previous.get("captured_at"))
    if captured_at:
        elapsed_hours = (now - captured_at.astimezone(timezone.utc)).total_seconds() / 3600
        if elapsed_hours > 0:
            delta = max(0, views - int(previous.get("view_count") or 0))
            return delta / elapsed_hours, "snapshot_delta"
    published_at = _parse_dt(video.get("published_at"))
    if not published_at:
        return 0.0, "unavailable"
    age_hours = max(1.0, (now - published_at.astimezone(timezone.utc)).total_seconds() / 3600)
    return views / age_hours, "lifetime_average"


def _velocity_percentiles(
    videos: list[dict], now: datetime
) -> dict[str, tuple[float, float, str]]:
    measured = [
        (str(video.get("video_id")), *_view_velocity(video, now))
        for video in videos
        if video.get("video_id")
    ]
    unique = sorted({value for _, value, _ in measured})
    if len(unique) <= 1:
        percentile_by_value = {value: 0.5 for value in unique}
    else:
        percentile_by_value = {
            value: index / (len(unique) - 1)
            for index, value in enumerate(unique)
        }
    return {
        video_id: (percentile_by_value.get(value, 0.0), value, source)
        for video_id, value, source in measured
    }


def _engagement_baseline(videos: list[dict]) -> float:
    views = sum(_stat(video, "view_count") for video in videos)
    interactions = sum(
        _stat(video, "like_count") + _stat(video, "comment_count") * 3
        for video in videos
    )
    return interactions / views if views > 0 else 0.0


def _smoothed_engagement_score(
    video: dict,
    baseline: float,
    prior_views: int,
) -> tuple[float, float]:
    views = _stat(video, "view_count")
    likes = _stat(video, "like_count")
    comments = _stat(video, "comment_count")
    smoothed_rate = (
        likes + comments * 3 + baseline * prior_views
    ) / max(1, views + prior_views)
    return max(0.0, min(1.0, smoothed_rate * 20)), smoothed_rate


def _channel_credibility_score(
    video: dict,
    matches: dict[str, list[str]],
    flags: dict[str, bool],
    config: dict,
) -> float:
    channel_id = str(video.get("channel_id") or "")
    configured = config.get("channel_quality_scores") or {}
    if channel_id in configured:
        return max(0.0, min(1.0, float(configured[channel_id])))
    if channel_id in set(config.get("trusted_channel_ids") or []):
        return 1.0
    stats = video.get("statistics") or {}
    metadata = 0.5 * bool(channel_id) + 0.5 * bool(video.get("channel_title"))
    topic_alignment = 1.0 if matches.get("channel_title") else 0.0
    quality_history_proxy = 0.0 if flags.get("low_signal") else 1.0
    statistics_completeness = sum(
        key in stats for key in ("view_count", "like_count", "comment_count")
    ) / 3
    return (
        0.25 * metadata
        + 0.25 * topic_alignment
        + 0.25 * quality_history_proxy
        + 0.25 * statistics_completeness
    )


def _information_completeness_score(video: dict) -> float:
    stats = video.get("statistics") or {}
    return (
        0.15 * bool(str(video.get("title") or "").strip())
        + 0.25 * min(1.0, len(str(video.get("description") or "").strip()) / 100)
        + 0.20 * min(1.0, len(video.get("tags") or []) / 3)
        + 0.10 * bool(video.get("category_id"))
        + 0.10 * (int(video.get("duration_seconds") or 0) > 0)
        + 0.20 * (
            sum(key in stats for key in ("view_count", "like_count", "comment_count")) / 3
        )
    )


def _score_components(
    video: dict,
    matches: dict[str, list[str]],
    flags: dict[str, bool],
    config: dict,
    now: datetime,
    velocity_score: float,
    engagement_baseline: float,
) -> tuple[dict[str, float], dict[str, object]]:
    match_cap = int(config.get("score_match_cap") or 3)
    engagement_score, smoothed_rate = _smoothed_engagement_score(
        video,
        engagement_baseline,
        int(config.get("engagement_prior_views") or 1000),
    )
    raw_scores = {
        "topic_relevance": _topic_relevance_score(matches, match_cap),
        "freshness": _freshness_score(video, config, now),
        "view_velocity": velocity_score,
        "smoothed_engagement": engagement_score,
        "channel_credibility": _channel_credibility_score(
            video, matches, flags, config
        ),
        "information_completeness": _information_completeness_score(video),
    }
    weights = {
        "topic_relevance": 0.45,
        "freshness": 0.15,
        "view_velocity": 0.15,
        "smoothed_engagement": 0.10,
        "channel_credibility": 0.10,
        "information_completeness": 0.05,
    }
    components = {
        name: round(weights[name] * value, 4)
        for name, value in raw_scores.items()
    }
    return components, {
        "raw_scores": {name: round(value, 4) for name, value in raw_scores.items()},
        "smoothed_engagement_rate": round(smoothed_rate, 6),
    }


def _topic_score(components: dict[str, float]) -> float:
    score = sum(components.values())
    return round(max(0.0, min(1.0, score)), 4)


def _accepted_video(
    video: dict,
    matches: dict[str, list[str]],
    score: float,
    components: dict[str, float],
    flags: dict[str, bool],
    candidate_index: int,
    ranking_signals: dict[str, object],
) -> dict:
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
        "score_components": components,
        "ranking_signals": ranking_signals,
        "quality_flags": flags,
        "reason": "命中主题字段并通过硬过滤，topic_score 达到阈值。",
        "_candidate_index": candidate_index,
    }


def _channel_key(video: dict) -> str:
    channel_id = str(video.get("channel_id") or "").strip()
    if channel_id:
        return f"id:{channel_id}"
    channel_title = " ".join(str(video.get("channel_title") or "").split()).casefold()
    if channel_title:
        return f"title:{channel_title}"
    return f"video:{video.get('video_id') or video.get('_candidate_index')}"


def _rank_key(video: dict) -> tuple:
    return (
        -float(video.get("topic_score") or 0),
    )


def _apply_channel_limit(
    accepted: list[dict],
    rejected: list[dict],
    max_per_channel: int,
) -> list[dict]:
    selected: list[dict] = []
    selected_by_channel: dict[str, list[dict]] = {}
    for video in sorted(accepted, key=_rank_key):
        channel_key = _channel_key(video)
        channel_videos = selected_by_channel.setdefault(channel_key, [])
        if len(channel_videos) < max_per_channel:
            channel_videos.append(video)
            selected.append(video)
            continue
        retained = channel_videos[0]
        if max_per_channel == 1:
            reason = (
                "同频道仅保留得分最高的视频；"
                f"已由 video_id={retained.get('video_id')} "
                f"(topic_score={float(retained.get('topic_score') or 0):.4f}) 替代。"
            )
        else:
            reason = (
                f"同频道最多保留 {max_per_channel} 条高分视频；"
                f"最高保留项为 video_id={retained.get('video_id')} "
                f"(topic_score={float(retained.get('topic_score') or 0):.4f})。"
            )
        rejected.append({
            "video_id": video.get("video_id"),
            "title": video.get("title", ""),
            "reason_code": "channel_limit_exceeded",
            "reason": reason,
        })
    for video in selected:
        video.pop("_candidate_index", None)
    return selected


def filter_and_rank(videos: list[dict], config: dict) -> dict:
    now = datetime.now(timezone.utc)
    eligible_videos = [
        video
        for video in videos
        if not _hard_reject_reason(video, config, _quality_flags(video, config))
    ]
    velocity_scores = _velocity_percentiles(eligible_videos, now)
    engagement_baseline = _engagement_baseline(eligible_videos)
    accepted: list[dict] = []
    rejected: list[dict] = []
    threshold_value = config.get("topic_score_threshold", 0.55)
    threshold = 0.55 if threshold_value is None else float(threshold_value)
    for candidate_index, video in enumerate(videos):
        flags = _quality_flags(video, config)
        reason = _hard_reject_reason(video, config, flags)
        if reason:
            rejected.append({"video_id": video.get("video_id"), "title": video.get("title", ""), "reason": reason})
            continue
        include_keywords = config.get("include_keywords") or []
        target_tags = config.get("target_tags") or []
        matches = collect_matches(video, include_keywords, target_tags)
        if not has_any_match(matches):
            rejected.append({
                "video_id": video.get("video_id"),
                "title": video.get("title", ""),
                "reason": "未命中 include_keywords 或 target_tags。",
            })
            continue
        velocity_score, velocity, velocity_source = velocity_scores.get(
            str(video.get("video_id")),
            (0.0, 0.0, "unavailable"),
        )
        components, ranking_signals = _score_components(
            video,
            matches,
            flags,
            config,
            now,
            velocity_score,
            engagement_baseline,
        )
        ranking_signals.update({
            "view_velocity_per_hour": round(velocity, 4),
            "view_velocity_source": velocity_source,
        })
        score = _topic_score(components)
        if score < threshold:
            rejected.append({"video_id": video.get("video_id"), "title": video.get("title", ""), "reason": f"topic_score {score} 低于阈值 {threshold}。"})
            continue
        accepted.append(
            _accepted_video(
                video,
                matches,
                score,
                components,
                flags,
                candidate_index,
                ranking_signals,
            )
        )
    max_per_channel = max(1, int(config.get("max_videos_per_channel") or 1))
    accepted = _apply_channel_limit(
        accepted,
        rejected,
        max_per_channel,
    )
    limit = int(config.get("max_results") or len(accepted) or 1)
    result = {
        "run_id": f"ytss_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}",
        "skill": "hermes-youtube-signal-scout",
        "version": config.get("version", "0.0.0"),
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
