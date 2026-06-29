# Himalaya MML Email Handoff Design

## Goal

Replace the generic HTML email handoff with a Himalaya-specific MML template
that the calling agent can pass directly to `himalaya template send`. Make the
selected Himalaya account and sender explicit, and prohibit blind automatic
retries after a send failure.

## Scope

The Skill continues to run weekly topic searches and render the HTML report.
It assembles the final MML message but does not execute Himalaya, manage email
credentials, or schedule itself.

This is an approved breaking contract change. The legacy `html_body`,
`content_type`, and `sections` handoff fields will be removed.

## Input Contract

The weekly `email` object requires:

- `account`: non-empty Himalaya account name.
- `sender`: valid sender email address used in the MML `From` header.
- `recipients`: non-empty array of valid recipient email addresses.
- `subject`: optional non-empty subject; the existing generated default remains.

Header values must not contain carriage returns or line feeds. Invalid or
missing delivery fields raise `ConfigurationError` before topic searches run.

## Output Contract

`run_weekly()` returns this delivery handoff:

```json
{
  "action": "send_himalaya_template",
  "account": "gmail",
  "sender": "sender@example.com",
  "recipients": ["recipient@example.com"],
  "subject": "YouTube Weekly Signal Report",
  "mml_template": "From: ...",
  "retry_policy": "never_automatic"
}
```

The removed fields must not appear in the result or weekly result schema.

## MML Assembly

The runtime constructs a complete MML template:

```text
From: sender@example.com
To: recipient@example.com
Subject: YouTube Weekly Signal Report

<#part type=text/html>
<html>...</html>
<#/part>
```

Multiple recipients are joined in the `To` header using comma-space. The HTML
continues to come from `tools/email_renderer.py`; callers must not transform or
escape it again.

The caller sends the template through the selected account using the equivalent
of:

```text
himalaya --account <account> template send
```

with `mml_template` supplied on standard input.

## Retry and Error Semantics

Search status and delivery status remain separate. A non-zero Himalaya exit
code is an indeterminate delivery result: SMTP submission may have succeeded
before saving the Sent copy failed. The calling agent must report the failure
and must not automatically invoke the send command again. Any retry requires
explicit user authorization after checking the Sent mailbox.

For Gmail accounts, the Himalaya Sent alias must resolve to
`[Gmail]/Sent Mail`; configuration remains the caller's responsibility.

## Documentation Changes

Update `SKILL.md`, `agents/openai.yaml`, and
`references/weekly-automation.md` to describe the exact Himalaya command,
MML input, account selection, and no-automatic-retry rule. Update the weekly
example with explicit `account` and `sender` fields.

## Tests

Add or update tests to verify:

- account, sender, and at least one recipient are required;
- the handoff contains the selected account and sender;
- `mml_template` contains valid headers and an HTML MML part;
- multiple recipients are rendered correctly;
- `retry_policy` is `never_automatic`;
- legacy HTML handoff fields are absent;
- the input and output schemas enforce the new contract;
- Skill and agent instructions name Himalaya MML and prohibit automatic retry.

Run focused weekly, schema, renderer, and contract tests before the complete
test suite and Skill validator.
