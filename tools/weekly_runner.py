"""Weekly multi-topic runner and email handoff contract."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .errors import ConfigurationError, SignalScoutError
from .runner import run

ROOT = Path(__file__).resolve().parents[1]
WEEKLY_INPUT_SCHEMA_PATH = ROOT / "schemas" / "weekly-input.schema.json"


def load_weekly_config(path: str | Path) -> dict:
    config_path = Path(path)
    try:
        text = config_path.read_text(encoding="utf-8")
        data = json.loads(text) if config_path.suffix.casefold() == ".json" else yaml.safe_load(text)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Cannot load weekly config {config_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError("Weekly config file must contain an object/mapping")
    validate_weekly_config(data)
    return data


def validate_weekly_config(config: dict) -> None:
    try:
        import jsonschema
    except ImportError:
        _topic_configs(config)
        return
    schema = json.loads(WEEKLY_INPUT_SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(config, schema)
    except jsonschema.ValidationError as exc:
        path = ".".join(str(part) for part in exc.absolute_path)
        prefix = f"{path}: " if path else ""
        raise ConfigurationError(f"{prefix}{exc.message}") from exc


def _topic_configs(config: dict) -> list[dict]:
    topics = config.get("topics")
    if not isinstance(topics, list) or not topics:
        raise ConfigurationError("topics must be a non-empty array")
    common = deepcopy(config.get("defaults") or {})
    if not isinstance(common, dict):
        raise ConfigurationError("defaults must be an object/mapping")
    normalized = []
    for index, item in enumerate(topics):
        topic = {"topic": item} if isinstance(item, str) else deepcopy(item)
        if not isinstance(topic, dict):
            raise ConfigurationError(f"topics[{index}] must be a string or object")
        if not isinstance(topic.get("topic"), str) or not topic["topic"].strip():
            raise ConfigurationError(f"topics[{index}].topic must be a non-empty string")
        normalized.append({**deepcopy(common), **topic})
    return normalized


def _build_email_html(subject: str, runs: list[dict], failures: list[dict], generated_at: str) -> str:
    from .email_renderer import render_email_html

    return render_email_html(subject, runs, failures, generated_at)


def run_weekly(config: dict, client=None) -> dict:
    """Run multiple topic searches and return a scheduler/email handoff payload."""
    validate_weekly_config(config)
    topic_configs = _topic_configs(config)
    schedule = deepcopy(config.get("schedule") or {})
    if not isinstance(schedule, dict):
        raise ConfigurationError("schedule must be an object/mapping")
    schedule.setdefault("cron", "0 9 * * 1")
    schedule.setdefault("timezone", "Asia/Tokyo")
    email = deepcopy(config.get("email") or {})
    if not isinstance(email, dict):
        raise ConfigurationError("email must be an object/mapping")
    recipients = email.get("recipients") or []
    if not isinstance(recipients, list) or any(not isinstance(value, str) for value in recipients):
        raise ConfigurationError("email.recipients must be an array of strings")
    continue_on_error = bool(config.get("continue_on_error", True))
    runs: list[dict] = []
    failures: list[dict] = []
    for topic_config in topic_configs:
        try:
            run_result = run(topic_config, client=client)
            run_result["_email_topic_config"] = deepcopy(topic_config)
            runs.append(run_result)
        except (SignalScoutError, OSError, ValueError) as exc:
            failure = {
                "topic": topic_config["topic"],
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
            failures.append(failure)
            if not continue_on_error:
                raise
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    subject = str(email.get("subject") or f"YouTube Weekly Signal Report - {generated_at[:10]}")
    sections = [
        {
            "topic": result["topic"],
            "accepted_count": len(result["videos"]),
            "report_markdown": result["report_markdown"],
            "videos": result["report_json"]["videos"],
        }
        for result in runs
    ]
    return {
        "generated_at": generated_at,
        "schedule": schedule,
        "status": "success" if not failures else ("partial" if runs else "failed"),
        "topic_count": len(topic_configs),
        "successful_topic_count": len(runs),
        "failed_topic_count": len(failures),
        "runs": runs,
        "failures": failures,
        "email_handoff": {
            "action": "send_email",
            "recipients": recipients,
            "subject": subject,
            "html_body": _build_email_html(subject, runs, failures, generated_at),
            "sections": sections,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a weekly multi-topic YouTube signal report")
    parser.add_argument("--config", required=True, help="Path to a weekly YAML or JSON config")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_weekly(load_weekly_config(args.config))
    except (SignalScoutError, OSError, ValueError) as exc:
        print(
            json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "failed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
