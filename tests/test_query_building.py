import unittest

from tools.search_discovery import build_query, resolve_region_codes, search_videos


class FakeClient:
    def __init__(self):
        self.calls = []

    def get(self, endpoint, params):
        self.calls.append((endpoint, params))
        return {"items": [{"id": {"videoId": "video-1"}}]}


class QueryBuildingTests(unittest.TestCase):
    def test_build_query_uses_short_include_only_query(self):
        query = build_query(["日本央行", "日銀", "BOJ", "金融政策", "利上げ"], ["娱乐", "切り抜き"])
        self.assertEqual(query, "日本央行|日銀|BOJ|金融政策")
        self.assertNotIn("-娱乐", query)

    def test_build_query_omits_empty_terms_and_dedupes(self):
        query = build_query(["AI agent", " ", "ai agent", "browser-use"], [])
        self.assertEqual(query, "AI agent|browser-use")

    def test_build_query_caps_long_boolean_query(self):
        query = build_query(
            ["AI泡沫", "AI bubble", "人工智能", "AIバブル", "生成AI", "GenAI", "ChatGPT", "LLM", "AI投资", "tech bubble", "Nvidia", "GPU", "AI估值", "AI过度", "科技泡沫"],
            ["广告", "推广", "sponsored", "promo", "affiliate", "限时优惠", "免费领取", "暴富", "副業", "稼げる", "案件紹介", "切り抜き", "娱乐"],
        )
        self.assertLessEqual(len(query), 80)
        self.assertEqual(query.count("|") + 1, 4)
        self.assertNotIn("-", query)

    def test_search_videos_keeps_exclude_keywords_local(self):
        client = FakeClient()
        result = search_videos(
            client,
            {
                "topic": "AI泡沫",
                "include_keywords": ["AI泡沫", "AI bubble", "人工智能", "AIバブル", "生成AI"],
                "exclude_keywords": ["广告", "推广", "sponsored"],
                "max_results": 5,
                "max_search_pages": 1,
            },
        )
        self.assertEqual(result["video_ids"], ["video-1"])
        _, params = client.calls[0]
        self.assertEqual(params["type"], "video")
        self.assertNotIn("-广告", params["q"])
        self.assertLessEqual(len(params["q"]), 80)

    def test_default_zones_expand_without_language_filter(self):
        client = FakeClient()
        result = search_videos(
            client,
            {
                "topic": "global markets",
                "zones": ["east_asia", "europe", "north_america"],
                "max_search_pages": 1,
            },
        )
        self.assertEqual(
            resolve_region_codes({"zones": ["east_asia", "europe", "north_america"]}),
            ["JP", "KR", "TW", "HK", "GB", "DE", "FR", "US", "CA"],
        )
        self.assertEqual(len(client.calls), 9)
        self.assertNotIn("relevanceLanguage", client.calls[0][1])
        self.assertEqual(result["page_count"], 9)


if __name__ == "__main__":
    unittest.main()
