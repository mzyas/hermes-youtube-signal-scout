"""Minimal YouTube Data API v3 client using the Python standard library."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


class YouTubeClientError(RuntimeError):
    pass


class YouTubeClient:
    def __init__(self, api_key: str | None = None, base_url: str = "https://www.googleapis.com/youtube/v3"):
        self.api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
        if not self.api_key:
            raise YouTubeClientError("YOUTUBE_API_KEY is required for live YouTube API calls")
        self.base_url = base_url.rstrip("/")

    def get(self, endpoint: str, params: dict) -> dict:
        query = dict(params)
        query["key"] = self.api_key
        url = f"{self.base_url}/{endpoint.lstrip('/')}?{urlencode(query, doseq=True)}"
        try:
            with urlopen(url, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise YouTubeClientError(f"YouTube API HTTP {exc.code}: {body}") from exc
        except URLError as exc:
            raise YouTubeClientError(f"YouTube API request failed: {exc}") from exc