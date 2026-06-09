# Input And Output Schema

## Input Configuration

Support these user-facing inputs when planning a run:

```yaml
topic: "日本央行加息"
include_keywords: ["日銀", "BOJ", "金融政策", "利上げ"]
exclude_keywords: ["広告", "切り抜き", "占い"]
target_tags: ["日本経済", "金融政策"]
channel_ids: []
channel_urls: []
region_code: "JP"
relevance_language: "ja"
published_after: "2026-06-01T00:00:00Z"
published_before: null
order: "date"
max_results: 25
min_views: 1000
max_duration_seconds: 3600
include_shorts: false
topic_score_threshold: 0.55
mode: "hybrid"
```

Common `mode` values:

```text
discovery
channel_watch
hybrid
```

## Result Object

Return a single JSON object with run metadata, query plan, quota estimate, accepted videos, and rejected videos.

```json
{
  "run_id": "ytss_20260609_001",
  "skill": "hermes-youtube-signal-scout",
  "topic": "日本央行加息",
  "mode": "hybrid",
  "created_at": "2026-06-09T12:00:00Z",
  "query_plan": {
    "search_queries": ["日本央行|日銀|BOJ -娱乐"],
    "published_after": "2026-06-01T00:00:00Z",
    "region_code": "JP",
    "relevance_language": "ja",
    "order": "date"
  },
  "quota_usage_estimate": {
    "search_list_calls": 1,
    "videos_list_calls": 1,
    "playlist_items_list_calls": 0
  },
  "videos": [],
  "rejected": []
}
```

## Video Object

Each accepted video should use this shape:

```json
{
  "video_id": "VIDEO_ID",
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "title": "Example title",
  "channel_id": "CHANNEL_ID",
  "channel_title": "Example Channel",
  "published_at": "2026-06-08T10:00:00Z",
  "description_excerpt": "First 300 characters...",
  "tags": ["日本経済", "日銀", "金融政策"],
  "category_id": "25",
  "duration_seconds": 753,
  "statistics": {
    "view_count": 123456,
    "like_count": 4567,
    "comment_count": 321
  },
  "matched_fields": {
    "title": ["日銀", "利上げ"],
    "description": ["金融政策"],
    "tags": ["日本経済", "日銀"],
    "channel_title": []
  },
  "topic_score": 0.87,
  "quality_flags": {
    "is_short": false,
    "possible_ad": false,
    "low_signal": false
  },
  "reason": "标题、描述和 tags 同时命中日本央行/金融政策主题，发布时间在窗口内，互动数据正常。"
}
```

Rejected videos should include the `video_id` when available, `title`, and a concise `reason`, such as a matched exclude keyword or failing the time window.