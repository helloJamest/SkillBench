# Pack Review Contract Release Note

Use this template when `pack-review-smoke --json` changes shape, semantics, or consumer guidance.

## Summary

- Version: `0.0.0`
- Date: `YYYY-MM-DD`
- Contract ID: `skillbench.pack-review-smoke-result`
- Compatibility: `additive | breaking | documentation`
- Schema: `docs/schemas/pack-review-smoke-result.schema.json`
- Changelog: `docs/schemas/pack-review-contracts.changelog.json`

## What Changed

- Describe the JSON fields, schema rules, or consumer guidance that changed.
- Link the changelog entry and schema diff.

## Stable Fields Changed

- Added:
- Changed:
- Removed:

## Consumer Impact

- Who needs to update: CI workflows, dashboards, scripts, or external integrations.
- Expected behavior for old consumers.
- Whether unknown fields can be ignored safely.

## Migration Notes

- Required code or workflow updates.
- Fallback behavior for older SkillBench output.
- Compatibility guard updates, if the major version changed.

## Verification

Run these checks before publishing the release note:

```bash
python -m json.tool docs/schemas/pack-review-contracts.changelog.json
python -m json.tool docs/schemas/pack-review-smoke-result.schema.json
python -m skillbench pack-review-smoke examples/eval_packs/generic-skill-smoke.json examples/eval_packs/generic-skill-release.json --json
```
