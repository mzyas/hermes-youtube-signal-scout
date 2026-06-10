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


def _render_markdown(output: dict, config: dict) -> str:
    videos = output.get("videos") or []
    rejected = output.get("rejected") or []
    query_plan = output.get("query_plan") or {}
    published_after = query_plan.get("published_after") or config.get("published_after") or "未指定"
    published_before = query_plan.get("published_before") or config.get("published_before") or "至今"
    cost, search_calls, video_calls = _quota_summary(output)

    lines = [
        f"# {output.get('topic') or config.get('topic') or 'YouTube'} · 最近7天 YouTube 信号",
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

    version = config.get("version") or output.get("version") or "0.1.0"
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

    markdown_path.write_text(_render_markdown(output, config), encoding="utf-8", newline="\n")
    json_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return str(markdown_path)
