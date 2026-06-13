"""Stable error types exposed by the signal scout runtime."""


class SignalScoutError(RuntimeError):
    """Base error for expected runtime failures."""


class ConfigurationError(SignalScoutError):
    """Raised when user configuration is invalid."""


class ApiError(SignalScoutError):
    """Raised when the YouTube API request or response is invalid."""


class ApiAuthError(ApiError):
    """Raised for invalid credentials or forbidden API access."""


class ApiQuotaError(ApiError):
    """Raised when the YouTube API quota is exhausted."""


class ApiRateLimitError(ApiError):
    """Raised when the YouTube API rate-limits a request."""


class ApiResponseError(ApiError):
    """Raised when an API response does not match the expected shape."""
