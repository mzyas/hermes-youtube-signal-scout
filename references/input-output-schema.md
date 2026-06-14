# Input and Output Contract

## Input

YAML and JSON are supported. Existing 0.1 fields remain valid.

```yaml
topic: "AI agent browser automation"
mode: hybrid
include_keywords: ["AI agent", "browser automation"]
exclude_keywords: ["sponsored"]
target_tags: ["agentic AI"]
channel_ids: ["UCxxxxxxxxxxxxxxxxxxxxxx"]
channel_urls: ["https://www.youtube.com/@example"]
published_after: "2026-06-01T00:00:00Z"
lookback_days: 7
zones: [east_asia, europe, north_america]
region_code: null
region_codes: []
region_priority_tiers:
  - [US, JP, HK, GB]
  - [KR, TW, DE, FR, CA]
relevance_language: null
localized_queries:
  en: ["current affairs", "politics"]
  ja: ["時事問題", "政治"]
  zh-Hant: ["時政"]
  ko: ["시사", "정치"]
  de: ["Zeitgeschehen", "Politik"]
  fr: ["actualité politique", "politique"]
max_results: 10
target_results: 10
max_videos_per_channel: 1
engagement_prior_views: 1000
channel_quality_scores:
  UCxxxxxxxxxxxxxxxxxxxxxx: 0.9
max_search_pages: 1
adaptive_max_search_pages: 1
include_shorts: false
reject_possible_ads: true
reject_entertainment: true
reject_exam_training: true
output_dir: null
cache_enabled: true
```

Dates must be RFC 3339 values with `Z` or an explicit UTC offset. Channel URLs
must use `/channel/UC...` or `/@handle`.

When `published_after` is omitted, `lookback_days: 7` generates a rolling
seven-day UTC start time. Set an explicit `published_after` to override it, or
set `lookback_days: null` to disable the default time window.

The default zone preset searches representative markets in East Asia
(`JP`, `KR`, `TW`, `HK`), Europe (`GB`, `DE`, `FR`), and North America
(`US`, `CA`). Each request uses that region's search language: English for
`US`/`GB`/`CA`, Japanese for `JP`, Traditional Chinese for `HK`/`TW`, Korean
for `KR`, German for `DE`, and French for `FR`. This is a recall hint, not a
hard result-language filter.

The agent should populate `localized_queries` with faithful translations of
the user's original topic. Translations must not broaden, narrow, or relabel
the intent. Missing languages fall back to the original `include_keywords`.
Set legacy `region_code`, or explicit `region_codes`, to override the zone
preset. An explicit `search_query` or `relevance_language` overrides regional
localization.

Default search priority:

1. `US`, `JP`, `HK`, `GB`
2. `KR`, `TW`, `DE`, `FR`, `CA`

The second tier runs only when the first tier produces fewer than
`target_results`.

Useful optional controls:

- `candidates_per_page`, `channel_max_results`, `hydration_batch_size`
- `target_results`, `adaptive_max_search_pages`
- `cache_path`, `video_cache_ttl_hours`
- `retry_attempts`, `retry_backoff_seconds`, `timeout_seconds`
- `shorts_max_duration_seconds`, `reject_possible_ads`, `reject_entertainment`
- `trusted_channel_ids`, `score_match_cap`

## Interfaces

```powershell
python -m tools.runner --config path/to/config.yaml
```

The CLI writes one JSON object to stdout. Configuration and API failures are
written as JSON to stderr with exit code `2`.

```python
from tools.runner import run

result = run(config)
```

Pass `client=` to inject a compatible client for tests.

For a scheduler-driven weekly batch:

```powershell
python -m tools.weekly_runner --config examples/weekly.yaml
```

The weekly config accepts shared `defaults`, a non-empty `topics` array,
descriptive `schedule` metadata, and optional email recipients. Its result
contains all per-topic runs plus `email_handoff` for agent-side HTML rendering
and delivery. See `schemas/weekly-input.schema.json`,
`schemas/weekly-result.schema.json`, and `references/weekly-automation.md`.
The normal `tools.runner.run()` result never contains an email action and must
not trigger HTML rendering or delivery.

## Output

The result preserves the 0.1 top-level fields and adds:

- `version`: runtime skill version.
- `run_stats`: candidate, cache, hydration, acceptance, and API call counts.
- `run_stats.channel_duplicate_count` and `unique_channel_count`: channel
  diversity statistics for the final topic result.
- `warnings`: non-fatal cache or output warnings.
- `score_components`: weighted score contribution for each accepted video.
- `ranking_signals`: raw six-dimension scores, smoothed engagement rate, view
  velocity, and whether velocity came from snapshots or lifetime average.
- `report_markdown`: canonical user-facing report; agents must output it verbatim.
- `report_json`: canonical JSON containing the same summary, video columns,
  rejected items, run statistics, and warnings as the Markdown report.
- `output_files`: Markdown and JSON paths when `output_dir` is configured.

Rejected records always contain `video_id`, `title`, and `reason`. The complete
machine-readable contract is in `schemas/result.schema.json`.
