# YouTube API Strategy

## Core Constraints

Use YouTube Data API v3 for candidate discovery and metadata hydration. Do not treat `search.list` results as final truth.

`search.list` cannot directly search arbitrary video `snippet.tags[]`. It can recall candidates by `q`, `topicId`, `videoCategoryId`, publish time, region, and language. Fetch actual video tags through `videos.list(part=snippet)`.

Always call `search.list` with:

```text
type=video
```

Without `type=video`, YouTube may return videos, channels, and playlists.

## Discovery Mode

Use this for first-pass topic discovery.

```text
user topic / keywords / target tags
  -> build one or more q queries
search.list(type=video, q=..., publishedAfter=..., regionCode=..., relevanceLanguage=...)
  -> collect video IDs
videos.list(part=snippet,contentDetails,statistics,topicDetails)
  -> hydrate tags, duration, stats, category, topic metadata
local filter + rank
  -> structured JSON results
```

## Channel Watch Mode

Use this for repeated monitoring of known channels.

```text
channels.list(part=contentDetails)
  -> read contentDetails.relatedPlaylists.uploads
playlistItems.list(playlistId=uploads)
  -> collect latest uploaded video IDs
videos.list(part=snippet,contentDetails,statistics,topicDetails)
  -> hydrate metadata
local filter + rank
  -> structured JSON results
```

## Query Guidance

`q` supports simple Boolean-style construction:

```text
keywordA|keywordB
keywordA -excludedTerm
keywordA|keywordB -excludedTerm
```

Encode `|` as `%7C` in request URLs. Treat `q` as recall, not classification; local filtering decides final relevance.

Use `topicId` only for broad curated YouTube categories such as music, gaming, sports, entertainment, lifestyle, society, business, politics, and technology. For topics such as Japanese central-bank policy, AWS operations jobs, AI browser automation, or Chrome Web Store compliance, prefer `q + target_tags + include_keywords + local classifier`.

## Quota Guidance

Estimate quota before running. `search.list` is expensive compared with `videos.list`; reuse search results when possible. Batch video hydration up to API limits rather than calling `videos.list` once per video. For recurring monitoring, prefer channel upload polling plus cache checks over repeated broad searches.

Recommended result metadata should include:

```json
"quota_usage_estimate": {
  "search_list_calls": 1,
  "videos_list_calls": 1,
  "playlist_items_list_calls": 0
}
```