# Filtering And Scoring

## Hard Filters

Reject clearly unsuitable videos before scoring:

```text
- Outside the configured publish-time window
- Channel is in the blocklist
- View count is below min_views
- Duration exceeds max_duration_seconds
- include_shorts=false and the video appears to be a Short
- Title, description, or tags match exclude_keywords
- Missing videoId or required snippet fields
```

## Field Matching

Match include keywords and target tags against:

```text
title
description
tags
channel_title
topicDetails.topicCategories
```

Record matches in `matched_fields` so downstream agents can explain why a video passed.

## Topic Score

Use this MVP scoring model unless the user supplies a different one:

```text
topic_score =
  0.30 * title_keyword_score
+ 0.25 * tag_score
+ 0.20 * description_score
+ 0.10 * channel_reliability_score
+ 0.10 * freshness_score
+ 0.05 * engagement_score
```

Recommended field weights:

```text
title:       0.30
tags:        0.25
description: 0.20
channel:     0.10
freshness:   0.10
engagement:  0.05
```

A video should pass when it matches required include keywords in title, description, tags, or channel title; avoids exclude keywords; satisfies configured date, region, language, duration, view count, and channel constraints; and reaches `topic_score_threshold`.

## Shorts Detection

YouTube Data API may not directly identify Shorts. For MVP, mark a video as a Short when:

```text
duration_seconds <= 60
```

Optionally strengthen the signal when title, description, or tags contain `#shorts`.

Represent the flag as:

```json
"quality_flags": {
  "is_short": true
}
```

## Low-Quality Or Ad-Like Signals

MVP should use rules rather than complex ML. Mark `possible_ad` or `low_signal` when title or description contains terms such as:

```text
sponsored
promo
affiliate
限时优惠
免费领取
暴富
副業で月収
稼げる
案件紹介だけ
```

Use the `reason` field to explain whether these flags caused rejection or only lowered confidence.