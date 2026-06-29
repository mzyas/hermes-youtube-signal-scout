import unittest

from tools.email_renderer import render_email_html


def _video(
    rank=1,
    title="signal update",
    channel_title="Signal Desk",
    url="https://www.youtube.com/watch?v=video-1",
    topic_score=0.49,
    published_at="2026-06-10T00:00:00Z",
    duration_seconds=125,
    view_count=12345,
):
    return {
        "rank": rank,
        "title": title,
        "url": url,
        "channel_title": channel_title,
        "published_at": published_at,
        "topic_score": topic_score,
        "duration_seconds": duration_seconds,
        "view_count": view_count,
    }


class EmailRendererTests(unittest.TestCase):
    def test_renders_basic_html_structure(self):
        runs = [{"topic": "global economy", "videos": [_video()]}]
        html_out = render_email_html("Weekly", runs, [], "2026-06-29T09:30:00Z")
        self.assertIn("<html>", html_out)
        self.assertIn("<body", html_out)
        self.assertIn("</html>", html_out)
        self.assertIn("YouTube 每周信号报告", html_out)
        self.assertIn("global economy", html_out)
        self.assertIn("12,345", html_out)

    def test_uses_table_layout_only(self):
        runs = [{"topic": "topic", "videos": [_video()]}]
        html_out = render_email_html("s", runs, [], "2026-06-29T09:30:00Z")
        # No <div> layout, no flexbox / grid
        self.assertNotIn('display:flex', html_out)
        self.assertNotIn('display:grid', html_out)
        # Table must exist
        self.assertIn('<table role="presentation"', html_out)
        self.assertIn("<thead>", html_out)
        self.assertIn("<tbody>", html_out)

    def test_uses_inline_styles_only(self):
        runs = [{"topic": "topic", "videos": [_video()]}]
        html_out = render_email_html("s", runs, [], "2026-06-29T09:30:00Z")
        # No <style> blocks
        self.assertNotIn("<style>", html_out)
        self.assertNotIn("<link", html_out)
        # inline style on cells
        self.assertIn('style="border:1px solid #d9d9d9;', html_out)

    def test_escapes_user_input(self):
        runs = [{"topic": "<script>alert(1)</script>", "videos": [_video()]}]
        html_out = render_email_html("s", runs, [], "2026-06-29T09:30:00Z")
        self.assertNotIn("<script>alert(1)</script>", html_out)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html_out)

    def test_renders_failure_section(self):
        failures = [
            {"topic": "bad topic", "error": {"type": "ValueError", "message": "bad input"}}
        ]
        runs = [{"topic": "good topic", "videos": [_video()]}]
        html_out = render_email_html("s", runs, failures, "2026-06-29T09:30:00Z")
        self.assertIn("失败主题", html_out)
        self.assertIn("bad topic", html_out)
        self.assertIn("ValueError", html_out)
        self.assertIn("bad input", html_out)

    def test_omits_failure_section_when_no_failures(self):
        runs = [{"topic": "good", "videos": [_video()]}]
        html_out = render_email_html("s", runs, [], "2026-06-29T09:30:00Z")
        self.assertNotIn("失败主题", html_out)

    def test_truncates_long_channel_title_to_60(self):
        long = "A" * 200
        runs = [{"topic": "t", "videos": [_video(channel_title=long)]}]
        html_out = render_email_html("s", runs, [], "2026-06-29T09:30:00Z")
        self.assertNotIn("A" * 200, html_out)
        # channel cell content should be exactly 60 chars
        import re
        m = re.search(r"max-width:220px[^>]*>([^<]+)</td>", html_out)
        self.assertIsNotNone(m, f"channel cell not found in: {html_out}")
        self.assertEqual(len(m.group(1)), 60)

    def test_truncates_long_title_to_80(self):
        long = "B" * 500
        runs = [{"topic": "t", "videos": [_video(title=long)]}]
        html_out = render_email_html("s", runs, [], "2026-06-29T09:30:00Z")
        self.assertNotIn("B" * 500, html_out)
        import re
        m = re.search(r'max-width:400px[^>]*><a href="[^"]+" style="[^"]+">([^<]+)</a>', html_out)
        self.assertIsNotNone(m, f"title link not found in: {html_out}")
        self.assertEqual(len(m.group(1)), 80)

    def test_empty_topic_renders_placeholder(self):
        runs = [{"topic": "empty", "videos": []}]
        html_out = render_email_html("s", runs, [], "2026-06-29T09:30:00Z")
        self.assertIn("empty", html_out)
        self.assertIn("暂无通过筛选的视频", html_out)

    def test_renders_multiple_topics(self):
        runs = [
            {"topic": "topic A", "videos": [_video(rank=1, title="video A")]},
            {"topic": "topic B", "videos": [_video(rank=1, title="video B")]},
        ]
        html_out = render_email_html("s", runs, [], "2026-06-29T09:30:00Z")
        self.assertIn("topic A", html_out)
        self.assertIn("topic B", html_out)
        self.assertIn("video A", html_out)
        self.assertIn("video B", html_out)
        self.assertIn("已收录 2 个主题", html_out)


if __name__ == "__main__":
    unittest.main()
