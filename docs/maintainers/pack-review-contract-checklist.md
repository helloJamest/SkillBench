# Pack Review Contract Maintainer Checklist

Use this checklist whenever `pack-review-smoke --json` changes shape, semantics, schema rules, or consumer guidance.

## Contract Scope

- [ ] Confirm whether the change is `additive`, `breaking`, or `documentation`.
- [ ] Confirm the contract ID remains `skillbench.pack-review-smoke-result`.
- [ ] Decide whether consumers need a migration note or only a documentation note.

## Version Files

- [ ] Update `VERSION`.
- [ ] Update `runtime/skillbench/__init__.py`.
- [ ] Update `pyproject.toml`.
- [ ] Update `.codex-plugin/plugin.json`.

## Contract Artifacts

- [ ] Update `docs/schemas/pack-review-smoke-result.schema.json` when the JSON output shape changes.
- [ ] Update `docs/schemas/pack-review-contracts.changelog.json` for every contract-related release.
- [ ] Update stable fields when a field becomes part of the supported output contract.
- [ ] Keep `latest_version` aligned with the emitted `contract.version`.

## Documentation

- [ ] Update `README.md` if user-facing commands, artifact paths, or consumer guidance changed.
- [ ] Update `docs/eval-pack-review-bundles.md` for reviewer or CI consumption changes.
- [ ] Start from `docs/templates/pack-review-contract-release-note.md` when publishing release notes.
- [ ] Update `ROADMAP.md` with the shipped item and next step.

## Tests

- [ ] Update `tests/test_skillbench_core.py` for emitted `contract.version`.
- [ ] Add or update tests for schema, changelog, documentation links, and new consumer guidance.
- [ ] Run focused tests before full verification.
- [ ] Keep the `CI contract version drift check` in `docs/eval-pack-review-bundles.md` aligned with the emitted contract metadata.

## Verification

Run the full verification set before committing:

```bash
python -m pytest tests -q
python -m compileall -q -f runtime
python -m json.tool docs/schemas/pack-review-smoke-result.schema.json
python -m json.tool docs/schemas/pack-review-contracts.changelog.json
python -m skillbench pack-review-smoke examples/eval_packs/generic-skill-smoke.json examples/eval_packs/generic-skill-release.json --json
git diff --check
```
