import tempfile
import unittest
from pathlib import Path

from tools.cache_store import (
    connect,
    get_previous_statistics,
    init_db,
    save_video,
)


class CacheStoreTests(unittest.TestCase):
    def test_video_statistics_snapshots_are_available_for_growth_scoring(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "cache.sqlite3"
            init_db(path)
            connection = connect(path)
            try:
                save_video(connection, {
                    "video_id": "video-1",
                    "statistics": {
                        "view_count": 100,
                        "like_count": 10,
                        "comment_count": 2,
                    },
                })
                previous = get_previous_statistics(connection, "video-1")
                self.assertEqual(previous["view_count"], 100)
                self.assertEqual(previous["like_count"], 10)
                self.assertEqual(previous["comment_count"], 2)
                self.assertTrue(previous["captured_at"])
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
