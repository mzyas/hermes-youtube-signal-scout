import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.channel_resolver import parse_channel_reference
from tools.config import apply_defaults, load_config
from tools.errors import ConfigurationError


class ConfigAndChannelTests(unittest.TestCase):
    def test_loads_yaml_and_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yaml_path = Path(temp_dir) / "config.yaml"
            yaml_path.write_text("topic: signal\ncache_enabled: false\n", encoding="utf-8")
            json_path = Path(temp_dir) / "config.json"
            json_path.write_text(json.dumps({"topic": "signal", "cache_enabled": False}), encoding="utf-8")
            self.assertEqual(load_config(yaml_path)["topic"], "signal")
            self.assertEqual(load_config(json_path)["topic"], "signal")

    def test_topic_becomes_match_term_when_keywords_are_empty(self):
        config = apply_defaults({"topic": "fallback topic", "cache_enabled": False})
        self.assertEqual(config["include_keywords"], ["fallback topic"])

    def test_default_search_uses_rolling_seven_day_window(self):
        before = datetime.now(timezone.utc) - timedelta(days=7, seconds=2)
        config = apply_defaults({"topic": "signal", "cache_enabled": False})
        after = datetime.fromisoformat(config["published_after"].replace("Z", "+00:00"))
        upper = datetime.now(timezone.utc) - timedelta(days=7) + timedelta(seconds=2)
        self.assertGreaterEqual(after, before)
        self.assertLessEqual(after, upper)

    def test_explicit_time_window_overrides_default_lookback(self):
        config = apply_defaults({
            "topic": "signal",
            "published_after": "2026-01-01T00:00:00Z",
            "cache_enabled": False,
        })
        self.assertEqual(config["published_after"], "2026-01-01T00:00:00Z")

    def test_rejects_timestamp_without_timezone(self):
        with self.assertRaisesRegex(ConfigurationError, "timezone"):
            apply_defaults({"topic": "signal", "published_after": "2026-06-01T00:00:00"})

    def test_rejects_reverse_time_window(self):
        with self.assertRaisesRegex(ConfigurationError, "must not be later"):
            apply_defaults({
                "topic": "signal",
                "published_after": "2026-06-02T00:00:00Z",
                "published_before": "2026-06-01T00:00:00Z",
            })

    def test_channel_reference_formats(self):
        channel_id = "UC1234567890123456789012"
        self.assertEqual(parse_channel_reference(channel_id), channel_id)
        self.assertEqual(parse_channel_reference("@signal"), "@signal")
        self.assertEqual(
            parse_channel_reference(f"https://www.youtube.com/channel/{channel_id}"),
            channel_id,
        )
        self.assertEqual(
            parse_channel_reference("https://youtube.com/@signal/videos"),
            "@signal",
        )

    def test_rejects_unsupported_channel_url(self):
        with self.assertRaises(ConfigurationError):
            parse_channel_reference("https://www.youtube.com/c/custom-name")


if __name__ == "__main__":
    unittest.main()
