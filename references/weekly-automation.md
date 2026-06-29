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

## Email Client Compatibility Contract

The renderer must produce HTML that survives the following hostile environments
without layout breakage or stripped styles. `html_requirements` in
`tools/weekly_runner.py` encodes this contract; treat it as a hard specification,
not a wish list.

- **Layout primitive: `<table>` only.** No flexbox, no grid, no `<div>`-based
  positioning. `table` / `tr` / `td` / `th` are the only reliable primitives
  across all major email clients.
- **Inline styles only.** Do not rely on `<style>` blocks, `<link>`, or class
  selectors. Gmail strips `<head><style>` entirely; Outlook (desktop, Word
  engine) honors `<style>` inconsistently.
- **Explicit table dimensions.** Use `table-layout: fixed` plus explicit
  `width` and `height` attributes on `<table>`, `<td>`, and `<th>`. Do not
  depend on `min-width` or `max-width` to constrain columns — Outlook ignores
  them. The channel cell's ellipsis fallback is unreliable in Outlook; the
  renderer must additionally truncate `channel_title` to about 40 characters
  before rendering, otherwise Outlook will wrap or overflow.
- **Gmail compatibility.** Avoid background-image, `<script>`, CSS variables,
  `@media` queries, and shorthand properties. Set `width`, `height`, `color`,
  `background-color`, `padding`, `margin`, `font-family`, `font-size`,
  `line-height` as individual inline declarations.
- **Outlook (desktop) compatibility.** Wrap Outlook-only markup in
  `<!--[if mso]>...<![endif]-->` conditional comments. Provide
  `mso-padding-alt` and `mso-line-height-rule` on cells that need exact text
  spacing. Always set `width` and `height` on `<img>`; always use absolute
  URLs; always set `alt` text. Never use CSS `background-image` for content
  images.

This handoff applies only to the weekly interface. Never infer an email action
from `report_markdown` or `report_json` returned by the normal single-run
interface.

## Example Invocation

```shell
python -m tools.weekly_runner --config examples/weekly.yaml
```
