"""Render the weekly email as a complete HTML document.

The renderer is intentionally self-contained: it reads the template from
``tools/email_template.html`` and substitutes topic sections plus an optional
failure block.  Output is intended to survive Outlook (Word engine) and Gmail
with inline styles and ``<table>``-only layout.
"""

from __future__ import annotations

import html
from pathlib import Path

from .text_sanitize import (
    sanitize_channel_title_for_email,
    sanitize_title_for_email,
)

TEMPLATE_PATH = Path(__file__).parent / "email_template.html"

_CELL_BASE = "border:1px solid #d9d9d9;padding:8px 10px;color:#111111;"

_TABLE_STYLE = (
    "border-collapse:collapse;width:100%;"
    "font-family:Arial,sans-serif;font-size:13px;"
    "background-color:#ffffff;border:1px solid #d9d9d9;"
)
_HEADER_STYLE = "background-color:#f2f2f2;"


def _format_duration(seconds: object) -> str:
    total = max(0, int(seconds or 0))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _render_video_row(video: dict) -> str:
    title = sanitize_title_for_email(video.get("title", ""))
    channel = sanitize_channel_title_for_email(video.get("channel_title", ""))
    url = html.escape(str(video.get("url", "")))
    title_escaped = html.escape(title)
    channel_escaped = html.escape(channel)
    rank = html.escape(str(video.get("rank", "")))
    score = float(video.get("topic_score") or 0)
    published_at = html.escape(str(video.get("published_at") or "")[:10])
    duration = html.escape(_format_duration(video.get("duration_seconds")))
    views = int(video.get("view_count") or 0)
    return (
        "<tr>"
        f'<td style="{_CELL_BASE}">{rank}</td>'
        f'<td style="{_CELL_BASE}">{score:.2f}</td>'
        f'<td style="{_CELL_BASE}max-width:400px;word-break:break-word;white-space:normal;">'
        f'<a href="{url}" style="color:#0f62fe;text-decoration:none;">{title_escaped}</a>'
        "</td>"
        f'<td style="{_CELL_BASE}max-width:220px;word-break:break-word;white-space:normal;">{channel_escaped}</td>'
        f'<td style="{_CELL_BASE}white-space:nowrap;">{published_at}</td>'
        f'<td style="{_CELL_BASE}white-space:nowrap;">{duration}</td>'
        f'<td style="{_CELL_BASE}white-space:nowrap;text-align:right;">{views:,}</td>'
        "</tr>"
    )


def _render_topic_section(topic: str, videos: list[dict]) -> str:
    rows = "".join(_render_video_row(v) for v in videos) or (
        "<tr><td colspan=\"7\" style=\"" + _CELL_BASE + "color:#666666;font-style:italic;\">"
        "本主题暂无通过筛选的视频。"
        "</td></tr>"
    )
    return (
        f'<h2 style="margin:24px 0 8px;font-size:16px;color:#111111;font-weight:700;">'
        f"{html.escape(topic)}</h2>"
        f'<table role="presentation" border="1" cellpadding="10" cellspacing="0" style="{_TABLE_STYLE}">'
        "<thead>"
        f'<tr style="{_HEADER_STYLE}">'
        "<th>#</th><th>得分</th><th>标题</th><th>频道</th><th>发布时间</th><th>时长</th><th>播放量</th>"
        "</tr>"
        "</thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
    )


def _render_failure_section(failures: list[dict]) -> str:
    if not failures:
        return ""
    rows = "".join(
        "<tr>"
        f'<td style="{_CELL_BASE}"><strong>{html.escape(str(f.get("topic", "")))}</strong></td>'
        f'<td style="{_CELL_BASE}">{html.escape(str((f.get("error") or {}).get("type", "")))}</td>'
        f'<td style="{_CELL_BASE}max-width:480px;word-break:break-word;white-space:normal;">'
        f"{html.escape(str((f.get('error') or {}).get('message', '')))}"
        "</td>"
        "</tr>"
        for f in failures
    )
    return (
        '<h2 style="margin:32px 0 8px;font-size:16px;color:#a40000;font-weight:700;">失败主题</h2>'
        f'<table role="presentation" border="1" cellpadding="10" cellspacing="0" style="{_TABLE_STYLE}">'
        "<thead>"
        f'<tr style="background-color:#fff0f0;">'
        "<th>主题</th><th>错误类型</th><th>详情</th>"
        "</tr>"
        "</thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
    )


def render_email_html(
    subject: str,
    runs: list[dict],
    failures: list[dict],
    generated_at: str,
) -> str:
    """Render the complete weekly email as an HTML string.

    ``runs`` items are expected to expose ``topic`` and a ``videos`` list
    (typically ``result['report_json']['videos']`` from the weekly runner).
    """
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    topic_sections = "".join(
        _render_topic_section(
            str(run.get("topic", "")),
            list(run.get("videos") or []),
        )
        for run in runs
    )
    return (
        template
        .replace("{{subject}}", html.escape(subject))
        .replace("{{generated_at}}", html.escape(generated_at))
        .replace("{{count}}", str(len(runs)))
        .replace("{{topic_sections}}", topic_sections)
        .replace("{{failure_section}}", _render_failure_section(failures))
    )
