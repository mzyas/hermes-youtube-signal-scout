import unittest

from tools.filter_ranker import filter_and_rank


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


if __name__ == "__main__":
    unittest.main()