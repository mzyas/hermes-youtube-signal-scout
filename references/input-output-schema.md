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
relevance_language: null
max_results: 25
max_search_pages: 1
include_shorts: false
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
(`US`, `CA`). No `relevanceLanguage` is sent by default. Set legacy
`region_code`, or explicit `region_codes`, to override the zone preset.

Useful optional controls:

- `candidates_per_page`, `channel_max_results`, `hydration_batch_size`
- `cache_path`, `video_cache_ttl_hours`
- `retry_attempts`, `retry_backoff_seconds`, `timeout_seconds`
- `shorts_max_duration_seconds`, `reject_possible_ads`
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

## Output

The result preserves the 0.1 top-level fields and adds:

- `version`: runtime skill version.
- `run_stats`: candidate, cache, hydration, acceptance, and API call counts.
- `warnings`: non-fatal cache or output warnings.
- `score_components`: weighted score contribution for each accepted video.
- `report_markdown`: canonical user-facing report; agents must output it verbatim.
- `report_json`: canonical JSON containing the same summary, video columns,
  rejected items, run statistics, and warnings as the Markdown report.
- `output_files`: Markdown and JSON paths when `output_dir` is configured.

Rejected records always contain `video_id`, `title`, and `reason`. The complete
machine-readable contract is in `schemas/result.schema.json`.
