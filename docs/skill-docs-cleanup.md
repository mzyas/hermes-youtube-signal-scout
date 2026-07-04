# Skill documentation cleanup — verified scope and outcome

## Summary

Document the `query_plan.order` recall behavior that the code already
supports. Documentation only — no code changes.

An earlier draft of this issue also proposed deduplicating SKILL.md,
restoring "lost" sections in weekly-automation.md, and adding
session-specific delivery workflows. Those items were verified against the
repository and dropped; see "Rejected items" below.

## Verified problem

`order` is fully supported in the codebase but was undocumented:

- `tools/search_discovery.py:121` — `config.get("order", "relevance")` →
  YouTube `search.list` `order` param
- `tools/runner.py:158` and `tools/filter_ranker.py:577` — echoed into
  `query_plan.order`
- `schemas/input.schema.json` — enum `date` / `relevance` / `viewCount` /
  `rating`, default `relevance`

Commit 4505df5 changed the default from `date` to `relevance`, which changes
candidate recall, yet neither SKILL.md nor
`references/input-output-schema.md` mentioned the field or that `order`
affects which candidates are recalled — not just how results are presented.

## Changes applied

| File | Change |
|------|--------|
| `references/input-output-schema.md` | Added `order: relevance` to the input example; added a paragraph explaining the enum values, the recall (not presentation) impact, and the fixed-order rule for recurring comparisons; documented `query_plan.order` in the output list |
| `SKILL.md` | Added one Operating Rules bullet: `order` controls recall; keep it fixed across recurring comparison runs |
| `examples/weekly.yaml` | Added `order: relevance` once under `defaults:` — `tools/weekly_runner.py` merges `defaults` into every topic, so per-topic repetition is unnecessary |

## Rejected items (verified against the repo)

1. **"SKILL.md has duplicate Delivery workflow / order warning sections"** —
   false. The current SKILL.md contains neither section and no duplicates;
   git history never contained them. The claim described an uncommitted
   session working tree, not this repository.
2. **"weekly-automation.md lost Responsibility Boundary, Default Schedule,
   and Gmail Sent Alias"** — false. All three sections are present in
   `references/weekly-automation.md`; nothing was lost or restored.
3. **Session-specific additions to SKILL.md** ("use this in this session",
   WSL path translation, account-alias pitfalls) — rejected. SKILL.md is a
   generic contract, not a session log.
4. **Removing the Email Client Compatibility Contract from
   weekly-automation.md** — rejected. It is the only written contract for
   `tools/email_renderer.py` / `tools/email_template.html` and must survive.
5. **Real recipient addresses and account aliases in `examples/weekly.yaml`**
   — rejected. Example files keep placeholders.

## Testing

```powershell
python -m unittest discover -s tests -p 'test_*.py'
python C:\Users\mzyas\.codex\skills\.system\skill-creator\scripts\quick_validate.py .
```
