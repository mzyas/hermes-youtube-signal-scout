import unittest

from tools.search_discovery import build_query


class QueryBuildingTests(unittest.TestCase):
    def test_build_query_with_include_and_exclude(self):
        query = build_query(["日本央行", "日銀", "BOJ"], ["娱乐", "切り抜き"])
        self.assertEqual(query, "日本央行|日銀|BOJ -娱乐 -切り抜き")

    def test_build_query_omits_empty_terms(self):
        query = build_query(["AI agent", " ", "browser-use"], [])
        self.assertEqual(query, "AI agent|browser-use")


if __name__ == "__main__":
    unittest.main()