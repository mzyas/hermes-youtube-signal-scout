---
name: hermes-youtube-signal-scout
description: Discover, hydrate, filter, rank, and monitor YouTube video signals for a topic, keyword/tag set, channel pool, or time window using YouTube Data API v3. Use for topic discovery, recurring channel monitoring, candidate lists for Hermes analysis, trend reports, archives, and downstream retrieval.
---

# Hermes YouTube Signal Scout

Use the bundled runtime for deterministic YouTube discovery. Do not treat raw
`search.list` results as final records: hydrate candidates, apply local filters,
and rank them before returning results.

## Run

1. Build a YAML or JSON config from the user request.
2. Select `discovery`, `channel_watch`, or `hybrid`.
3. Estimate the likely quota cost and keep broad search pages low.
4. Run:

```powershell
python -m tools.runner --config examples/ai_agents.yaml
```

Live calls require `YOUTUBE_API_KEY`. The stable Python interface is:

```python
from tools.runner import run

result = run(config)
```

The runtime resolves channels, searches candidates, uses the local cache,
hydrates video metadata, filters and ranks results, and returns both structured
data and a canonical Markdown report in `report_markdown`. It optionally writes
matching Markdown and JSON files when `output_dir` is configured.

## Final Response

After a successful run, use one canonical presentation:

- Default: output `result["report_markdown"]` verbatim.
- When the user explicitly asks for JSON, output the complete
  `result["report_json"]` object as a JSON code block.
- Every JSON video must retain `rank`, `topic_score`, `title`, `url`,
  `channel_title`, `published_at`, `duration_seconds`, and `view_count`.
- Do not summarize, rewrite, translate, reorder, or omit video fields.
- Do not add an introduction, conclusion, emoji, numbered cards, recommendations,
  caveats, or follow-up questions.
- Do not replace the Markdown table with a custom list format.
- Use the full runtime result only for downstream processing or debugging.

## Operating Rules

- Use `search.list(type=video)` only for candidate recall.
- Fetch tags, duration, statistics, and topic metadata with `videos.list`.
- Keep `exclude_keywords` in local filtering; long negative API queries reduce recall.
- Prefer `channel_watch` for recurring known-channel monitoring.
- Report API errors clearly; do not silently return partial results.
- Preserve the runtime's structured JSON for downstream processing.
- Present `report_markdown` verbatim by default, or complete `report_json` when
  JSON is explicitly requested.

## References

- `references/input-output-schema.md`: configuration, CLI, and output contract.
- `references/youtube-api-strategy.md`: API modes, quota, retries, and cache strategy.
- `references/filtering-scoring.md`: hard filters, score components, and quality flags.

## Validation

```powershell
python -m unittest discover -s tests -p 'test_*.py'
python C:\Users\mzyas\.codex\skills\.system\skill-creator\scripts\quick_validate.py .
```
