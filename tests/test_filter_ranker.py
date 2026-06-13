import unittest
from datetime import datetime, timezone

from tools.filter_ranker import _freshness_score, filter_and_rank


class FilterRankerTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "topic": "日本央行加息",
            "mode": "discovery",
            "include_keywords": ["日銀", "金融政策", "利上げ"],
            "exclude_keywords": ["広告"],
            "target_tags": ["日本経済", "日銀"],
            "published_after": "2026-06-01T00:00:00Z",
            "min_views": 1000,
            "max_duration_seconds": 3600,
            "include_shorts": False,
            "topic_score_threshold": 0.25,
            "region_code": "JP",
            "relevance_language": "ja",
        }

    def test_accepts_relevant_video_and_rejects_excluded(self):
        videos = [
            {
                "video_id": "ok1",
                "title": "日銀 利上げと金融政策の最新解説",
                "description": "日本経済と金融政策を詳しく分析します。",
                "tags": ["日本経済", "日銀"],
                "channel_id": "ch1",
                "channel_title": "Macro Japan",
                "published_at": "2026-06-08T10:00:00Z",
                "duration_seconds": 900,
                "statistics": {"view_count": 20000, "like_count": 1000, "comment_count": 50},
            },
            {
                "video_id": "bad1",
                "title": "広告 日銀ニュース",
                "description": "広告案件です。",
                "tags": ["日銀"],
                "channel_id": "ch2",
                "channel_title": "Promo Channel",
                "published_at": "2026-06-08T10:00:00Z",
                "duration_seconds": 800,
                "statistics": {"view_count": 5000},
            },
        ]
        result = filter_and_rank(videos, self.config)
        self.assertEqual(result["skill"], "hermes-youtube-signal-scout")
        self.assertEqual(len(result["videos"]), 1)
        self.assertEqual(result["videos"][0]["video_id"], "ok1")
        self.assertEqual(len(result["rejected"]), 1)
        self.assertIn("排除词", result["rejected"][0]["reason"])

    def test_rejects_shorts_when_disabled(self):
        videos = [
            {
                "video_id": "short1",
                "title": "日銀 shorts",
                "description": "金融政策",
                "tags": ["日銀"],
                "channel_id": "ch1",
                "channel_title": "Macro Japan",
                "published_at": "2026-06-08T10:00:00Z",
                "duration_seconds": 45,
                "statistics": {"view_count": 10000},
            }
        ]
        result = filter_and_rank(videos, self.config)
        self.assertEqual(result["videos"], [])
        self.assertIn("Shorts", result["rejected"][0]["reason"])

    def test_zero_threshold_is_respected(self):
        config = dict(self.config)
        config["topic_score_threshold"] = 0.0
        videos = [
            {
                "video_id": "weak1",
                "title": "日銀 brief mention",
                "description": "general market update",
                "tags": [],
                "channel_id": "ch1",
                "channel_title": "Market Notes",
                "published_at": "2026-06-08T10:00:00Z",
                "duration_seconds": 900,
                "statistics": {"view_count": 2000},
            }
        ]
        result = filter_and_rank(videos, config)
        self.assertEqual(len(result["videos"]), 1)
        self.assertLess(result["videos"][0]["topic_score"], 0.55)

    def test_large_synonym_pool_does_not_suppress_relevant_video(self):
        config = dict(self.config)
        config["include_keywords"] = [
            "AI泡沫", "AI bubble", "人工智能", "AIバブル", "生成AI", "GenAI", "ChatGPT",
            "LLM", "AI投资", "tech bubble", "Nvidia", "GPU", "AI估值", "AI过度", "科技泡沫",
        ]
        config["target_tags"] = ["AI泡沫", "Nvidia", "GPU"]
        config["exclude_keywords"] = ["广告", "推广", "sponsored"]
        config["topic_score_threshold"] = 0.55
        config["min_views"] = 0
        videos = [
            {
                "video_id": "ai-bubble-1",
                "title": "AI泡沫還是新時代？深度對比2000年互聯網泡沫 Nvidia GPU 投资",
                "description": "AI bubble, LLM and GenAI valuation analysis without sponsor content.",
                "tags": ["AI泡沫", "Nvidia", "GPU"],
                "channel_id": "ch-ai",
                "channel_title": "AI Market Research",
                "published_at": "2026-06-08T10:00:00Z",
                "duration_seconds": 1200,
                "statistics": {"view_count": 50000, "like_count": 2000, "comment_count": 200},
            }
        ]
        result = filter_and_rank(videos, config)
        self.assertEqual(len(result["videos"]), 1)
        self.assertGreaterEqual(result["videos"][0]["topic_score"], 0.55)

    def test_score_components_and_future_date_behavior(self):
        config = dict(self.config)
        config["topic_score_threshold"] = 0
        config["min_views"] = 0
        videos = [
            {
                "video_id": "future",
                "title": "日銀",
                "description": "",
                "tags": [],
                "channel_id": "ch1",
                "channel_title": "",
                "published_at": "2999-01-01T00:00:00Z",
                "duration_seconds": 900,
                "statistics": {},
            },
            {
                "video_id": "current",
                "title": "日銀",
                "description": "",
                "tags": [],
                "channel_id": "trusted",
                "channel_title": "",
                "published_at": "2026-06-08T10:00:00Z",
                "duration_seconds": 900,
                "statistics": {},
            },
        ]
        config["trusted_channel_ids"] = ["trusted"]
        result = filter_and_rank(videos, config)
        self.assertIn("未来", result["rejected"][0]["reason"])
        self.assertEqual(result["videos"][0]["score_components"]["channel"], 0.1)
        self.assertEqual(result["videos"][0]["score_components"]["engagement"], 0.0)

    def test_reject_possible_ads_is_configurable(self):
        video = {
            "video_id": "ad",
            "title": "日銀 sponsored",
            "description": "",
            "tags": [],
            "channel_id": "ch1",
            "channel_title": "",
            "published_at": "2026-06-08T10:00:00Z",
            "duration_seconds": 900,
            "statistics": {"view_count": 2000},
        }
        config = dict(self.config)
        config["topic_score_threshold"] = 0
        config["reject_possible_ads"] = False
        self.assertEqual(len(filter_and_rank([video], config)["videos"]), 1)
        config["reject_possible_ads"] = True
        self.assertIn("广告", filter_and_rank([video], config)["rejected"][0]["reason"])

    def test_rejects_entertainment_when_enabled(self):
        video = {
            "video_id": "entertainment",
            "title": "日銀 reaction 搞笑",
            "description": "",
            "tags": ["日銀"],
            "channel_id": "ch1",
            "channel_title": "",
            "published_at": "2026-06-08T10:00:00Z",
            "duration_seconds": 900,
            "statistics": {"view_count": 2000},
        }
        config = dict(self.config)
        config["topic_score_threshold"] = 0
        config["reject_entertainment"] = True
        result = filter_and_rank([video], config)
        self.assertIn("娱乐", result["rejected"][0]["reason"])

    def test_target_tags_only_matches_video_tags(self):
        config = dict(self.config)
        config["include_keywords"] = []
        config["target_tags"] = ["日本経済"]
        config["topic_score_threshold"] = 0
        config["min_views"] = 0
        video = {
            "video_id": "tag-only",
            "title": "Market update",
            "description": "",
            "tags": ["日本経済"],
            "channel_id": "ch1",
            "channel_title": "",
            "published_at": "2026-06-08T10:00:00Z",
            "duration_seconds": 900,
            "statistics": {},
        }
        result = filter_and_rank([video], config)
        self.assertEqual(result["videos"][0]["video_id"], "tag-only")

    def test_explicit_time_window_gives_full_freshness(self):
        now = datetime(2026, 6, 14, tzinfo=timezone.utc)
        config = {
            "published_after": "2026-06-07T00:00:00Z",
            "published_before": "2026-06-14T00:00:00Z",
        }
        oldest = {"published_at": "2026-06-07T00:00:00Z"}
        middle = {"published_at": "2026-06-10T12:00:00Z"}
        newest = {"published_at": "2026-06-14T00:00:00Z"}
        self.assertAlmostEqual(_freshness_score(oldest, config, now), 1.0)
        self.assertAlmostEqual(_freshness_score(middle, config, now), 1.0)
        self.assertAlmostEqual(_freshness_score(newest, config, now), 1.0)

    def test_thirty_day_window_decays_after_first_seven_days(self):
        now = datetime(2026, 6, 14, tzinfo=timezone.utc)
        config = {
            "published_after": "2026-05-15T00:00:00Z",
            "published_before": "2026-06-14T00:00:00Z",
        }
        newest = {"published_at": "2026-06-14T00:00:00Z"}
        seven_days_old = {"published_at": "2026-06-07T00:00:00Z"}
        middle_of_decay = {"published_at": "2026-05-26T12:00:00Z"}
        oldest = {"published_at": "2026-05-15T00:00:00Z"}
        self.assertAlmostEqual(_freshness_score(newest, config, now), 1.0)
        self.assertAlmostEqual(_freshness_score(seven_days_old, config, now), 1.0)
        self.assertAlmostEqual(_freshness_score(middle_of_decay, config, now), 0.75)
        self.assertAlmostEqual(_freshness_score(oldest, config, now), 0.50)

    def test_freshness_uses_rolling_30_days_without_start_date(self):
        now = datetime(2026, 6, 14, tzinfo=timezone.utc)
        config = {"published_before": "2026-06-14T00:00:00Z"}
        oldest = {"published_at": "2026-05-15T00:00:00Z"}
        middle = {"published_at": "2026-05-30T00:00:00Z"}
        newest = {"published_at": "2026-06-14T00:00:00Z"}
        self.assertAlmostEqual(_freshness_score(oldest, config, now), 0.0)
        self.assertAlmostEqual(_freshness_score(middle, config, now), 0.5)
        self.assertAlmostEqual(_freshness_score(newest, config, now), 1.0)


if __name__ == "__main__":
    unittest.main()
