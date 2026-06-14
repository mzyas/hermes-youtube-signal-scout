# Filtering and Scoring

## Hard Filters

Candidates are rejected for missing IDs/snippets, blocklisted channels, invalid
or out-of-window dates, future publication dates, low views, excessive duration,
disabled Shorts, excluded keywords, suspected ads/promotions, and entertainment
or low-information content. Exam-preparation and training channels are also
rejected by default, including Academy/coaching brands, civil-service exam
preparation, test-prep schools, and equivalent multilingual terms.

Shorts detection uses duration plus `#shorts`. Configure the duration boundary
with `shorts_max_duration_seconds`.

Advertisement and entertainment rejection are enabled by default through
`reject_possible_ads` and `reject_entertainment`.
Exam-training rejection is controlled by `reject_exam_training`.

## Topic Match

Matching is case-insensitive and checks title, description, tags, channel title,
and topic categories. If both `include_keywords` and `target_tags` are empty,
the topic is used as the include keyword. A target-tags-only configuration is
valid and matches video tags.

## Score

Each accepted video exposes six weighted `score_components`:

```text
topic_relevance           0.45
freshness                 0.15
view_velocity             0.15
smoothed_engagement       0.10
channel_credibility       0.10
information_completeness  0.05
```

Topic relevance combines title, tags, description, topic categories, and
channel-title matches. Their internal weights are `0.40`, `0.25`, `0.20`,
`0.10`, and `0.05`, then the combined value is multiplied by `0.45`.

For a publication window of seven days or less, every video that passes the
time-window hard filter receives the full raw freshness score of `1.0`.

For a longer window, including a 30-day search:

- videos from the most recent seven days receive `1.0`;
- older videos decay linearly;
- a video at the start of the requested window retains `0.50`.

The default configuration creates a rolling seven-day `published_after`. If
that default is disabled entirely, freshness falls back to linear position
within a rolling 30-day window.

## Growth and Engagement

View velocity uses the latest two locally cached Data API snapshots when
available:

```text
(current views - previous views) / elapsed hours
```

On first discovery it falls back to `current views / hours since publication`.
Velocity is converted to a percentile among the current candidate set so large
established channels do not receive an automatic absolute-view advantage. The
cache retains the latest 20 snapshots per video.

Engagement uses Bayesian smoothing:

```text
(likes + comments * 3 + candidate_baseline * prior_views)
/ (views + prior_views)
```

`engagement_prior_views` defaults to `1000`, preventing very small samples from
receiving extreme scores.

## Channel and Information Quality

`trusted_channel_ids` receive full channel credibility. Optional
`channel_quality_scores` assigns reviewed scores from `0` to `1`. Other
channels receive a conservative Data-API-only proxy based on channel metadata
presence, channel-title topic alignment, absence of low-quality flags, and
statistics completeness. This score does not claim factual accuracy.

Information completeness measures title, description depth, tags, category,
duration, and statistics availability.

`topic_score` is the sum of components, clamped to `[0, 1]`. Accepted videos are
sorted by score, deduplicated by channel, and then limited by `max_results`.

By default, `max_videos_per_channel: 1` keeps only the highest-ranked video from
each channel in one topic result. Ties are resolved by newer publication time,
then higher view count, then original candidate order. Channel identity uses
`channel_id`, falls back to a normalized `channel_title`, and treats videos
without either field independently.

Videos suppressed by this limit are added to `rejected` with
`reason_code: channel_limit_exceeded`. The runner uses the channel-deduplicated
accepted count when deciding whether to expand regions or fetch another page.
