import unittest

from tools.text_matcher import collect_matches, match_keywords


class TextMatcherTests(unittest.TestCase):
    def test_case_insensitive_keyword_match(self):
        self.assertEqual(match_keywords("AI Agent Browser Automation", ["ai agent", "missing"]), ["ai agent"])

    def test_collect_matches_across_fields(self):
        video = {
            "title": "日銀 利上げ 解説",
            "description": "金融政策の最新ニュース",
            "tags": ["日本経済", "日銀"],
            "channel_title": "Macro Japan",
        }
        matches = collect_matches(video, ["日銀", "金融政策"], ["日本経済"])
        self.assertEqual(matches["title"], ["日銀"])
        self.assertEqual(matches["description"], ["金融政策"])
        self.assertIn("日本経済", matches["tags"])


if __name__ == "__main__":
    unittest.main()