import json
import tempfile
import unittest
from pathlib import Path

from tools.filter_ranker import filter_and_rank
from tools.md_writer import write_markdown_report


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
                    "reason": "命中排除词：sponsored。",
                }
            ],
        }

    def test_writes_markdown_and_json_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            markdown_path = Path(write_markdown_report(self.output, temp_dir, {"version": "0.1.0"}))
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
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), self.output)
            self.assertEqual(self.output["output_files"]["markdown"], str(markdown_path))
            self.assertEqual(self.output["output_files"]["json"], str(json_path))

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
