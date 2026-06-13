import io
import json
import unittest
from urllib.error import HTTPError, URLError

from tools.errors import ApiAuthError, ApiQuotaError, ApiRateLimitError, ApiResponseError
from tools.youtube_client import YouTubeClient


def http_error(code: int, reason: str) -> HTTPError:
    body = json.dumps({"error": {"errors": [{"reason": reason}]}}).encode()
    return HTTPError("https://example.test", code, "error", {}, io.BytesIO(body))


class Response:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.body


class YouTubeClientTests(unittest.TestCase):
    def test_retries_transient_network_error(self):
        calls = []

        def opener(url, timeout):
            calls.append(url)
            if len(calls) == 1:
                raise URLError("temporary")
            return Response(b'{"items": []}')

        client = YouTubeClient(api_key="key", retry_attempts=1, retry_backoff_seconds=0, opener=opener)
        self.assertEqual(client.get("search", {}), {"items": []})
        self.assertEqual(len(calls), 2)

    def test_classifies_quota_auth_and_rate_errors(self):
        cases = [
            (403, "quotaExceeded", ApiQuotaError),
            (403, "forbidden", ApiAuthError),
            (429, "rateLimitExceeded", ApiRateLimitError),
        ]
        for code, reason, error_type in cases:
            with self.subTest(code=code, reason=reason):
                client = YouTubeClient(
                    api_key="key",
                    retry_attempts=0,
                    opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(http_error(code, reason)),
                )
                with self.assertRaises(error_type):
                    client.get("search", {})

    def test_rejects_invalid_json(self):
        client = YouTubeClient(
            api_key="key",
            opener=lambda *_args, **_kwargs: Response(b"not json"),
        )
        with self.assertRaises(ApiResponseError):
            client.get("search", {})


if __name__ == "__main__":
    unittest.main()
