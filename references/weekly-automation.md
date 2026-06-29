# Weekly Automation

## Responsibility Boundary

An external scheduler invokes the weekly CLI or Python API. The Skill performs
search, ranking, HTML rendering, and report assembly. The calling agent sends
the pre-rendered `email_handoff.html_body` to `email_handoff.recipients` with
an available email tool.

The Skill deliberately does not contain SMTP credentials or provider-specific
delivery code.

## Default Schedule

- cron: `0 9 * * 1`
- timezone: `Asia/Tokyo`
- meaning: every Monday at 09:00 Japan time

Schedule metadata is descriptive. The scheduler remains responsible for
triggering the command at the configured time.

## Agent Handoff

When `email_handoff.action` is `send_email`:

1. Send the pre-rendered `email_handoff.html_body` as the email body.
2. Use `email_handoff.recipients` and `email_handoff.subject`.
3. Treat email delivery status separately from the search `status`.
4. Failed topics are already inlined in the HTML under "失败主题" — do not
   filter them out.

The HTML body is built by `tools/email_renderer.py` from
`tools/email_template.html`; it is designed to render correctly in Outlook
(Word engine) and Gmail without further transformation by the caller.

This handoff applies only to the weekly interface. Never infer an email action
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
