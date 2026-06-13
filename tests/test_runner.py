import tempfile
import unittest
from pathlib import Path

from tools.runner import run


def video_resource(video_id: str, title: str = "signal update") -> dict:
    return {
        "id": video_id,
        "snippet": {
            "title": title,
            "channelId": "UC1234567890123456789012",
            "channelTitle": "Signal Desk",
            "publishedAt": "2026-06-10T00:00:00Z",
            "description": "signal analysis",
            "tags": ["signal"],
        },
        "contentDetails": {"duration": "PT10M"},
        "statistics": {"viewCount": "1000", "likeCount": "20", "commentCount": "3"},
    }


class FakeYouTubeClient:
    def __init__(self, search_pages=None, playlist_ids=None):
        self.search_pages = search_pages or []
        self.playlist_ids = playlist_ids or []
        self.calls = []

    def get(self, endpoint, params):
        self.calls.append((endpoint, dict(params)))
        if endpoint == "search":
            page = 1 if params.get("pageToken") else 0
            ids = self.search_pages[page] if page < len(self.search_pages) else []
            return {
                "items": [{"id": {"videoId": value}} for value in ids],
                "nextPageToken": "page-2" if page == 0 and len(self.search_pages) > 1 else None,
            }
        if endpoint == "channels":
            return {
                "items": [{
                    "id": "UC1234567890123456789012",
                    "snippet": {"title": "Signal Channel"},
                    "contentDetails": {"relatedPlaylists": {"uploads": "UUuploads"}},
                }]
            }
        if endpoint == "playlistItems":
            return {
                "items": [
                    {"contentDetails": {"videoId": value}}
                    for value in self.playlist_ids
                ]
            }
        if endpoint == "videos":
            return {
                "items": [
                    video_resource(value)
                    for value in str(params["id"]).split(",")
                ]
            }
        raise AssertionError(endpoint)


class RegionalFakeYouTubeClient(FakeYouTubeClient):
    def __init__(self, regional_ids):
        super().__init__()
        self.regional_ids = regional_ids

    def get(self, endpoint, params):
        if endpoint == "search":
            self.calls.append((endpoint, dict(params)))
            ids = self.regional_ids.get(params.get("regionCode"), [])
            return {"items": [{"id": {"videoId": value}} for value in ids]}
        return super().get(endpoint, params)


def base_config(**overrides):
    config = {
        "topic": "signal",
        "include_keywords": ["signal"],
        "topic_score_threshold": 0,
        "include_shorts": False,
        "cache_enabled": False,
        "max_results": 50,
        "zones": [],
        "region_code": "JP",
        "region_priority_tiers": [],
    }
    config.update(overrides)
    return config


class RunnerTests(unittest.TestCase):
    def test_region_priority_stops_after_first_tier_when_target_is_met(self):
        client = RegionalFakeYouTubeClient({
            "US": [f"us-{index}" for index in range(10)],
            "JP": [],
            "HK": [],
            "GB": [],
            "KR": ["should-not-search"],
        })
        result = run(
            base_config(
                region_code=None,
                region_priority_tiers=[
                    ["US", "JP", "HK", "GB"],
                    ["KR", "TW", "DE", "FR", "CA"],
                ],
                target_results=10,
            ),
            client=client,
        )

        searched_regions = [
            params["regionCode"]
            for endpoint, params in client.calls
            if endpoint == "search"
        ]
        self.assertEqual(searched_regions, ["US", "JP", "HK", "GB"])
        self.assertEqual(result["query_plan"]["region_tiers_searched"], 1)
        self.assertEqual(result["query_plan"]["region_codes"], searched_regions)
        self.assertTrue(result["run_stats"]["target_met"])

    def test_region_priority_expands_to_second_tier_when_target_is_short(self):
        client = RegionalFakeYouTubeClient({
            "US": ["us-1", "us-2"],
            "JP": ["jp-1"],
            "HK": [],
            "GB": [],
            "KR": ["kr-1", "kr-2"],
            "TW": ["tw-1"],
            "DE": ["de-1"],
            "FR": ["fr-1"],
            "CA": ["ca-1", "ca-2"],
        })
        result = run(
            base_config(
                region_code=None,
                region_priority_tiers=[
                    ["US", "JP", "HK", "GB"],
                    ["KR", "TW", "DE", "FR", "CA"],
                ],
                target_results=10,
            ),
            client=client,
        )

        searched_regions = [
            params["regionCode"]
            for endpoint, params in client.calls
            if endpoint == "search"
        ]
        self.assertEqual(
            searched_regions,
            ["US", "JP", "HK", "GB", "KR", "TW", "DE", "FR", "CA"],
        )
        self.assertEqual(result["query_plan"]["region_tiers_searched"], 2)
        self.assertEqual(result["query_plan"]["region_codes"], searched_regions)
        self.assertTrue(result["run_stats"]["target_met"])

    def test_discovery_pages_and_hydration_batches_use_actual_counts(self):
        ids = [f"v{i}" for i in range(75)]
        client = FakeYouTubeClient([ids[:50], ids[50:]])
        result = run(base_config(max_search_pages=2), client=client)

        self.assertEqual(result["run_stats"]["candidate_count"], 75)
        self.assertEqual(result["run_stats"]["hydrated_count"], 75)
        self.assertEqual(result["quota_usage_estimate"]["search_list_calls"], 2)
        self.assertEqual(result["quota_usage_estimate"]["videos_list_calls"], 2)
        self.assertEqual(result["quota_usage_estimate"]["estimated_quota_cost"], 202)
        self.assertIn("| # | 得分 | 标题 | 频道 | 发布日期 | 时长 | 播放量 |", result["report_markdown"])
        self.assertEqual(len(result["report_json"]["videos"]), 50)
        self.assertNotIn("email_handoff", result)
        video_calls = [params for endpoint, params in client.calls if endpoint == "videos"]
        self.assertEqual([len(call["id"].split(",")) for call in video_calls], [50, 25])

    def test_channel_watch_resolves_handle_and_fetches_uploads(self):
        client = FakeYouTubeClient(playlist_ids=["channel-video"])
        result = run(
            base_config(mode="channel_watch", channel_urls=["https://www.youtube.com/@signal"]),
            client=client,
        )

        self.assertEqual(result["videos"][0]["video_id"], "channel-video")
        self.assertEqual(result["query_plan"]["channels"][0]["reference"], "@signal")
        self.assertEqual(result["quota_usage_estimate"]["channels_list_calls"], 1)
        self.assertEqual(result["quota_usage_estimate"]["playlist_items_list_calls"], 1)

    def test_hybrid_deduplicates_before_hydration(self):
        client = FakeYouTubeClient([["same", "search-only"]], ["same", "channel-only"])
        result = run(
            base_config(
                mode="hybrid",
                channel_ids=["UC1234567890123456789012"],
            ),
            client=client,
        )

        self.assertEqual(result["run_stats"]["candidate_count"], 4)
        self.assertEqual(result["run_stats"]["deduplicated_count"], 3)
        self.assertEqual(result["run_stats"]["hydrated_count"], 3)
        hydrated_ids = [
            value
            for endpoint, params in client.calls
            if endpoint == "videos"
            for value in params["id"].split(",")
        ]
        self.assertEqual(hydrated_ids, ["same", "search-only", "channel-only"])

    def test_cache_hit_avoids_second_hydration_call(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = str(Path(temp_dir) / "cache.sqlite3")
            config = base_config(cache_enabled=True, cache_path=cache_path)
            first_client = FakeYouTubeClient([["cached-video"]])
            first = run(config, client=first_client)
            second_client = FakeYouTubeClient([["cached-video"]])
            second = run(config, client=second_client)

            self.assertEqual(first["run_stats"]["cache_hits"], 0)
            self.assertEqual(second["run_stats"]["cache_hits"], 1)
            self.assertEqual(second["quota_usage_estimate"]["videos_list_calls"], 0)
            self.assertFalse(any(endpoint == "videos" for endpoint, _ in second_client.calls))

    def test_corrupt_cache_warns_and_continues(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "cache.sqlite3"
            cache_path.write_bytes(b"not sqlite")
            result = run(
                base_config(cache_enabled=True, cache_path=str(cache_path)),
                client=FakeYouTubeClient([["fresh-video"]]),
            )

            self.assertEqual(result["videos"][0]["video_id"], "fresh-video")
            self.assertTrue(any("Cache disabled" in warning for warning in result["warnings"]))

    def test_zero_cache_ttl_forces_refresh(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = str(Path(temp_dir) / "cache.sqlite3")
            first_config = base_config(cache_enabled=True, cache_path=cache_path)
            run(first_config, client=FakeYouTubeClient([["refresh-video"]]))
            second = run(
                base_config(
                    cache_enabled=True,
                    cache_path=cache_path,
                    video_cache_ttl_hours=0,
                ),
                client=FakeYouTubeClient([["refresh-video"]]),
            )
            self.assertEqual(second["run_stats"]["cache_hits"], 0)
            self.assertEqual(second["quota_usage_estimate"]["videos_list_calls"], 1)


if __name__ == "__main__":
    unittest.main()
