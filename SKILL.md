---
name: hermes-youtube-signal-scout
description: Discover, hydrate, filter, and rank YouTube video signals for a user-defined topic, keyword group, tag set, channel pool, or time window using YouTube Data API v3. Use when Codex needs to find YouTube videos about a topic, monitor channels or topics, filter videos by keyword/tag/channel/language/region/date/duration/view count, build candidate video lists for Hermes-agent summarization, trend analysis, reports, archiving, or downstream retrieval.
---

# Hermes YouTube Signal Scout

## Purpose

Use this skill to plan and execute YouTube video signal discovery for Hermes workflows. Treat YouTube search as candidate recall only: always hydrate videos, apply local filters, rank by topic fit, and return structured JSON for downstream analysis.

## Workflow

1. Clarify the topic, keywords/tags, channel scope, region/language, time window, and result limit from the user request.
2. Choose a discovery mode:
   - Use `search.list(type=video)` for new topic discovery.
   - Use channel uploads polling for repeated monitoring of known channels.
   - Combine both for hybrid runs.
3. Hydrate all candidate video IDs with `videos.list(part=snippet,contentDetails,statistics,topicDetails)` before using tags, duration, statistics, or topic metadata.
4. Apply hard filters for date window, blocklisted channels, minimum views, duration, Shorts policy, missing metadata, and `exclude_keywords`.
5. Score remaining videos with local field matching and produce `topic_score`, `matched_fields`, `quality_flags`, and a short human-readable `reason`.
6. Return structured JSON; when `output_dir` is configured, also write human-readable Markdown and matching JSON report files for downstream review.

## Required API Strategy

`search.list` cannot precisely search arbitrary `snippet.tags[]`; use it only to recall candidates through `q`, `topicId`, `videoCategoryId`, time, region, and language parameters. Fetch tags with `videos.list(part=snippet)` after video IDs are known.

Always set `type=video` for `search.list`; otherwise YouTube may return channels or playlists.

Use simple Boolean query construction in `q` when useful:

```text
keywordA|keywordB -excludedTerm
```

Encode `|` as `%7C` in URLs. Prefer `q + target_tags + include_keywords + local classifier` for natural-language topics rather than relying on `topicId`.

## References

Load only the reference needed for the task:

- `references/youtube-api-strategy.md`: API constraints, discovery/channel-watch flows, quota guidance.
- `references/input-output-schema.md`: input configuration shape and output JSON examples.
- `references/filtering-scoring.md`: hard filters, field weights, `topic_score`, Shorts and low-quality/ad rules.


## MVP Runtime

The skill folder includes a Python MVP runtime:

- `tools/`: YouTube API client, discovery, hydration, channel watch, cache/quota helpers, duration parsing, text matching, local filter/rank logic, and Markdown/JSON report writing.
- `schemas/`: JSON schema contracts for input config, normalized video objects, and final results.
- `examples/`: YAML example configs for Japan BOJ, AI agent browser automation, and AWS operations topics.
- `tests/`: Offline unit tests for duration parsing, query building, text matching, filter/rank, and schema JSON parsing.

Use the offline tests before live API work:

```powershell
python -m unittest discover -s tests -p 'test_*.py'
```

Live YouTube API calls require `YOUTUBE_API_KEY` and should start with one example config and one search page.

## Output Contract

Return a JSON object containing run metadata, query plan, quota estimate, accepted videos, and rejected videos. Each accepted video should include `video_id`, `url`, `title`, `channel_id`, `channel_title`, `published_at`, `description_excerpt`, `tags`, `duration_seconds`, statistics, `matched_fields`, `topic_score`, `quality_flags`, and `reason`.

Set `output_dir` in the runtime config to write two timestamped files after filtering:

```text
{output_dir}/{topic}_{timestamp}.md
{output_dir}/{topic}_{timestamp}.json
```

The Markdown report includes the query plan, time window, quota estimate, accepted-video table, and rejected-video reasons. Table text escapes Markdown separators. The returned result includes `output_files.markdown` and `output_files.json`. Leave `output_dir` as `null` to keep the default JSON-only behavior.
