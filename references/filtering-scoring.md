# Filtering and Scoring

## Hard Filters

Candidates are rejected for missing IDs/snippets, blocklisted channels, invalid
or out-of-window dates, future publication dates, low views, excessive duration,
disabled Shorts, excluded keywords, suspected ads/promotions, and entertainment
or low-information content.

Shorts detection uses duration plus `#shorts`. Configure the duration boundary
with `shorts_max_duration_seconds`.

Advertisement and entertainment rejection are enabled by default through
`reject_possible_ads` and `reject_entertainment`.

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

For a publication window of seven days or less, every video that passes the
time-window hard filter receives the full raw freshness score of `1.0`.

For a longer window, including a 30-day search:

- videos from the most recent seven days receive `1.0`;
- older videos decay linearly;
- a video at the start of the requested window retains `0.50`.

The default configuration creates a rolling seven-day `published_after`. If
that default is disabled entirely, freshness falls back to linear position
within a rolling 30-day window.

`topic_score` is the sum of components, clamped to `[0, 1]`. Accepted videos are
sorted by score and then limited by `max_results`.
