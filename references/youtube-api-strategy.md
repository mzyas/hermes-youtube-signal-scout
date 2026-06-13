# YouTube API Strategy

## Modes

- `discovery`: call `search.list(type=video)`, then batch hydrate IDs.
- `channel_watch`: resolve each channel's uploads playlist, fetch recent items,
  then hydrate IDs.
- `hybrid`: combine both sources and deduplicate IDs before hydration.

`max_results` limits final ranked output. Candidate recall is controlled by
`max_search_pages`, `candidates_per_page`, and `channel_max_results`.

The default target is 10 accepted videos at a fixed `topic_score_threshold` of
`0.45`. The runtime first searches `US`, `JP`, `HK`, and `GB`. If fewer than 10
videos pass, it adds `KR`, `TW`, `DE`, `FR`, and `CA`. If the target is still
unmet, it follows available regional page tokens for additional pages, hydrates
only new IDs, and re-ranks the combined pool. It never lowers the threshold
automatically. `adaptive_max_search_pages` controls the extra page rounds.

YouTube accepts one `regionCode` per search request, not a geographic zone.
The runtime expands `east_asia`, `europe`, and `north_america` into representative
country codes, searches each scope, then deduplicates video IDs. Language is
unrestricted unless `relevance_language` is explicitly configured.

## Quota

Current unit estimates:

- `search.list`: 100 units per page.
- `videos.list`: 1 unit per batch of up to 50 IDs.
- `channels.list`: 1 unit per channel resolution.
- `playlistItems.list`: 1 unit per channel page.

The result reports calls actually made by the runtime. Cache hits therefore
reduce `videos.list` calls and the quota estimate.

## Cache

Hydrated videos are cached in SQLite. The default path is under the operating
system's user cache directory. A cache failure does not abort the run; the
runtime adds a warning and continues without cache.

## Reliability

The client retries network failures, HTTP 5xx, and rate limits with exponential
backoff. Authentication failures and quota exhaustion are classified separately
and are not retried as generic transient failures. Malformed JSON responses are
reported as response errors.
