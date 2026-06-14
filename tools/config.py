"""Configuration loading, defaults, and schema validation."""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from .errors import ConfigurationError

ROOT = Path(__file__).resolve().parents[1]
INPUT_SCHEMA_PATH = ROOT / "schemas" / "input.schema.json"
SKILL_MANIFEST_PATH = ROOT / "skill.yaml"
_RFC3339_ZONE_RE = re.compile(r"(?:Z|[+-]\d{2}:\d{2})$")


def load_skill_manifest() -> dict:
    try:
        data = yaml.safe_load(SKILL_MANIFEST_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Cannot read skill manifest: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError("skill.yaml must contain a mapping")
    return data


def skill_version() -> str:
    return str(load_skill_manifest().get("version") or "0.0.0")


def default_cache_path() -> str:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return str(base / "hermes-youtube-signal-scout" / "cache.sqlite3")


def _validate_rfc3339(value: object, field: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not _RFC3339_ZONE_RE.search(value):
        raise ConfigurationError(f"{field} must be an RFC 3339 timestamp with a timezone")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConfigurationError(f"{field} must be a valid RFC 3339 timestamp") from exc


def _manual_validate(config: dict) -> None:
    topic = config.get("topic")
    if not isinstance(topic, str) or not topic.strip():
        raise ConfigurationError("topic must be a non-empty string")
    if config.get("mode") not in {"discovery", "channel_watch", "hybrid"}:
        raise ConfigurationError("mode must be discovery, channel_watch, or hybrid")
    for field in ("published_after", "published_before"):
        _validate_rfc3339(config.get(field), field)
    after = config.get("published_after")
    before = config.get("published_before")
    if after and before:
        start = datetime.fromisoformat(after.replace("Z", "+00:00"))
        end = datetime.fromisoformat(before.replace("Z", "+00:00"))
        if start > end:
            raise ConfigurationError("published_after must not be later than published_before")
    if config["mode"] in {"channel_watch", "hybrid"} and not (
        config.get("channel_ids") or config.get("channel_urls")
    ):
        raise ConfigurationError(f"{config['mode']} mode requires channel_ids or channel_urls")
    if config["mode"] in {"discovery", "hybrid"} and not (
        config.get("search_query") or config.get("include_keywords") or topic.strip()
    ):
        raise ConfigurationError(f"{config['mode']} mode requires a topic or search terms")
    localized_queries = config.get("localized_queries") or {}
    if not isinstance(localized_queries, dict):
        raise ConfigurationError("localized_queries must be an object/mapping")
    for language, terms in localized_queries.items():
        if language not in {"en", "ja", "zh-Hant", "ko", "de", "fr"}:
            raise ConfigurationError(f"unsupported localized query language: {language}")
        if not isinstance(terms, list) or not terms or any(
            not isinstance(term, str) or not term.strip() for term in terms
        ):
            raise ConfigurationError(
                f"localized_queries.{language} must be a non-empty string array"
            )
    max_per_channel = config.get("max_videos_per_channel")
    if (
        not isinstance(max_per_channel, int)
        or isinstance(max_per_channel, bool)
        or max_per_channel < 1
    ):
        raise ConfigurationError("max_videos_per_channel must be a positive integer")
    prior_views = config.get("engagement_prior_views")
    if (
        not isinstance(prior_views, int)
        or isinstance(prior_views, bool)
        or prior_views < 1
    ):
        raise ConfigurationError("engagement_prior_views must be a positive integer")
    channel_scores = config.get("channel_quality_scores") or {}
    if not isinstance(channel_scores, dict) or any(
        not isinstance(score, (int, float))
        or isinstance(score, bool)
        or score < 0
        or score > 1
        for score in channel_scores.values()
    ):
        raise ConfigurationError(
            "channel_quality_scores values must be numbers between 0 and 1"
        )


def validate_config(config: dict) -> None:
    try:
        import jsonschema
    except ImportError:
        _manual_validate(config)
        return
    schema = json.loads(INPUT_SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(config, schema)
    except jsonschema.ValidationError as exc:
        path = ".".join(str(part) for part in exc.absolute_path)
        prefix = f"{path}: " if path else ""
        raise ConfigurationError(f"{prefix}{exc.message}") from exc
    _manual_validate(config)


def apply_defaults(config: dict) -> dict:
    manifest = load_skill_manifest()
    merged = deepcopy(manifest.get("defaults") or {})
    merged.update(deepcopy(config))
    if merged.get("cache_enabled", True) and not merged.get("cache_path"):
        merged["cache_path"] = default_cache_path()
    merged.setdefault("retry_attempts", 2)
    merged.setdefault("retry_backoff_seconds", 1.0)
    merged.setdefault("shorts_max_duration_seconds", 60)
    merged.setdefault("reject_possible_ads", True)
    merged.setdefault("reject_entertainment", True)
    merged.setdefault("trusted_channel_ids", [])
    lookback_days = merged.get("lookback_days")
    if not merged.get("published_after") and lookback_days:
        merged["published_after"] = (
            datetime.now(timezone.utc) - timedelta(days=int(lookback_days))
        ).isoformat().replace("+00:00", "Z")
    if not merged.get("include_keywords") and not merged.get("target_tags"):
        merged["include_keywords"] = [str(merged.get("topic") or "").strip()]
    localized = merged.get("localized_queries") or {}
    localized_terms = [
        term
        for terms in localized.values()
        if isinstance(terms, list)
        for term in terms
    ] if isinstance(localized, dict) else []
    merged["include_keywords"] = list(dict.fromkeys([
        *(merged.get("include_keywords") or []),
        *localized_terms,
    ]))
    merged["version"] = str(manifest.get("version") or "0.0.0")
    validate_config(merged)
    return merged


def load_config(path: str | Path) -> dict:
    config_path = Path(path)
    try:
        text = config_path.read_text(encoding="utf-8")
        if config_path.suffix.casefold() == ".json":
            data = json.loads(text)
        else:
            data = yaml.safe_load(text)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Cannot load config {config_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError("Config file must contain an object/mapping")
    return apply_defaults(data)
