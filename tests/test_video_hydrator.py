import unittest

from tools.text_sanitize import (
    sanitize_channel_title,
    sanitize_channel_title_for_email,
    sanitize_title_for_email,
)
from tools.video_hydrator import hydrate_videos, parse_video_resource


class SanitizeChannelTitleTests(unittest.TestCase):
    def test_pure_name_unchanged(self):
        self.assertEqual(sanitize_channel_title("SurTaal Studios"), "SurTaal Studios")

    def test_strips_pollution_delimiters(self):
        result = sanitize_channel_title("SurTaal Studios \u2022 2.3M views \u2022 2 days ago")
        self.assertNotIn("\u2022", result)
        self.assertNotIn("|", result)
        self.assertEqual(result, "SurTaal Studios 2.3M views 2 days ago")

    def test_collapses_whitespace(self):
        self.assertEqual(
            sanitize_channel_title("  SurTaal   Studios  "),
            "SurTaal Studios",
        )

    def test_strips_control_chars(self):
        self.assertEqual(
            sanitize_channel_title("SurTaal\x00\nStudios"),
            "SurTaal Studios",
        )

    def test_strips_html_like_tags(self):
        self.assertEqual(
            sanitize_channel_title("<b>Channel</b>"),
            "Channel",
        )

    def test_keeps_cjk(self):
        self.assertEqual(sanitize_channel_title("\u65e5\u9280"), "\u65e5\u9280")

    def test_keeps_japanese_hiragana(self):
        self.assertEqual(
            sanitize_channel_title("\u8cc7\u683c\u306e\u5b66\u6821TAC \u516c\u5f0f"),
            "\u8cc7\u683c\u306e\u5b66\u6821TAC \u516c\u5f0f",
        )

    def test_normalizes_fullwidth_space(self):
        self.assertEqual(
            sanitize_channel_title("\u516c\u793e\u56e3\u3000\u516c\u5f0f"),
            "\u516c\u793e\u56e3 \u516c\u5f0f",
        )

    def test_truncates_long(self):
        long = "A" * 1000
        result = sanitize_channel_title(long)
        self.assertEqual(len(result), 200)

    def test_pure_punctuation_returns_empty(self):
        self.assertEqual(sanitize_channel_title("---"), "")
        self.assertEqual(sanitize_channel_title("..."), "")
        self.assertEqual(sanitize_channel_title("___"), "")

    def test_empty_and_none_return_empty(self):
        self.assertEqual(sanitize_channel_title(""), "")
        self.assertEqual(sanitize_channel_title(None), "")

    def test_idempotent(self):
        first = sanitize_channel_title("SurTaal Studios \u2022 2.3M views \u2022 2 days ago")
        second = sanitize_channel_title(first)
        self.assertEqual(first, second)

    def test_keeps_thai(self):
        self.assertEqual(sanitize_channel_title("\u0e25\u0e07\u0e17\u0e38\u0e19\u0e2d\u0e30\u0e44\u0e23\u0e14\u0e35"), "\u0e25\u0e07\u0e17\u0e38\u0e19\u0e2d\u0e30\u0e44\u0e23\u0e14\u0e35")

    def test_keeps_korean_hangul(self):
        self.assertEqual(sanitize_channel_title("\ud55c\uad6d\uacbd\uc81c\ub274\uc2a4"), "\ud55c\uad6d\uacbd\uc81c\ub274\uc2a4")

    def test_keeps_devanagari(self):
        self.assertEqual(sanitize_channel_title("\u0928\u093f\u0935\u0947\u0936 \u0938\u092e\u093e\u091a\u093e\u0930"), "\u0928\u093f\u0935\u0947\u0936 \u0938\u092e\u093e\u091a\u093e\u0930")

    def test_keeps_cyrillic(self):
        self.assertEqual(sanitize_channel_title("\u0420\u043e\u0441\u0441\u0438\u044f \u042d\u043a\u043e\u043d\u043e\u043c\u0438\u043a\u0430"), "\u0420\u043e\u0441\u0441\u0438\u044f \u042d\u043a\u043e\u043d\u043e\u043c\u0438\u043a\u0430")

    def test_keeps_latin_extended(self):
        self.assertEqual(sanitize_channel_title("Caf\u00e9 M\u00fcller"), "Caf\u00e9 M\u00fcller")

    def test_keeps_arabic(self):
        self.assertEqual(sanitize_channel_title("\u0627\u0644\u0627\u0633\u062a\u062b\u0645\u0627\u0631"), "\u0627\u0644\u0627\u0633\u062a\u062b\u0645\u0627\u0631")

    def test_keeps_vietnamese(self):
        self.assertEqual(sanitize_channel_title("\u0110\u1ea7u t\u01b0"), "\u0110\u1ea7u t\u01b0")

    def test_still_strips_html_tags(self):
        self.assertEqual(
            sanitize_channel_title("<script>alert(1)</script>title"),
            "alert(1) title",
        )


class SanitizeChannelTitleForEmailTests(unittest.TestCase):
    def test_short_value_unchanged(self):
        self.assertEqual(
            sanitize_channel_title_for_email("SurTaal Studios"),
            "SurTaal Studios",
        )

    def test_default_max_len_is_60(self):
        long = "A" * 200
        result = sanitize_channel_title_for_email(long)
        self.assertEqual(len(result), 60)
        self.assertTrue(result.endswith("\u2026"))

    def test_custom_max_len(self):
        long = "A" * 100
        result = sanitize_channel_title_for_email(long, max_len=20)
        self.assertEqual(len(result), 20)

    def test_strips_pollution_then_truncates(self):
        result = sanitize_channel_title_for_email(
            "SurTaal Studios \u2022 2.3M views \u2022 2 days ago", max_len=15
        )
        self.assertEqual(len(result), 15)
        self.assertNotIn("\u2022", result)
        self.assertNotIn("views", result)
        self.assertTrue(result.endswith("\u2026"))

    def test_cjk_handling(self):
        result = sanitize_channel_title_for_email(
            "\u8cc7\u683c\u306e\u5b66\u6821TAC \u516c\u5f0f", max_len=10
        )
        self.assertEqual(len(result), 10)
        self.assertTrue(result.endswith("\u2026"))

    def test_empty_and_none(self):
        self.assertEqual(sanitize_channel_title_for_email(""), "")
        self.assertEqual(sanitize_channel_title_for_email(None), "")

    def test_keeps_thai_through_email(self):
        text = "\u0e25\u0e07\u0e17\u0e38\u0e19\u0e2d\u0e30\u0e44\u0e23\u0e14\u0e35"
        self.assertEqual(sanitize_channel_title_for_email(text), text)


class SanitizeTitleForEmailTests(unittest.TestCase):
    def test_short_value_unchanged(self):
        self.assertEqual(sanitize_title_for_email("signal update"), "signal update")

    def test_default_max_len_is_80(self):
        long = "A" * 500
        result = sanitize_title_for_email(long)
        self.assertEqual(len(result), 80)
        self.assertTrue(result.endswith("\u2026"))

    def test_custom_max_len(self):
        result = sanitize_title_for_email("A" * 200, max_len=50)
        self.assertEqual(len(result), 50)

    def test_strips_html_tags(self):
        result = sanitize_title_for_email("<script>alert(1)</script>title")
        self.assertNotIn("<", result)
        self.assertNotIn(">", result)
        self.assertNotIn("script", result)
        self.assertIn("title", result)

    def test_keeps_thai_in_title(self):
        text = "\u0e27\u0e34\u0e40\u0e04\u0e23\u0e32\u0e30\u0e2b\u0e4c\u0e2b\u0e38\u0e49\u0e19 (NASDAQ: KEEL)"
        self.assertEqual(sanitize_title_for_email(text), text)

    def test_strips_pollution_delimiters(self):
        result = sanitize_title_for_email(
            "Real Title \u2022 1.2M views \u2022 5 hours ago"
        )
        self.assertNotIn("\u2022", result)
        self.assertIn("Real", result)
        self.assertIn("Title", result)

    def test_empty_and_none(self):
        self.assertEqual(sanitize_title_for_email(""), "")
        self.assertEqual(sanitize_title_for_email(None), "")


def _resource(video_id: str, channel_title: str) -> dict:
    return {
        "id": video_id,
        "snippet": {
            "title": f"video {video_id}",
            "channelId": f"UC{video_id}",
            "channelTitle": channel_title,
            "publishedAt": "2026-06-10T00:00:00Z",
            "description": "",
            "tags": [],
        },
        "contentDetails": {"duration": "PT10M"},
        "statistics": {"viewCount": "1000", "likeCount": "20", "commentCount": "3"},
    }


class ParseVideoResourceSanitizationTests(unittest.TestCase):
    def test_parse_video_resource_sanitizes_channel_title(self):
        polluted = "SurTaal Studios \u2022 2.3M views \u2022 2 days ago"
        result = parse_video_resource(_resource("v1", polluted))
        self.assertEqual(result["channel_title"], "SurTaal Studios 2.3M views 2 days ago")
        self.assertNotIn("\u2022", result["channel_title"])

    def test_parse_video_resource_preserves_raw_json_channel_title(self):
        polluted = "SurTaal Studios \u2022 2.3M views \u2022 2 days ago"
        result = parse_video_resource(_resource("v1", polluted))
        self.assertEqual(
            result["raw_json"]["snippet"]["channelTitle"],
            polluted,
        )


class _FakeClient:
    def __init__(self, items_by_id: dict[str, dict]):
        self._items = items_by_id
        self.calls: list[tuple[str, dict]] = []

    def get(self, endpoint: str, params: dict) -> dict:
        self.calls.append((endpoint, dict(params)))
        ids = [value for value in str(params["id"]).split(",") if value]
        return {"items": [self._items[video_id] for video_id in ids]}


class HydrateVideosSanitizationTests(unittest.TestCase):
    def test_hydrate_videos_sanitizes_every_video(self):
        client = _FakeClient(
            {
                "v1": _resource("v1", "SurTaal Studios \u2022 2.3M views \u2022 2 days ago"),
                "v2": _resource("v2", "  Macro  Japan  "),
                "v3": _resource("v3", "\u8cc7\u683c\u306e\u5b66\u6821TAC"),
            }
        )
        results = hydrate_videos(client, ["v1", "v2", "v3"], batch_size=2)
        titles = {item["video_id"]: item["channel_title"] for item in results}
        self.assertEqual(titles["v1"], "SurTaal Studios 2.3M views 2 days ago")
        self.assertEqual(titles["v2"], "Macro Japan")
        self.assertEqual(titles["v3"], "\u8cc7\u683c\u306e\u5b66\u6821TAC")
        for item in results:
            self.assertNotIn("\u2022", item["channel_title"])
            self.assertNotIn("\u00b7", item["channel_title"])
            self.assertNotIn("\u30fb", item["channel_title"])


if __name__ == "__main__":
    unittest.main()
