import unittest

from tools.text_sanitize import sanitize_channel_title
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
            "b Channel /b",
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
