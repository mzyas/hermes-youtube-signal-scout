---
name: hermes-youtube-signal-scout
description: Discover, hydrate, filter, rank, and monitor YouTube video signals for a topic, keyword/tag set, channel pool, or time window using YouTube Data API v3. Use for topic discovery, recurring channel monitoring, candidate lists for Hermes analysis, trend reports, archives, and downstream retrieval.
---

# Hermes YouTube Signal Scout

Use the bundled runtime for deterministic YouTube discovery. Do not treat raw
`search.list` results as final records: hydrate candidates, apply local filters,
and rank them before returning results.

## Run

1. Build a YAML or JSON config from the user request. Populate
   `localized_queries` with faithful translations for the target regions while
   preserving the user's original meaning.
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

For externally scheduled multi-topic runs, use:

```powershell
python -m tools.weekly_runner --config examples/weekly.yaml
```

The stable weekly Python interface is
`tools.weekly_runner.run_weekly(config, client=None)`.

## Weekly Automation

The external scheduler invokes the weekly interface, for example every Monday
morning. The Skill performs search and report assembly but does not schedule
itself or send email directly. It returns `email_handoff`; the agent must convert
`markdown_body` to semantic HTML, preserve every video's information, and send
it through the available email tool to `recipients`.

Only perform HTML rendering and email delivery after an explicit
`run_weekly()`/weekly CLI invocation. A normal `run()` result must never trigger
HTML rendering or email delivery.

See `references/weekly-automation.md` for the handoff contract.

## Clarification Gate

Before running, ask only when clarification materially improves precision:

- If the topic is broad, ask which specific economic, market, industry, policy,
  or company angle matters most.
- If the intended time horizon is unclear and could change the result set, ask
  whether to search the latest 7 days or 30 days.

Ask both questions together when both are needed. Do not ask about regions,
language, channels, Shorts, advertisements, or entertainment preferences.
Reuse the user's exact topic wording in every clarification. Never replace it
with a broader, narrower, or adjacent label.

Apply these defaults without asking:

- latest 7 days;
- region tier 1: `US`, `JP`, `HK`, `GB`;
- region tier 2 if needed: `KR`, `TW`, `DE`, `FR`, `CA`;
- localized search queries for each region, without hard-filtering result language;
- exclude Shorts, advertisements, promotions, and entertainment content.

Only override regions when the user explicitly requests another geography. If
the request is already specific enough, run immediately without clarification.
See `references/intake-guidance.md` for the decision rules and question template.

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
- Rank with the documented six-dimension model; use cached Data API snapshots
  for view growth and Bayesian smoothing for engagement.
- Keep `exclude_keywords` in local filtering; long negative API queries reduce recall.
- Keep at most `max_videos_per_channel` ranked videos from one channel per
  topic result; the default is one.
- Prefer `channel_watch` for recurring known-channel monitoring.
- Report API errors clearly; do not silently return partial results.
- Preserve the runtime's structured JSON for downstream processing.
- Present `report_markdown` verbatim by default, or complete `report_json` when
  JSON is explicitly requested.

## References

- `references/input-output-schema.md`: configuration, CLI, and output contract.
- `references/youtube-api-strategy.md`: API modes, quota, retries, and cache strategy.
- `references/filtering-scoring.md`: hard filters, score components, and quality flags.
- `references/intake-guidance.md`: when and how to ask for missing search intent.
- `references/weekly-automation.md`: scheduled batch and email handoff contract.

## Validation

```powershell
python -m unittest discover -s tests -p 'test_*.py'
python C:\Users\mzyas\.codex\skills\.system\skill-creator\scripts\quick_validate.py .
```
