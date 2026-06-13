"""Minimal YouTube Data API v3 client using the Python standard library."""

from __future__ import annotations

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from .errors import (
    ApiAuthError,
    ApiError,
    ApiQuotaError,
    ApiRateLimitError,
    ApiResponseError,
)


YouTubeClientError = ApiError


class YouTubeClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://www.googleapis.com/youtube/v3",
        retry_attempts: int = 2,
        retry_backoff_seconds: float = 1.0,
        timeout_seconds: float = 30.0,
        opener=urlopen,
        sleeper=time.sleep,
    ):
        self.api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
        if not self.api_key:
            raise YouTubeClientError("YOUTUBE_API_KEY is required for live YouTube API calls")
        self.base_url = base_url.rstrip("/")
        self.retry_attempts = max(0, int(retry_attempts))
        self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))
        self.timeout_seconds = max(0.1, float(timeout_seconds))
        self._opener = opener
        self._sleeper = sleeper

    @staticmethod
    def _http_error(exc: HTTPError, body: str) -> ApiError:
        reason = ""
        try:
            payload = json.loads(body)
            errors = (payload.get("error") or {}).get("errors") or []
            reason = str((errors[0] if errors else {}).get("reason") or "")
        except (TypeError, ValueError):
            pass
        message = f"YouTube API HTTP {exc.code}: {body}"
        if reason in {"quotaExceeded", "dailyLimitExceeded"}:
            return ApiQuotaError(message)
        if exc.code == 429 or reason in {"rateLimitExceeded", "userRateLimitExceeded"}:
            return ApiRateLimitError(message)
        if exc.code in {401, 403}:
            return ApiAuthError(message)
        return ApiError(message)

    def get(self, endpoint: str, params: dict) -> dict:
        query = dict(params)
        query["key"] = self.api_key
        url = f"{self.base_url}/{endpoint.lstrip('/')}?{urlencode(query, doseq=True)}"
        for attempt in range(self.retry_attempts + 1):
            try:
                with self._opener(url, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ApiResponseError("YouTube API response must be a JSON object")
                return payload
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                error = self._http_error(exc, body)
                retryable = exc.code >= 500 or isinstance(error, ApiRateLimitError)
                if not retryable or attempt >= self.retry_attempts:
                    raise error from exc
            except (URLError, TimeoutError) as exc:
                if attempt >= self.retry_attempts:
                    raise ApiError(f"YouTube API request failed: {exc}") from exc
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ApiResponseError(f"YouTube API returned invalid JSON: {exc}") from exc
            self._sleeper(self.retry_backoff_seconds * (2**attempt))
        raise ApiError("YouTube API request failed")
