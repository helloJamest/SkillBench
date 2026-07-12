# SkillBench Eval Packs

Reusable eval packs help third-party skill authors start with a trusted baseline instead of a blank JSON file.

## Packs

- `generic-skill-smoke.json`: fast smoke coverage for trigger routing, negative boundaries, safety, and evidence.
- `generic-skill-release.json`: broader release coverage for trigger precision, ambiguous routing, workflow depth, tooling, safety, evidence, and maintainability.

## Usage

Validate a pack before adapting it:

```bash
skillbench validate-cases examples/eval_packs/generic-skill-smoke.json --json
```

Preview cases and tags:

```bash
skillbench list-cases examples/eval_packs/generic-skill-release.json --json
skillbench list-cases examples/eval_packs/generic-skill-release.json --include-tag safety --json
```

Run a skill against a pack:

```bash
skillbench eval path/to/SKILL.md --eval-set examples/eval_packs/generic-skill-smoke.json
skillbench ci path/to/SKILL.md --eval-set examples/eval_packs/generic-skill-release.json --min-score 8.0 --min-safety 8.0
```

Copy a pack into your project, then edit case inputs, expected fields, and trusted metadata for your domain. Keep `tags`, `difficulty`, `category`, `golden_behavior`, `anti_patterns`, and `rubric_notes` complete so reports stay explainable.
