# Weekly Automation

## Responsibility Boundary

An external scheduler invokes the weekly CLI or Python API. The Skill performs
search, ranking, and report assembly. The calling agent converts
`email_handoff.markdown_body` to HTML and sends it with an available email tool.

The Skill deliberately does not contain SMTP credentials or provider-specific
delivery code.

## Default Schedule

- cron: `0 9 * * 1`
- timezone: `Asia/Tokyo`
- meaning: every Monday at 09:00 Japan time

Schedule metadata is descriptive. The scheduler remains responsible for
triggering the command at the configured time.

## Agent Handoff

When `email_handoff.action` is `render_html_and_send_email`:

1. Render one HTML section per topic.
2. Preserve all video information from each section.
3. Send to `email_handoff.recipients` with `email_handoff.subject`.
4. Include failed topics in the email instead of hiding them.
5. Treat email delivery status separately from the search `status`.
6. Apply `style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"`
   to the channel cell of every result row as a visual safety net against
   unusually long or unsanitized `channel_title` values. The Skill sanitizes
   `channel_title` at the hydration boundary, but the renderer must still
   guard against long content breaking the table layout.

This handoff applies only to the weekly interface. Never infer an email action
from `report_markdown` or `report_json` returned by the normal single-run
interface.

## Example Invocation

```shell
python -m tools.weekly_runner --config examples/weekly.yaml
```
