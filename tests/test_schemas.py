import json
import unittest
from pathlib import Path

try:
    from referencing import Registry, Resource
    _HAS_REFERENCING = True
except ImportError:
    _HAS_REFERENCING = False

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"


class SchemaTests(unittest.TestCase):
    def test_schema_files_are_valid_json(self):
        for path in SCHEMAS.glob("*.json"):
            with self.subTest(path=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(data["type"], "object")

    def test_input_and_result_instances_validate(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema dependency is not installed")

        input_schema = json.loads((SCHEMAS / "input.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(
            input_schema,
            format_checker=jsonschema.FormatChecker(),
        ).validate({
            "topic": "signal",
            "mode": "discovery",
            "published_after": "2026-06-01T00:00:00Z",
            "localized_queries": {
                "en": ["current affairs"],
                "ja": ["時事問題"],
            },
        })

        result_schema = json.loads((SCHEMAS / "result.schema.json").read_text(encoding="utf-8"))
        video_schema = json.loads((SCHEMAS / "video.schema.json").read_text(encoding="utf-8"))
        result_schema = dict(result_schema)
        result_schema["$id"] = (SCHEMAS / "result.schema.json").as_uri()
        if _HAS_REFERENCING:
            registry = Registry().with_resource(
                (SCHEMAS / "video.schema.json").as_uri(),
                Resource.from_contents(video_schema),
            )
            validator = jsonschema.Draft202012Validator(
                result_schema,
                registry=registry,
                format_checker=jsonschema.FormatChecker(),
            )
        else:
            resolver = jsonschema.RefResolver(
                base_uri=SCHEMAS.as_uri() + "/",
                referrer=result_schema,
                store={(SCHEMAS / "video.schema.json").as_uri(): video_schema},
            )
            validator = jsonschema.Draft202012Validator(
                result_schema,
                resolver=resolver,
                format_checker=jsonschema.FormatChecker(),
            )
        validator.validate({
            "run_id": "run",
            "skill": "hermes-youtube-signal-scout",
            "version": "0.4.2",
            "topic": "signal",
            "mode": "discovery",
            "created_at": "2026-06-10T00:00:00Z",
            "query_plan": {"search_queries": ["signal"], "channels": []},
            "quota_usage_estimate": {
                "search_list_calls": 1,
                "videos_list_calls": 1,
                "channels_list_calls": 0,
                "playlist_items_list_calls": 0,
                "estimated_quota_cost": 101,
            },
            "videos": [],
            "rejected": [],
            "run_stats": {
                "candidate_count": 0,
                "deduplicated_count": 0,
                "cache_hits": 0,
                "hydrated_count": 0,
                "accepted_count": 0,
                "rejected_count": 0,
                "target_results": 10,
                "target_met": False,
                "channel_duplicate_count": 0,
                "unique_channel_count": 0,
                "api_calls": {},
            },
            "warnings": [],
            "report_markdown": "# signal",
            "report_json": {
                "topic": "signal",
                "generated_at": "2026-06-10T00:00:00Z",
                "search_queries": ["signal"],
                "time_range": {"published_after": None, "published_before": None},
                "quota": {"estimated_cost": 101, "search_calls": 1, "video_calls": 1},
                "accepted_count": 0,
                "rejected_count": 0,
                "videos": [],
                "rejected": [],
                "run_stats": {},
                "warnings": [],
            },
        })

        weekly_input_schema = json.loads(
            (SCHEMAS / "weekly-input.schema.json").read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator(
            weekly_input_schema,
            format_checker=jsonschema.FormatChecker(),
        ).validate({
            "topics": ["global economy", {"topic": "AI chips"}],
            "email": {
                "account": "gmail",
                "sender": "signals@example.com",
                "recipients": ["analyst@example.com"],
            },
        })

    def test_weekly_input_requires_delivery_identity(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema dependency is not installed")

        schema = json.loads(
            (SCHEMAS / "weekly-input.schema.json").read_text(encoding="utf-8")
        )
        validator = jsonschema.Draft202012Validator(
            schema,
            format_checker=jsonschema.FormatChecker(),
        )
        cases = [
            {"topics": ["signal"]},
            {
                "topics": ["signal"],
                "email": {
                    "sender": "signals@example.com",
                    "recipients": ["a@example.com"],
                },
            },
            {
                "topics": ["signal"],
                "email": {
                    "account": "gmail",
                    "recipients": ["a@example.com"],
                },
            },
            {
                "topics": ["signal"],
                "email": {
                    "account": "gmail",
                    "sender": "signals@example.com",
                    "recipients": [],
                },
            },
        ]
        for instance in cases:
            with self.subTest(instance=instance):
                self.assertTrue(list(validator.iter_errors(instance)))

    def test_weekly_result_accepts_only_himalaya_handoff(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema dependency is not installed")

        schema = json.loads(
            (SCHEMAS / "weekly-result.schema.json").read_text(encoding="utf-8")
        )
        validator = jsonschema.Draft202012Validator(
            schema,
            format_checker=jsonschema.FormatChecker(),
        )
        result = {
            "generated_at": "2026-06-29T00:00:00Z",
            "schedule": {"cron": "0 9 * * 1", "timezone": "Asia/Tokyo"},
            "status": "success",
            "topic_count": 1,
            "successful_topic_count": 1,
            "failed_topic_count": 0,
            "runs": [],
            "failures": [],
            "email_handoff": {
                "action": "send_himalaya_template",
                "account": "gmail",
                "sender": "signals@example.com",
                "recipients": ["analyst@example.com"],
                "subject": "Weekly Signals",
                "mml_template": (
                    "From: signals@example.com\n\n"
                    "<#part type=text/html>\n<html></html>\n<#/part>\n"
                ),
                "retry_policy": "never_automatic",
            },
        }
        validator.validate(result)
        result["email_handoff"]["html_body"] = "<html></html>"
        self.assertTrue(list(validator.iter_errors(result)))


if __name__ == "__main__":
    unittest.main()
