import unittest
from datetime import datetime, timezone

from tools.filter_ranker import (
    _freshness_score,
    _smoothed_engagement_score,
    _view_velocity,
    filter_and_rank,
)


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

    def test_keeps_highest_scoring_video_per_channel(self):
        config = dict(self.config)
        config.update(topic_score_threshold=0, min_views=0)
        videos = [
            {
                "video_id": "lower",
                "title": "日銀",
                "description": "",
                "tags": [],
                "channel_id": "same-channel",
                "channel_title": "Macro Japan",
                "published_at": "2026-06-09T00:00:00Z",
                "duration_seconds": 900,
                "statistics": {"view_count": 1000},
            },
            {
                "video_id": "higher",
                "title": "日銀 金融政策 利上げ",
                "description": "金融政策",
                "tags": ["日銀", "日本経済"],
                "channel_id": "same-channel",
                "channel_title": "Macro Japan",
                "published_at": "2026-06-08T00:00:00Z",
                "duration_seconds": 900,
                "statistics": {"view_count": 1000},
            },
        ]
        result = filter_and_rank(videos, config)

        self.assertEqual([video["video_id"] for video in result["videos"]], ["higher"])
        duplicate = next(
            item for item in result["rejected"]
            if item.get("reason_code") == "channel_limit_exceeded"
        )
        self.assertEqual(duplicate["video_id"], "lower")
        self.assertIn("video_id=higher", duplicate["reason"])
        self.assertEqual(
            sum(
                item.get("reason_code") == "channel_limit_exceeded"
                for item in result["rejected"]
            ),
            1,
        )

    def test_channel_ties_use_date_views_then_candidate_order(self):
        config = dict(self.config)
        config.update(topic_score_threshold=0, min_views=0)

        def candidate(video_id, channel_id, published_at, views):
            return {
                "video_id": video_id,
                "title": "日銀",
                "description": "",
                "tags": [],
                "channel_id": channel_id,
                "channel_title": "",
                "published_at": published_at,
                "duration_seconds": 900,
                "statistics": {"view_count": views},
            }

        videos = [
            candidate("date-old", "date-channel", "2026-06-08T00:00:00Z", 1000),
            candidate("date-new", "date-channel", "2026-06-09T00:00:00Z", 1000),
            candidate("views-low", "views-channel", "2026-06-09T00:00:00Z", 1000),
            candidate("views-high", "views-channel", "2026-06-09T00:00:00Z", 2000),
            candidate("order-first", "order-channel", "2026-06-09T00:00:00Z", 1000),
            candidate("order-second", "order-channel", "2026-06-09T00:00:00Z", 1000),
        ]
        result = filter_and_rank(videos, config)

        self.assertEqual(
            {video["video_id"] for video in result["videos"]},
            {"date-new", "views-high", "order-first"},
        )

    def test_channel_title_fallback_and_missing_channel_identity(self):
        config = dict(self.config)
        config.update(topic_score_threshold=0, min_views=0)
        base = {
            "title": "日銀",
            "description": "",
            "tags": [],
            "published_at": "2026-06-09T00:00:00Z",
            "duration_seconds": 900,
            "statistics": {"view_count": 1000},
        }
        videos = [
            {**base, "video_id": "title-1", "channel_id": "", "channel_title": " Macro   Japan "},
            {**base, "video_id": "title-2", "channel_id": "", "channel_title": "macro japan"},
            {**base, "video_id": "missing-1", "channel_id": "", "channel_title": ""},
            {**base, "video_id": "missing-2", "channel_id": "", "channel_title": ""},
        ]
        result = filter_and_rank(videos, config)

        self.assertEqual(
            {video["video_id"] for video in result["videos"]},
            {"title-1", "missing-1", "missing-2"},
        )

    def test_channel_limit_can_be_increased(self):
        config = dict(self.config)
        config.update(topic_score_threshold=0, min_views=0, max_videos_per_channel=2)
        videos = [
            {
                "video_id": f"same-{index}",
                "title": "日銀",
                "description": "",
                "tags": [],
                "channel_id": "same-channel",
                "channel_title": "",
                "published_at": f"2026-06-0{index + 7}T00:00:00Z",
                "duration_seconds": 900,
                "statistics": {"view_count": 1000},
            }
            for index in range(3)
        ]
        result = filter_and_rank(videos, config)
        self.assertEqual(len(result["videos"]), 2)
        self.assertEqual(
            sum(
                item.get("reason_code") == "channel_limit_exceeded"
                for item in result["rejected"]
            ),
            1,
        )

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
        self.assertEqual(
            result["videos"][0]["score_components"]["channel_credibility"],
            0.1,
        )
        self.assertEqual(
            result["videos"][0]["score_components"]["smoothed_engagement"],
            0.0,
        )

    def test_score_uses_six_weighted_components(self):
        config = dict(self.config)
        config.update(
            topic_score_threshold=0,
            min_views=0,
            trusted_channel_ids=["trusted"],
        )
        video = {
            "video_id": "six-components",
            "title": "日銀 金融政策 利上げ",
            "description": "日本経済と金融政策を詳しく説明する動画です。" * 5,
            "tags": ["日銀", "金融政策", "日本経済"],
            "category_id": "25",
            "channel_id": "trusted",
            "channel_title": "日銀 Research",
            "published_at": "2026-06-08T10:00:00Z",
            "duration_seconds": 900,
            "statistics": {
                "view_count": 10000,
                "like_count": 500,
                "comment_count": 50,
            },
        }
        ranked = filter_and_rank([video], config)["videos"][0]
        self.assertEqual(
            set(ranked["score_components"]),
            {
                "topic_relevance",
                "freshness",
                "view_velocity",
                "smoothed_engagement",
                "channel_credibility",
                "information_completeness",
            },
        )
        self.assertAlmostEqual(
            ranked["topic_score"],
            sum(ranked["score_components"].values()),
            places=4,
        )
        self.assertEqual(ranked["score_components"]["channel_credibility"], 0.1)

    def test_view_velocity_prefers_snapshot_delta(self):
        now = datetime(2026, 6, 14, 12, tzinfo=timezone.utc)
        snapshot_video = {
            "published_at": "2026-06-10T00:00:00Z",
            "statistics": {"view_count": 2200},
            "previous_statistics": {
                "view_count": 1000,
                "captured_at": "2026-06-14T06:00:00Z",
            },
        }
        velocity, source = _view_velocity(snapshot_video, now)
        self.assertAlmostEqual(velocity, 200.0)
        self.assertEqual(source, "snapshot_delta")

        first_seen = {
            "published_at": "2026-06-14T02:00:00Z",
            "statistics": {"view_count": 1000},
        }
        velocity, source = _view_velocity(first_seen, now)
        self.assertAlmostEqual(velocity, 100.0)
        self.assertEqual(source, "lifetime_average")

    def test_higher_view_velocity_improves_rank_for_equal_relevance(self):
        config = dict(self.config)
        config.update(topic_score_threshold=0, min_views=0)
        common = {
            "title": "日銀 金融政策",
            "description": "金融政策の解説",
            "tags": ["日銀"],
            "published_at": "2026-06-08T10:00:00Z",
            "duration_seconds": 900,
            "statistics": {
                "like_count": 10,
                "comment_count": 1,
            },
        }
        videos = [
            {
                **common,
                "video_id": "slow",
                "channel_id": "slow-channel",
                "channel_title": "Macro",
                "statistics": {**common["statistics"], "view_count": 1000},
            },
            {
                **common,
                "video_id": "fast",
                "channel_id": "fast-channel",
                "channel_title": "Macro",
                "statistics": {**common["statistics"], "view_count": 10000},
            },
        ]
        result = filter_and_rank(videos, config)
        self.assertEqual(result["videos"][0]["video_id"], "fast")
        self.assertGreater(
            result["videos"][0]["score_components"]["view_velocity"],
            result["videos"][1]["score_components"]["view_velocity"],
        )

    def test_bayesian_engagement_reduces_low_view_outlier(self):
        low_view = {
            "statistics": {"view_count": 10, "like_count": 2, "comment_count": 0}
        }
        score, rate = _smoothed_engagement_score(
            low_view,
            baseline=0.02,
            prior_views=1000,
        )
        self.assertLess(rate, 0.03)
        self.assertAlmostEqual(score, rate * 20)

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

    def test_rejects_academy_and_exam_training_channels(self):
        config = dict(self.config)
        config.update(
            topic_score_threshold=0,
            min_views=0,
            reject_exam_training=True,
        )
        base = {
            "title": "日銀 金融政策",
            "description": "金融政策の解説",
            "tags": ["日銀"],
            "published_at": "2026-06-08T10:00:00Z",
            "duration_seconds": 900,
            "statistics": {"view_count": 2000},
        }
        videos = [
            {
                **base,
                "video_id": "academy",
                "channel_id": "academy-channel",
                "channel_title": "Global Finance Academy",
            },
            {
                **base,
                "video_id": "civil-service",
                "channel_id": "exam-channel",
                "channel_title": "公考申论培训",
            },
            {
                **base,
                "video_id": "japanese-exam",
                "channel_id": "jp-exam-channel",
                "channel_title": "公務員試験対策予備校",
            },
        ]
        result = filter_and_rank(videos, config)
        self.assertEqual(result["videos"], [])
        self.assertEqual(len(result["rejected"]), 3)
        self.assertTrue(all("考试培训" in item["reason"] for item in result["rejected"]))

    def test_rejects_vajiram_and_ravi_official_channel(self):
        config = dict(self.config)
        config.update(
            topic_score_threshold=0,
            min_views=0,
            reject_exam_training=True,
        )
        video = {
            "video_id": "vajiram-ravi",
            "title": "Current Affairs Analysis for UPSC preparation",
            "description": "Daily current affairs course",
            "tags": ["UPSC"],
            "channel_id": "vajiram-ravi-channel",
            "channel_title": "Vajiram and Ravi Official",
            "published_at": "2026-06-08T10:00:00Z",
            "duration_seconds": 900,
            "statistics": {"view_count": 2000},
        }
        result = filter_and_rank([video], config)
        self.assertEqual(result["videos"], [])
        self.assertIn("考试培训", result["rejected"][0]["reason"])

    def test_vajiram_name_alone_does_not_trigger_brand_blocklist(self):
        config = dict(self.config)
        config.update(
            topic_score_threshold=0,
            min_views=0,
            reject_exam_training=True,
        )
        video = {
            "video_id": "vajiram-name-only",
            "title": "日銀 金融政策 Current Affairs",
            "description": "日本経済のニュース分析",
            "tags": ["日銀"],
            "channel_id": "vajiram-ravi-channel",
            "channel_title": "Vajiram and Ravi Official",
            "published_at": "2026-06-08T10:00:00Z",
            "duration_seconds": 900,
            "statistics": {"view_count": 2000},
        }
        result = filter_and_rank([video], config)
        self.assertEqual(
            [ranked["video_id"] for ranked in result["videos"]],
            ["vajiram-name-only"],
        )

    def test_rejects_upsc_coaching_combination_but_not_upsc_news(self):
        config = dict(self.config)
        config.update(
            topic_score_threshold=0,
            min_views=0,
            reject_exam_training=True,
        )
        common = {
            "description": "日銀 金融政策",
            "tags": ["日銀"],
            "published_at": "2026-06-08T10:00:00Z",
            "duration_seconds": 900,
            "statistics": {"view_count": 2000},
        }
        videos = [
            {
                **common,
                "video_id": "upsc-course",
                "title": "日銀と経済 UPSC preparation course",
                "channel_id": "course-channel",
                "channel_title": "Current Affairs Learning",
            },
            {
                **common,
                "video_id": "upsc-news",
                "title": "日銀と経済 UPSC policy news",
                "channel_id": "news-channel",
                "channel_title": "India Policy News",
            },
        ]
        result = filter_and_rank(videos, config)
        self.assertEqual(
            [video["video_id"] for video in result["videos"]],
            ["upsc-news"],
        )
        self.assertEqual(result["rejected"][0]["video_id"], "upsc-course")

    def test_rejects_explicit_exam_training_content(self):
        config = dict(self.config)
        config.update(
            topic_score_threshold=0,
            min_views=0,
            reject_exam_training=True,
        )
        video = {
            "video_id": "exam-course",
            "title": "日銀ニュースと公务员考试备考课程",
            "description": "金融政策",
            "tags": ["日銀"],
            "channel_id": "generic-channel",
            "channel_title": "Daily Learning",
            "published_at": "2026-06-08T10:00:00Z",
            "duration_seconds": 900,
            "statistics": {"view_count": 2000},
        }
        result = filter_and_rank([video], config)
        self.assertEqual(result["videos"], [])
        self.assertIn("考公备考", result["rejected"][0]["reason"])

    def test_exam_training_filter_is_configurable(self):
        config = dict(self.config)
        config.update(
            topic_score_threshold=0,
            min_views=0,
            reject_exam_training=False,
        )
        video = {
            "video_id": "academy-allowed",
            "title": "日銀 金融政策",
            "description": "金融政策",
            "tags": ["日銀"],
            "channel_id": "academy-channel",
            "channel_title": "Macro Academy",
            "published_at": "2026-06-08T10:00:00Z",
            "duration_seconds": 900,
            "statistics": {"view_count": 2000},
        }
        self.assertEqual(len(filter_and_rank([video], config)["videos"]), 1)

    def test_general_university_education_is_not_exam_training(self):
        config = dict(self.config)
        config.update(
            topic_score_threshold=0,
            min_views=0,
            reject_exam_training=True,
        )
        video = {
            "video_id": "university",
            "title": "日銀 金融政策 公開講座",
            "description": "大学教授による日本経済の解説",
            "tags": ["日銀", "日本経済"],
            "channel_id": "university-channel",
            "channel_title": "Tokyo University Economics",
            "published_at": "2026-06-08T10:00:00Z",
            "duration_seconds": 900,
            "statistics": {"view_count": 2000},
        }
        self.assertEqual(len(filter_and_rank([video], config)["videos"]), 1)

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
