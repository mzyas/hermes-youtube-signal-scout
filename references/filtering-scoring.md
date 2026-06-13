# Filtering and Scoring

## Hard Filters

Candidates are rejected for missing IDs/snippets, blocklisted channels, invalid
or out-of-window dates, future publication dates, low views, excessive duration,
disabled Shorts, excluded keywords, and optionally suspected ads.

Shorts detection uses duration plus `#shorts`. Configure the duration boundary
with `shorts_max_duration_seconds`.

## Topic Match

Matching is case-insensitive and checks title, description, tags, channel title,
and topic categories. If both `include_keywords` and `target_tags` are empty,
the topic is used as the include keyword. A target-tags-only configuration is
valid and matches video tags.

## Score

Each accepted video exposes weighted `score_components`:

```text
title       0.30
tags        0.25
description 0.20
channel     0.10
freshness   0.10
engagement  0.05
```

Channel points require a channel-title keyword match or a channel ID listed in
`trusted_channel_ids`; there is no unconditional baseline. Missing statistics
produce zero engagement rather than an error.

`topic_score` is the sum of components, clamped to `[0, 1]`. Accepted videos are
sorted by score and then limited by `max_results`.
