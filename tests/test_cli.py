import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools.runner import main


class CliTests(unittest.TestCase):
    def test_success_writes_json_to_stdout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.yaml"
            path.write_text("topic: signal\ncache_enabled: false\n", encoding="utf-8")
            stdout = io.StringIO()
            with patch("tools.runner.run", return_value={"skill": "hermes-youtube-signal-scout"}):
                with redirect_stdout(stdout):
                    exit_code = main(["--config", str(path)])
            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["skill"], "hermes-youtube-signal-scout")

    def test_config_error_writes_json_to_stderr(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.yaml"
            path.write_text("mode: discovery\n", encoding="utf-8")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                exit_code = main(["--config", str(path)])
            self.assertEqual(exit_code, 2)
            self.assertEqual(json.loads(stderr.getvalue())["error"], "ConfigurationError")


if __name__ == "__main__":
    unittest.main()
