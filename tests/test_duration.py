import unittest

from tools.duration import parse_youtube_duration


class DurationTests(unittest.TestCase):
    def test_parse_common_youtube_durations(self):
        self.assertEqual(parse_youtube_duration("PT12M35S"), 755)
        self.assertEqual(parse_youtube_duration("PT1H02M03S"), 3723)
        self.assertEqual(parse_youtube_duration("PT45S"), 45)
        self.assertEqual(parse_youtube_duration("P1DT2H"), 93600)

    def test_invalid_duration_raises(self):
        with self.assertRaises(ValueError):
            parse_youtube_duration("12 minutes")


if __name__ == "__main__":
    unittest.main()