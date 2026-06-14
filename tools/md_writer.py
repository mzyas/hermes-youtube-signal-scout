"""Markdown and JSON report output for ranked YouTube results."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


def _table_text(value: object) -> str:
    return str(value or "").replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _safe_topic(value: object) -> str:
    topic = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value or "youtube-report")).strip(" ._")
    return topic or "youtube-report"


def _timestamp(value: object) -> str:
    if value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.astimezone(timezone.utc).strftime("%Y%m%d_%H%M%S")
        except ValueError:
            pass
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _duration(seconds: object) -> str:
    total = max(0, int(seconds or 0))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _views(video: dict) -> int:
    statistics = video.get("statistics") or {}
    return int(video.get("view_count") or statistics.get("view_count") or statistics.get("viewCount") or 0)


def _query(output: dict) -> str:
    query_plan = output.get("query_plan") or {}
    queries = query_plan.get("search_queries") or []
    return " | ".join(str(query) for query in queries)


def _quota_summary(output: dict) -> tuple[int, int, int]:
    quota = output.get("quota_usage_estimate") or {}
    search_calls = int(quota.get("search_list_calls") or 0)
    video_calls = int(quota.get("videos_list_calls") or 0)
    cost = int(quota.get("estimated_quota_cost") or quota.get("quota_cost") or 0)
    return cost, search_calls, video_calls


def build_json_report(output: dict, config: dict) -> dict:
    """Build canonical JSON with the same information as the Markdown report."""
    query_plan = output.get("query_plan") or {}
    cost, search_calls, video_calls = _quota_summary(output)
    videos = output.get("videos") or []
    rejected = output.get("rejected") or []
    return {
        "topic": output.get("topic") or config.get("topic") or "YouTube",
        "generated_at": output.get("created_at", ""),
        "search_queries": query_plan.get("search_queries") or [],
        "time_range": {
            "published_after": query_plan.get("published_after") or config.get("published_after"),
            "published_before": query_plan.get("published_before") or config.get("published_before"),
        },
        "quota": {
            "estimated_cost": cost,
            "search_calls": search_calls,
            "video_calls": video_calls,
        },
        "accepted_count": len(videos),
        "rejected_count": len(rejected),
        "videos": [
            {
                "rank": index,
                "topic_score": float(video.get("topic_score") or 0),
                "title": video.get("title", ""),
                "url": video.get("url", ""),
                "channel_title": video.get("channel_title", ""),
                "published_at": video.get("published_at", ""),
                "duration_seconds": int(video.get("duration_seconds") or 0),
                "view_count": _views(video),
                "score_components": video.get("score_components") or {},
                "ranking_signals": video.get("ranking_signals") or {},
            }
            for index, video in enumerate(videos, start=1)
        ],
        "rejected": [
            {
                "rank": index,
                "video_id": video.get("video_id"),
                "title": video.get("title", ""),
                "reason_code": video.get("reason_code"),
                "reason": video.get("reason", ""),
            }
            for index, video in enumerate(rejected, start=1)
        ],
        "run_stats": output.get("run_stats") or {},
        "warnings": output.get("warnings") or [],
    }


def render_markdown_report(output: dict, config: dict) -> str:
    """Render the canonical user-facing Markdown report."""
    videos = output.get("videos") or []
    rejected = output.get("rejected") or []
    query_plan = output.get("query_plan") or {}
    published_after = query_plan.get("published_after") or config.get("published_after") or "未指定"
    published_before = query_plan.get("published_before") or config.get("published_before") or "至今"
    cost, search_calls, video_calls = _quota_summary(output)

    lines = [
        f"# {output.get('topic') or config.get('topic') or 'YouTube'} · YouTube 信号报告",
        "",
        f"**生成时间:** {output.get('created_at', '')}",
        f"**搜索 query:** `{_query(output)}`",
        f"**时间范围:** {published_after} ~ {published_before}",
        f"**配额消耗:** {cost:,} units (search×{search_calls}, videos×{video_calls})",
        f"**通过/过滤:** {len(videos)}/{len(rejected)}",
        "",
        "---",
        "",
        f"## 通过筛选 ({len(videos)} 条)",
        "",
        "| # | 得分 | 标题 | 频道 | 发布日期 | 时长 | 播放量 |",
        "|---|------|------|------|----------|------|--------|",
    ]
    for index, video in enumerate(videos, start=1):
        title = _table_text(video.get("title"))
        url = str(video.get("url") or "")
        linked_title = f"[{title}]({url})" if url else title
        lines.append(
            f"| {index} | {float(video.get('topic_score') or 0):.2f} | {linked_title} | "
            f"{_table_text(video.get('channel_title'))} | {str(video.get('published_at') or '')[:10]} | "
            f"{_duration(video.get('duration_seconds'))} | {_views(video):,} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            f"## 被过滤 ({len(rejected)} 条)",
            "",
            "| # | 标题 | 原因 |",
            "|---|------|------|",
        ]
    )
    for index, video in enumerate(rejected, start=1):
        lines.append(
            f"| {index} | {_table_text(video.get('title'))} | {_table_text(video.get('reason'))} |"
        )

    version = config.get("version") or output.get("version")
    if not version:
        from .config import skill_version

        version = skill_version()
    lines.extend(["", "---", "", f"*由 hermes-youtube-signal-scout v{version} 生成*", ""])
    return "\n".join(lines)


def write_markdown_report(output: dict, output_dir: str, config: dict) -> str:
    """Render ranked output as Markdown and JSON, returning the Markdown path."""
    destination = Path(output_dir).expanduser()
    destination.mkdir(parents=True, exist_ok=True)
    stem = f"{_safe_topic(output.get('topic') or config.get('topic'))}_{_timestamp(output.get('created_at'))}"
    markdown_path = destination / f"{stem}.md"
    json_path = destination / f"{stem}.json"
    output["output_files"] = {
        "markdown": str(markdown_path),
        "json": str(json_path),
    }
    output["report_json"] = build_json_report(output, config)
    output["report_markdown"] = render_markdown_report(output, config)

    markdown_path.write_text(output["report_markdown"], encoding="utf-8", newline="\n")
    json_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return str(markdown_path)
