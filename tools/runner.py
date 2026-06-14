"""End-to-end Python API and CLI for YouTube signal scouting."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from .cache_store import connect, get_cached_video, init_db, save_video
from .channel_resolver import parse_channel_reference, resolve_channel
from .channel_watch import fetch_latest_uploads
from .config import apply_defaults, load_config
from .errors import ConfigurationError, SignalScoutError
from .filter_ranker import filter_and_rank
from .md_writer import build_json_report, render_markdown_report, write_markdown_report
from .quota_guard import summarize_calls
from .search_discovery import resolve_region_tiers, search_videos
from .video_hydrator import hydrate_videos
from .youtube_client import YouTubeClient


class _CountingClient:
    def __init__(self, client):
        self.client = client
        self.calls: Counter[str] = Counter()

    def get(self, endpoint: str, params: dict) -> dict:
        self.calls[endpoint] += 1
        return self.client.get(endpoint, params)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _output_channel_key(video: dict) -> str:
    channel_id = str(video.get("channel_id") or "").strip()
    if channel_id:
        return f"id:{channel_id}"
    channel_title = " ".join(str(video.get("channel_title") or "").split()).casefold()
    if channel_title:
        return f"title:{channel_title}"
    return f"video:{video.get('video_id')}"


def _channel_references(config: dict) -> list[str]:
    references = [
        *(config.get("channel_ids") or []),
        *(config.get("channel_urls") or []),
    ]
    return _dedupe([parse_channel_reference(value) for value in references])


def _discover_channels(client, config: dict) -> tuple[list[str], list[dict]]:
    video_ids: list[str] = []
    channels: list[dict] = []
    for reference in _channel_references(config):
        channel = resolve_channel(client, reference)
        playlist_id = channel.get("uploads_playlist_id")
        if not playlist_id:
            raise ConfigurationError(f"channel has no uploads playlist: {reference}")
        channels.append({
            "channel_id": channel.get("channel_id"),
            "channel_title": channel.get("channel_title"),
            "reference": reference,
        })
        video_ids.extend(
            fetch_latest_uploads(
                client,
                playlist_id,
                max_results=int(config.get("channel_max_results") or 20),
            )
        )
    return _dedupe(video_ids), channels


def _hydrate_with_cache(
    client,
    video_ids: list[str],
    config: dict,
    warnings: list[str],
) -> tuple[list[dict], int, int]:
    cached: dict[str, dict] = {}
    missing = list(video_ids)
    connection = None
    if config.get("cache_enabled", True):
        try:
            cache_path = Path(str(config["cache_path"])).expanduser()
            init_db(cache_path)
            connection = connect(cache_path)
            ttl_value = config.get("video_cache_ttl_hours")
            ttl = 24 if ttl_value is None else int(ttl_value)
            missing = []
            for video_id in video_ids:
                video = get_cached_video(connection, video_id, ttl)
                if video:
                    cached[video_id] = video
                else:
                    missing.append(video_id)
        except (OSError, sqlite3.Error, ValueError) as exc:
            warnings.append(f"Cache disabled for this run: {exc}")
            if connection:
                connection.close()
            connection = None
            missing = list(video_ids)
    fresh = hydrate_videos(client, missing, int(config.get("hydration_batch_size") or 50))
    fresh_ids = {video.get("video_id") for video in fresh}
    omitted_ids = [video_id for video_id in missing if video_id not in fresh_ids]
    if omitted_ids:
        warnings.append(
            f"YouTube API omitted {len(omitted_ids)} requested video(s): {', '.join(omitted_ids[:5])}"
        )
    if connection:
        try:
            for video in fresh:
                save_video(connection, video)
        except sqlite3.Error as exc:
            warnings.append(f"Could not update cache: {exc}")
        finally:
            connection.close()
    by_id = {**cached, **{video["video_id"]: video for video in fresh}}
    return [by_id[video_id] for video_id in video_ids if video_id in by_id], len(cached), len(fresh)


def run(config: dict, client=None) -> dict:
    """Execute discovery, channel watch, or hybrid mode and return one result object."""
    config = apply_defaults(config)
    raw_client = client or YouTubeClient(
        retry_attempts=config["retry_attempts"],
        retry_backoff_seconds=config["retry_backoff_seconds"],
        timeout_seconds=config.get("timeout_seconds", 30),
    )
    counted = _CountingClient(raw_client)
    warnings: list[str] = []
    candidate_ids: list[str] = []
    query_plan = {
        "search_queries": [],
        "published_after": config.get("published_after"),
        "published_before": config.get("published_before"),
        "region_code": config.get("region_code"),
        "relevance_language": config.get("relevance_language"),
        "order": config.get("order", "date"),
        "channels": [],
    }
    mode = config["mode"]
    discovery = None
    region_tiers = resolve_region_tiers(config)
    searched_tiers = 0
    searched_region_codes: list[str] = []
    search_queries: list[str] = []
    region_queries: list[dict] = []
    if mode in {"discovery", "hybrid"}:
        discovery = search_videos(
            counted,
            config,
            region_codes_override=region_tiers[0],
        )
        searched_tiers = 1
        candidate_ids.extend(discovery["video_ids"])
        query_plan.update(discovery["query_plan"])
        searched_region_codes.extend(discovery["query_plan"].get("region_codes", []))
        search_queries.extend(discovery["query_plan"].get("search_queries", []))
        region_queries.extend(discovery["query_plan"].get("region_queries", []))
        query_plan["search_page_count"] = discovery["page_count"]
    if mode in {"channel_watch", "hybrid"}:
        channel_ids, channels = _discover_channels(counted, config)
        candidate_ids.extend(channel_ids)
        query_plan["channels"] = channels
    raw_candidate_count = len(candidate_ids)
    candidate_ids = _dedupe(candidate_ids)
    videos, cache_hits, hydrated = _hydrate_with_cache(
        counted, candidate_ids, config, warnings
    )
    runtime_config = dict(config)
    runtime_config["search_queries"] = query_plan["search_queries"]
    runtime_config["quota_usage_estimate"] = summarize_calls(counted.calls)
    runtime_config["output_dir"] = None
    result = filter_and_rank(videos, runtime_config)
    target_results = int(config.get("target_results") or 10)
    next_page_tokens = (discovery or {}).get("next_page_tokens") or {}
    total_search_pages = (discovery or {}).get("page_count") or 0
    while (
        mode in {"discovery", "hybrid"}
        and len(result["videos"]) < target_results
        and searched_tiers < len(region_tiers)
    ):
        extra = search_videos(
            counted,
            config,
            region_codes_override=region_tiers[searched_tiers],
        )
        searched_tiers += 1
        total_search_pages += extra["page_count"]
        searched_region_codes.extend(extra["query_plan"].get("region_codes", []))
        search_queries.extend(extra["query_plan"].get("search_queries", []))
        region_queries.extend(extra["query_plan"].get("region_queries", []))
        next_page_tokens.update(extra["next_page_tokens"])
        raw_candidate_count += len(extra["video_ids"])
        extra_ids = [
            video_id for video_id in extra["video_ids"] if video_id not in candidate_ids
        ]
        if not extra_ids:
            continue
        candidate_ids.extend(extra_ids)
        extra_videos, extra_cache_hits, extra_hydrated = _hydrate_with_cache(
            counted, extra_ids, config, warnings
        )
        cache_hits += extra_cache_hits
        hydrated += extra_hydrated
        videos.extend(extra_videos)
        runtime_config["quota_usage_estimate"] = summarize_calls(counted.calls)
        result = filter_and_rank(videos, runtime_config)
    adaptive_pages_used = 0
    max_adaptive_pages = int(config.get("adaptive_max_search_pages") or 1)
    while (
        mode in {"discovery", "hybrid"}
        and len(result["videos"]) < target_results
        and adaptive_pages_used < max_adaptive_pages
        and next_page_tokens
    ):
        extra = search_videos(
            counted,
            config,
            page_tokens=next_page_tokens,
            max_pages_override=1,
        )
        adaptive_pages_used += 1
        total_search_pages += extra["page_count"]
        next_page_tokens = extra["next_page_tokens"]
        search_queries.extend(extra["query_plan"].get("search_queries", []))
        region_queries.extend(extra["query_plan"].get("region_queries", []))
        extra_ids = [
            video_id for video_id in extra["video_ids"] if video_id not in candidate_ids
        ]
        raw_candidate_count += len(extra["video_ids"])
        if not extra_ids:
            continue
        candidate_ids.extend(extra_ids)
        extra_videos, extra_cache_hits, extra_hydrated = _hydrate_with_cache(
            counted, extra_ids, config, warnings
        )
        cache_hits += extra_cache_hits
        hydrated += extra_hydrated
        videos.extend(extra_videos)
        runtime_config["quota_usage_estimate"] = summarize_calls(counted.calls)
        result = filter_and_rank(videos, runtime_config)
    result["query_plan"] = query_plan
    result["query_plan"]["search_queries"] = _dedupe(search_queries)
    result["query_plan"]["region_queries"] = list({
        (
            item.get("region_code"),
            item.get("language"),
            item.get("query"),
        ): item
        for item in region_queries
    }.values())
    result["query_plan"]["region_codes"] = _dedupe(searched_region_codes)
    result["query_plan"]["region_priority_tiers"] = region_tiers
    result["query_plan"]["region_tiers_searched"] = searched_tiers
    result["query_plan"]["search_page_count"] = total_search_pages
    result["query_plan"]["adaptive_search_pages"] = adaptive_pages_used
    result["quota_usage_estimate"] = summarize_calls(counted.calls)
    channel_duplicate_count = sum(
        item.get("reason_code") == "channel_limit_exceeded"
        for item in result["rejected"]
    )
    result["run_stats"] = {
        "candidate_count": raw_candidate_count,
        "deduplicated_count": len(candidate_ids),
        "cache_hits": cache_hits,
        "hydrated_count": hydrated,
        "accepted_count": len(result["videos"]),
        "rejected_count": len(result["rejected"]),
        "target_results": target_results,
        "target_met": len(result["videos"]) >= target_results,
        "channel_duplicate_count": channel_duplicate_count,
        "unique_channel_count": len({
            _output_channel_key(video) for video in result["videos"]
        }),
        "api_calls": dict(counted.calls),
    }
    if len(result["videos"]) < target_results:
        warnings.append(
            f"Only {len(result['videos'])} video(s) passed the fixed score threshold; target was {target_results}."
        )
    result["warnings"] = warnings
    if config.get("output_dir"):
        write_markdown_report(result, str(config["output_dir"]), config)
    else:
        result["report_json"] = build_json_report(result, config)
        result["report_markdown"] = render_markdown_report(result, config)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discover and rank YouTube video signals")
    parser.add_argument("--config", required=True, help="Path to a YAML or JSON config file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run(load_config(args.config))
    except (SignalScoutError, OSError, ValueError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
