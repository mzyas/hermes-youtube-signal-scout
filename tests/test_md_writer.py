import json
import tempfile
import unittest
from pathlib import Path

from tools.filter_ranker import filter_and_rank
from tools.md_writer import build_json_report, render_markdown_report, write_markdown_report


class MarkdownWriterTests(unittest.TestCase):
    def setUp(self):
        self.output = {
            "run_id": "ytss_test",
            "skill": "hermes-youtube-signal-scout",
            "topic": "AI|泡沫",
            "mode": "discovery",
            "created_at": "2026-06-10T12:34:56Z",
            "query_plan": {
                "search_queries": ["AI bubble", "Nvidia"],
                "published_after": "2026-06-03T00:00:00Z",
                "published_before": None,
            },
            "quota_usage_estimate": {
                "search_list_calls": 1,
                "videos_list_calls": 1,
                "estimated_quota_cost": 101,
            },
            "videos": [
                {
                    "video_id": "accepted-1",
                    "url": "https://www.youtube.com/watch?v=accepted-1",
                    "title": "AI | bubble update",
                    "channel_title": "Market | Desk",
                    "published_at": "2026-06-09T10:00:00Z",
                    "duration_seconds": 125,
                    "statistics": {"view_count": 12345},
                    "topic_score": 0.491,
                }
            ],
            "rejected": [
                {
                    "video_id": "rejected-1",
                    "title": "Sponsored | clip",
                    "reason_code": "channel_limit_exceeded",
                    "reason": "命中排除词：sponsored。",
                }
            ],
        }

    def test_writes_markdown_and_json_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            markdown_path = Path(write_markdown_report(self.output, temp_dir, {}))
            json_path = markdown_path.with_suffix(".json")

            self.assertEqual(markdown_path.name, "AI_泡沫_20260610_123456.md")
            self.assertTrue(json_path.exists())

            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertIn("[AI \\| bubble update](https://www.youtube.com/watch?v=accepted-1)", markdown)
            self.assertIn("Market \\| Desk", markdown)
            self.assertIn("| 1 | 0.49 |", markdown)
            self.assertIn("| 2026-06-09 | 02:05 | 12,345 |", markdown)
            self.assertIn("命中排除词：sponsored。", markdown)
            self.assertIn("101 units (search×1, videos×1)", markdown)
            self.assertIn("hermes-youtube-signal-scout v0.3.1", markdown)
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), self.output)
            self.assertEqual(self.output["output_files"]["markdown"], str(markdown_path))
            self.assertEqual(self.output["output_files"]["json"], str(json_path))
            self.assertEqual(self.output["report_markdown"], markdown)
            self.assertEqual(self.output["report_json"]["videos"][0]["title"], "AI | bubble update")
            self.assertEqual(
                self.output["report_json"]["rejected"][0]["reason_code"],
                "channel_limit_exceeded",
            )

    def test_canonical_renderer_uses_table_format(self):
        markdown = render_markdown_report(self.output, {"version": "0.2.1"})
        self.assertIn("| # | 得分 | 标题 | 频道 | 发布日期 | 时长 | 播放量 |", markdown)
        self.assertNotIn("🏆", markdown)
        self.assertNotIn("1️⃣", markdown)

    def test_json_report_matches_markdown_columns(self):
        report = build_json_report(self.output, {})
        video = report["videos"][0]
        self.assertEqual(
            set(video),
            {
                "rank",
                "topic_score",
                "title",
                "url",
                "channel_title",
                "published_at",
                "duration_seconds",
                "view_count",
            },
        )
        self.assertEqual(video["rank"], 1)
        self.assertEqual(video["view_count"], 12345)

    def test_filter_and_rank_does_not_write_without_output_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = filter_and_rank([], {"topic": "No output"})
            self.assertNotIn("output_files", result)
            self.assertEqual(list(Path(temp_dir).iterdir()), [])

    def test_filter_and_rank_writes_when_output_dir_is_set(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = filter_and_rank(
                [],
                {
                    "topic": "Integration",
                    "output_dir": temp_dir,
                    "search_queries": ["integration query"],
                    "quota_usage_estimate": {"estimated_quota_cost": 0},
                },
            )
            self.assertTrue(Path(result["output_files"]["markdown"]).exists())
            self.assertTrue(Path(result["output_files"]["json"]).exists())


if __name__ == "__main__":
    unittest.main()
