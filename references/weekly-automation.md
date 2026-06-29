# Weekly Automation

## Responsibility Boundary

An external scheduler invokes the weekly CLI or Python API. The Skill performs
search, ranking, HTML rendering, MML assembly, and report assembly. The calling
agent sends the complete `email_handoff.mml_template` through Himalaya using
the selected `email_handoff.account`.

The Skill deliberately does not contain SMTP credentials or provider-specific
delivery code.

## Default Schedule

- cron: `0 9 * * 1`
- timezone: `Asia/Tokyo`
- meaning: every Monday at 09:00 Japan time

Schedule metadata is descriptive. The scheduler remains responsible for
triggering the command at the configured time.

## Agent Handoff

When `email_handoff.action` is `send_himalaya_template`:

1. Pass `email_handoff.mml_template` unchanged on standard input to
   `himalaya --account <account> template send`, replacing `<account>` with
   `email_handoff.account`.
2. Do not render, escape, or add MIME headers. The template already contains
   `From`, `To`, `Subject`, and the `<#part type=text/html>` MML part.
3. Treat email delivery status separately from the search `status`.
4. Failed topics are already inlined in the HTML under "失败主题" — do not
   filter them out.
5. Honor `email_handoff.retry_policy == "never_automatic"`. On any non-zero
   Himalaya exit, the caller must not automatically retry. Report delivery as
   indeterminate, check the Sent mailbox, and require explicit user approval
   before another send attempt.

The HTML body is built by `tools/email_renderer.py` from
`tools/email_template.html`; it is designed to render correctly in Outlook
(Word engine) and Gmail. `tools/weekly_runner.py` wraps it in Himalaya MML.

The weekly email config requires a Himalaya `account`, a matching `sender`, and
at least one recipient. For Gmail, configure the Sent alias as:

```toml
folder.aliases.sent = "[Gmail]/Sent Mail"
```

Without that alias, SMTP delivery can succeed before Himalaya fails to save the
Sent copy. Retrying from the non-zero exit code can therefore duplicate mail.

This handoff applies only to the weekly interface. Never infer a Himalaya action
from `report_markdown` or `report_json` returned by the normal single-run
interface.

## Email Client Compatibility Contract

`tools/email_renderer.py` produces HTML that survives the following hostile
environments without layout breakage or stripped styles. Treat the structure
as a hard contract when editing the template or renderer.

- **Layout primitive: `<table>` only.** No flexbox, no grid, no `<div>`-based
  positioning. `table` / `tr` / `td` / `th` are the only reliable primitives
  across all major email clients.
- **Inline styles only.** No `<style>` blocks, no `<link>`, no class selectors.
  Gmail strips `<head><style>` entirely; Outlook (desktop, Word engine)
  honors `<style>` inconsistently.
- **Long-content defense.** Video titles are truncated to 80 characters and
  channel titles to 60 characters before render
  (`sanitize_title_for_email` / `sanitize_channel_title_for_email` in
  `tools/text_sanitize.py`). Cells use
  `max-width:<N>px;word-break:break-word;white-space:normal;` so long content
  wraps inside the column instead of inflating row height. Do not switch to
  `text-overflow:ellipsis` — Outlook's Word engine ignores it.
- **Failure topics** get their own `<table>` block under a red "失败主题"
  heading, never folded into the result table.
- **Images and links** always use absolute URLs. `<a>` tags carry inline
  `color` and `text-decoration:none` so Gmail's link recoloring does not
  override them.

## Example Invocation

```shell
python -m tools.weekly_runner --config examples/weekly.yaml
```
