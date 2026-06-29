# Himalaya MML Email Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the generic weekly HTML handoff with a complete Himalaya MML template carrying explicit account, sender, recipients, and no-automatic-retry semantics.

**Architecture:** `tools.weekly_runner` remains responsible for weekly orchestration and HTML rendering, then wraps that HTML in a complete MML message. JSON schemas define the breaking contract, while the external agent pipes `mml_template` to the selected Himalaya account and owns delivery status.

**Tech Stack:** Python 3, `unittest`, JSON Schema Draft 2020-12, YAML, Himalaya MML.

---

## File Structure

- Modify `tools/weekly_runner.py`: validate delivery identity and assemble the MML handoff.
- Modify `schemas/weekly-input.schema.json`: require `email.account`, `email.sender`, and non-empty recipients.
- Modify `schemas/weekly-result.schema.json`: define only the Himalaya handoff fields.
- Modify `tests/test_weekly_runner.py`: regression tests for runtime validation and MML output.
- Modify `tests/test_schemas.py`: schema examples and rejection tests for the new contract.
- Modify `tests/test_skill_contract.py`: enforce Himalaya and retry instructions.
- Modify `SKILL.md`, `references/weekly-automation.md`, `agents/openai.yaml`: document exact caller behavior.
- Modify `examples/weekly.yaml`: provide explicit Himalaya account and sender.
- Modify `references/input-output-schema.md`: synchronize the public weekly contract.
- Modify `skill.yaml`: bump the breaking interface version to `0.5.0`.

### Task 1: Runtime MML contract

**Files:**
- Modify: `tests/test_weekly_runner.py`
- Modify: `tools/weekly_runner.py`
- Modify: `schemas/weekly-input.schema.json`
- Modify: `schemas/weekly-result.schema.json`

- [ ] **Step 1: Replace the existing handoff assertions with a failing MML contract test**

Update every valid weekly fixture to include:

```python
"email": {
    "account": "gmail",
    "sender": "signals@example.com",
    "recipients": ["analyst@example.com"],
    "subject": "Weekly Signals",
},
```

Change `test_runs_multiple_topics_and_builds_html_email_handoff` to
`test_runs_multiple_topics_and_builds_himalaya_mml_handoff` and assert:

```python
handoff = result["email_handoff"]
self.assertEqual(handoff["action"], "send_himalaya_template")
self.assertEqual(handoff["account"], "gmail")
self.assertEqual(handoff["sender"], "signals@example.com")
self.assertEqual(handoff["recipients"], ["analyst@example.com"])
self.assertEqual(handoff["subject"], "Weekly Signals")
self.assertEqual(handoff["retry_policy"], "never_automatic")
self.assertIn("From: signals@example.com\n", handoff["mml_template"])
self.assertIn("To: analyst@example.com\n", handoff["mml_template"])
self.assertIn("Subject: Weekly Signals\n", handoff["mml_template"])
self.assertIn("\n<#part type=text/html>\n<html>", handoff["mml_template"])
self.assertTrue(handoff["mml_template"].endswith("\n<#/part>\n"))
for removed in ("html_body", "content_type", "sections"):
    self.assertNotIn(removed, handoff)
```

- [ ] **Step 2: Add failing validation and multiple-recipient tests**

Add a shared minimal config helper and these behaviors:

```python
def weekly_config(email):
    return {
        "defaults": {
            "cache_enabled": False,
            "topic_score_threshold": 0,
            "region_code": "JP",
            "region_priority_tiers": [],
            "target_results": 1,
            "max_results": 1,
        },
        "topics": ["signal"],
        "email": email,
    }


def test_requires_himalaya_account_sender_and_recipient(self):
    cases = [
        {},
        {"sender": "signals@example.com", "recipients": ["a@example.com"]},
        {"account": "gmail", "recipients": ["a@example.com"]},
        {"account": "gmail", "sender": "signals@example.com", "recipients": []},
    ]
    for email in cases:
        with self.subTest(email=email):
            with self.assertRaises(ConfigurationError):
                run_weekly(weekly_config(email), client=FakeYouTubeClient())


def test_rejects_header_newlines(self):
    email = {
        "account": "gmail\nother",
        "sender": "signals@example.com",
        "recipients": ["a@example.com"],
        "subject": "Weekly\nBcc: attacker@example.com",
    }
    with self.assertRaises(ConfigurationError):
        run_weekly(weekly_config(email), client=FakeYouTubeClient())


def test_rejects_invalid_email_addresses(self):
    for sender, recipients in [
        ("not-an-email", ["a@example.com"]),
        ("signals@example.com", ["not-an-email"]),
    ]:
        with self.subTest(sender=sender, recipients=recipients):
            email = {"account": "gmail", "sender": sender, "recipients": recipients}
            with self.assertRaises(ConfigurationError):
                run_weekly(weekly_config(email), client=FakeYouTubeClient())


def test_mml_joins_multiple_recipients(self):
    email = {
        "account": "gmail",
        "sender": "signals@example.com",
        "recipients": ["a@example.com", "b@example.com"],
    }
    result = run_weekly(weekly_config(email), client=FakeYouTubeClient())
    self.assertIn("To: a@example.com, b@example.com\n", result["email_handoff"]["mml_template"])
```

- [ ] **Step 3: Run the runtime tests and verify RED**

Run:

```powershell
python -m unittest tests.test_weekly_runner -v
```

Expected: failures because the handoff still exposes `send_email`,
`html_body`, `content_type`, and `sections`, and missing delivery identity is
still accepted.

- [ ] **Step 4: Implement minimal delivery validation and MML assembly**

First make the schemas understand the new property names so the runtime tests
can reach `run_weekly()`. At this stage, add `account` and `sender` properties
to the existing input `email` object, and replace the result handoff property
names with `account`, `sender`, `mml_template`, and `retry_policy`. Do not yet
add `required`, `minItems`, or `additionalProperties: false`; Task 2 adds those
constraints after their rejection tests fail.

Use these transitional property definitions:

```json
"account": {"type": "string", "minLength": 1},
"sender": {"type": "string", "format": "email"}
```

and this transitional result handoff:

```json
"email_handoff": {
  "type": "object",
  "required": [
    "action", "account", "sender", "recipients", "subject",
    "mml_template", "retry_policy"
  ],
  "properties": {
    "action": {"const": "send_himalaya_template"},
    "account": {"type": "string"},
    "sender": {"type": "string"},
    "recipients": {"type": "array", "items": {"type": "string"}},
    "subject": {"type": "string"},
    "mml_template": {"type": "string"},
    "retry_policy": {"const": "never_automatic"}
  }
}
```

Change the existing schema validation call so JSON Schema email formats are
enforced at runtime:

```python
jsonschema.validate(
    config,
    schema,
    format_checker=jsonschema.FormatChecker(),
)
```

Add focused helpers in `tools/weekly_runner.py`:

```python
def _require_header_value(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"email.{name} must be a non-empty string")
    if "\r" in value or "\n" in value:
        raise ConfigurationError(f"email.{name} must not contain newlines")
    return value.strip()


def _email_config(config: dict) -> tuple[str, str, list[str], str | None]:
    email = config.get("email")
    if not isinstance(email, dict):
        raise ConfigurationError("email must be an object/mapping")
    account = _require_header_value("account", email.get("account"))
    sender = _require_header_value("sender", email.get("sender"))
    recipients = email.get("recipients")
    if not isinstance(recipients, list) or not recipients:
        raise ConfigurationError("email.recipients must be a non-empty array of strings")
    normalized_recipients = [
        _require_header_value(f"recipients[{index}]", value)
        for index, value in enumerate(recipients)
    ]
    subject = email.get("subject")
    if subject is not None:
        subject = _require_header_value("subject", subject)
    return account, sender, normalized_recipients, subject


def _build_mml_template(
    sender: str,
    recipients: list[str],
    subject: str,
    html_body: str,
) -> str:
    return (
        f"From: {sender}\n"
        f"To: {', '.join(recipients)}\n"
        f"Subject: {subject}\n\n"
        "<#part type=text/html>\n"
        f"{html_body}\n"
        "<#/part>\n"
    )
```

Call `_email_config(config)` before topic execution. Render HTML once, wrap it
with `_build_mml_template`, and return only:

```python
"email_handoff": {
    "action": "send_himalaya_template",
    "account": account,
    "sender": sender,
    "recipients": recipients,
    "subject": subject,
    "mml_template": _build_mml_template(sender, recipients, subject, html_body),
    "retry_policy": "never_automatic",
},
```

- [ ] **Step 5: Run the runtime tests and verify GREEN**

Run:

```powershell
python -m unittest tests.test_weekly_runner tests.test_email_renderer -v
```

Expected: all weekly and renderer tests pass.

- [ ] **Step 6: Commit the runtime behavior**

```powershell
git add tools/weekly_runner.py tests/test_weekly_runner.py schemas/weekly-input.schema.json schemas/weekly-result.schema.json
git commit -m "feat: emit Himalaya MML email handoff"
```

### Task 2: Weekly JSON schemas

**Files:**
- Modify: `tests/test_schemas.py`
- Modify: `schemas/weekly-input.schema.json`
- Modify: `schemas/weekly-result.schema.json`

- [ ] **Step 1: Write failing schema tests**

Update the valid weekly input example to:

```python
{
    "topics": ["global economy", {"topic": "AI chips"}],
    "email": {
        "account": "gmail",
        "sender": "signals@example.com",
        "recipients": ["analyst@example.com"],
    },
}
```

Add these focused tests:

```python
def test_weekly_input_requires_delivery_identity(self):
    import jsonschema

    schema = json.loads((SCHEMAS / "weekly-input.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    )
    cases = [
        {"topics": ["signal"]},
        {"topics": ["signal"], "email": {"sender": "signals@example.com", "recipients": ["a@example.com"]}},
        {"topics": ["signal"], "email": {"account": "gmail", "recipients": ["a@example.com"]}},
        {"topics": ["signal"], "email": {"account": "gmail", "sender": "signals@example.com", "recipients": []}},
    ]
    for instance in cases:
        with self.subTest(instance=instance):
            self.assertTrue(list(validator.iter_errors(instance)))


def test_weekly_result_accepts_only_himalaya_handoff(self):
    import jsonschema

    schema = json.loads((SCHEMAS / "weekly-result.schema.json").read_text(encoding="utf-8"))
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
            "mml_template": "From: signals@example.com\n\n<#part type=text/html>\n<html></html>\n<#/part>\n",
            "retry_policy": "never_automatic",
        },
    }
    validator.validate(result)
    result["email_handoff"]["html_body"] = "<html></html>"
    self.assertTrue(list(validator.iter_errors(result)))
```

- [ ] **Step 2: Run schema tests and verify RED**

```powershell
python -m unittest tests.test_schemas -v
```

Expected: failures because the transitional schemas from Task 1 still allow
missing delivery identity and legacy handoff properties.

- [ ] **Step 3: Update the weekly input schema**

Set the top-level requirement to:

```json
"required": ["topics", "email"]
```

Set the email contract to:

```json
"email": {
  "type": "object",
  "required": ["account", "sender", "recipients"],
  "additionalProperties": false,
  "properties": {
    "account": {"type": "string", "minLength": 1, "pattern": "^[^\\r\\n]+$"},
    "sender": {"type": "string", "format": "email", "pattern": "^[^\\r\\n]+$"},
    "recipients": {
      "type": "array",
      "minItems": 1,
      "items": {"type": "string", "format": "email", "pattern": "^[^\\r\\n]+$"}
    },
    "subject": {"type": "string", "minLength": 1, "pattern": "^[^\\r\\n]+$"}
  }
}
```

- [ ] **Step 4: Replace the weekly result handoff schema**

Use `additionalProperties: false` and require exactly the new contract:

```json
"email_handoff": {
  "type": "object",
  "additionalProperties": false,
  "required": [
    "action", "account", "sender", "recipients", "subject",
    "mml_template", "retry_policy"
  ],
  "properties": {
    "action": {"const": "send_himalaya_template"},
    "account": {"type": "string", "minLength": 1},
    "sender": {"type": "string", "format": "email"},
    "recipients": {"type": "array", "minItems": 1, "items": {"type": "string", "format": "email"}},
    "subject": {"type": "string", "minLength": 1},
    "mml_template": {"type": "string", "minLength": 1},
    "retry_policy": {"const": "never_automatic"}
  }
}
```

- [ ] **Step 5: Run schema and runtime tests**

```powershell
python -m unittest tests.test_schemas tests.test_weekly_runner -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit the schema contract**

```powershell
git add schemas/weekly-input.schema.json schemas/weekly-result.schema.json tests/test_schemas.py
git commit -m "feat: define Himalaya weekly email schema"
```

### Task 3: Agent instructions and examples

**Files:**
- Modify: `tests/test_skill_contract.py`
- Modify: `SKILL.md`
- Modify: `references/weekly-automation.md`
- Modify: `references/input-output-schema.md`
- Modify: `agents/openai.yaml`
- Modify: `examples/weekly.yaml`
- Modify: `skill.yaml`

- [ ] **Step 1: Replace the contract test and verify RED**

Change the test to require these strings in both `SKILL.md` and
`agents/openai.yaml`:

```python
self.assertIn("email_handoff.mml_template", text)
self.assertIn("himalaya", text.casefold())
self.assertIn("never_automatic", text)
self.assertNotIn("email_handoff.html_body", text)
self.assertNotIn("text/html through an explicit HTML-capable email field", text)
```

Also assert `references/weekly-automation.md` contains
`[Gmail]/Sent Mail`, `must not automatically retry`, and the exact command
shape `himalaya --account <account> template send`.

Run:

```powershell
python -m unittest tests.test_skill_contract -v
```

Expected: FAIL because documentation still describes the HTML-capable tool
contract.

- [ ] **Step 2: Update the Skill and agent prompt**

Replace generic HTML delivery guidance with these rules:

```text
Only after an explicit weekly run, pass email_handoff.mml_template unchanged
to `himalaya --account <account> template send` on standard input, using
email_handoff.account. Do not render, escape, or wrap the template again.
The retry policy is never_automatic: on any non-zero Himalaya exit, report an
indeterminate delivery failure and do not retry without explicit user approval
after checking Sent mail.
```

Keep the normal `run()` prohibition unchanged.

- [ ] **Step 3: Update reference documentation and example**

Document the new fields, MML structure, sender/account responsibility, Gmail
Sent alias, and indeterminate failure semantics. Change `examples/weekly.yaml`
to:

```yaml
email:
  account: gmail
  sender: signals@example.com
  recipients:
    - analyst@example.com
  subject: YouTube 每周信号报告
```

Update `references/input-output-schema.md` so it no longer claims agent-side
HTML rendering. Set `skill.yaml` version to `0.5.0` because this removes public
handoff fields.

- [ ] **Step 4: Run contract tests and Skill validation**

```powershell
python -m unittest tests.test_skill_contract tests.test_schemas tests.test_weekly_runner -v
python C:\Users\mzyas\.codex\skills\.system\skill-creator\scripts\quick_validate.py .
```

Expected: all tests pass and the validator reports a valid Skill.

- [ ] **Step 5: Commit documentation and metadata**

```powershell
git add SKILL.md agents/openai.yaml examples/weekly.yaml references/weekly-automation.md references/input-output-schema.md skill.yaml tests/test_skill_contract.py
git commit -m "docs: define Himalaya MML delivery workflow"
```

### Task 4: Final verification

**Files:**
- Verify only; no planned modifications.

- [ ] **Step 1: Run the complete test suite**

```powershell
python -m unittest discover -s tests -p 'test_*.py'
```

Expected: all tests pass with zero failures and errors.

- [ ] **Step 2: Run Skill validation again**

```powershell
python C:\Users\mzyas\.codex\skills\.system\skill-creator\scripts\quick_validate.py .
```

Expected: validation succeeds.

- [ ] **Step 3: Inspect the final patch and repository state**

```powershell
git diff HEAD~3 --check
git status --short
```

Expected: no whitespace errors; the worktree is clean after the planned
commits.
