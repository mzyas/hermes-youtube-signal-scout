import unittest

from tools.errors import ConfigurationError
from tools.weekly_runner import run_weekly


def video_resource(video_id):
    return {
        "id": video_id,
        "snippet": {
            "title": "signal update",
            "channelId": "UC1234567890123456789012",
            "channelTitle": "Signal Desk",
            "publishedAt": "2026-06-10T00:00:00Z",
            "description": "signal analysis",
            "tags": ["signal"],
        },
        "contentDetails": {"duration": "PT10M"},
        "statistics": {"viewCount": "1000", "likeCount": "20", "commentCount": "3"},
    }


def long_channel_resource(video_id, channel_title):
    return {
        "id": video_id,
        "snippet": {
            "title": "signal update",
            "channelId": "UC1234567890123456789012",
            "channelTitle": channel_title,
            "publishedAt": "2026-06-10T00:00:00Z",
            "description": "signal analysis",
            "tags": ["signal"],
        },
        "contentDetails": {"duration": "PT10M"},
        "statistics": {"viewCount": "1000", "likeCount": "20", "commentCount": "3"},
    }


class FakeYouTubeClient:
    def __init__(self, ids=None, channel_titles=None):
        self.ids = ids or []
        self.channel_titles = channel_titles or {}

    def get(self, endpoint, params):
        if endpoint == "search":
            return {"items": [{"id": {"videoId": value}} for value in self.ids]}
        if endpoint == "videos":
            items = []
            for value in str(params["id"]).split(","):
                if value in self.channel_titles:
                    items.append(long_channel_resource(value, self.channel_titles[value]))
                else:
                    items.append(video_resource(value))
            return {"items": items}
        raise AssertionError(endpoint)


class WeeklyRunnerTests(unittest.TestCase):
    def test_runs_multiple_topics_and_builds_html_email_handoff(self):
        client = FakeYouTubeClient(["video-1"])
        result = run_weekly({
            "schedule": {"cron": "0 9 * * 1", "timezone": "Asia/Tokyo"},
            "defaults": {
                "cache_enabled": False,
                "topic_score_threshold": 0,
                "region_code": "JP",
                "region_priority_tiers": [],
                "target_results": 1,
                "max_results": 1,
            },
            "topics": ["global economy", {"topic": "AI chips"}],
            "email": {
                "recipients": ["analyst@example.com"],
                "subject": "Weekly Signals",
            },
        }, client=client)

        handoff = result["email_handoff"]
        self.assertEqual(handoff["action"], "send_email")
        self.assertEqual(handoff["recipients"], ["analyst@example.com"])
        self.assertEqual(handoff["subject"], "Weekly Signals")
        self.assertEqual(len(handoff["sections"]), 2)
        self.assertIn("<html>", handoff["html_body"])
        self.assertIn("global economy", handoff["html_body"])
        self.assertIn("AI chips", handoff["html_body"])
        # Old contract fields are gone
        self.assertNotIn("html_requirements", handoff)
        self.assertNotIn("markdown_body", handoff)

    def test_requires_non_empty_topics(self):
        with self.assertRaisesRegex(ConfigurationError, "topics"):
            run_weekly({"topics": []}, client=FakeYouTubeClient())

    def test_email_html_truncates_long_channel_titles(self):
        long_channel = "SurTaal Studios \u2022 2.3M views \u2022 2 days ago \u2022 extra spam"
        client = FakeYouTubeClient(
            ids=["video-1"],
            channel_titles={"video-1": long_channel},
        )
        result = run_weekly({
            "schedule": {"cron": "0 9 * * 1", "timezone": "Asia/Tokyo"},
            "defaults": {
                "cache_enabled": False,
                "topic_score_threshold": 0,
                "region_code": "JP",
                "region_priority_tiers": [],
                "target_results": 1,
                "max_results": 1,
            },
            "topics": ["long channel test"],
            "email": {"recipients": ["analyst@example.com"], "subject": "Weekly Signals"},
        }, client=client)

        body = result["email_handoff"]["html_body"]
        # The polluted channel title must not appear verbatim in the rendered email
        self.assertNotIn(long_channel, body)
        self.assertNotIn("\u2022", body)

    def test_email_html_omits_failure_section_when_no_failures(self):
        client = FakeYouTubeClient(["video-1"])
        result = run_weekly({
            "schedule": {"cron": "0 9 * * 1", "timezone": "Asia/Tokyo"},
            "defaults": {
                "cache_enabled": False,
                "topic_score_threshold": 0,
                "region_code": "JP",
                "region_priority_tiers": [],
                "target_results": 1,
                "max_results": 1,
            },
            "topics": ["good topic"],
            "email": {"recipients": ["analyst@example.com"], "subject": "Weekly Signals"},
        }, client=client)
        body = result["email_handoff"]["html_body"]
        self.assertNotIn("失败主题", body)


if __name__ == "__main__":
    unittest.main()
