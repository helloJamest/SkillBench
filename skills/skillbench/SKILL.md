---
name: skillbench
description: Evaluate, compare, trace, gate, or optimize Codex skills and skill plugins. Use when the user asks to assess SKILL.md quality, generate skill eval cases, run skill evo, compare skill versions, create a skill quality report, run GEPA-style skill document optimization, inspect case-level judge evidence, or use SkillBench/Comet for skill evaluation.
---

# SkillBench

Use the SkillBench runtime to evaluate and evolve Codex skills.

## Workflow

1. Locate the target `SKILL.md` or plugin skill folder.
2. Choose the smallest command that matches the request:
   - `generate-cases`: create a deterministic eval set from `SKILL.md`.
   - `validate-cases`: validate eval set structure and optional source hash; use returned `hints` to explain repair suggestions for eval pack authors.
   - `list-packs`: discover bundled or custom eval pack catalogs before copying one into a skill repo.
   - `bootstrap-pack`: copy a bundled or custom eval pack into a target skill project for customization.
   - `pack-checklist`: render a Markdown authoring checklist for reviewing an eval pack before CI.
   - `pack-compare`: compare eval pack versions for case and coverage changes, with optional removed-coverage CI gates.
   - `pack-review-artifacts`: build pack review CI result JSON, JUnit, and SARIF from eval pack review artifacts.
   - `list-cases`: inspect case IDs, tags, modes, and dimensions before filtering.
   - `eval`: score one candidate against an eval set.
   - `lift`: compare with-skill and without-skill runs to measure skill utility.
   - `harness-matrix`: run `lift` across multiple agent runner adapters, rank measured utility, summarize confidence/cost/latency, and optionally fail CI on lift gates.
   - `evo`: run select, execute, reflect, mutate, accept over candidate documents.
   - `calibrate`: repeat eval runs and summarize judge stability before CI or research comparisons.
   - `compare`: compare existing reports or run directories.
   - `ci`: enforce score and safety thresholds.
   - `benchmark`: run the bundled good/vague/unsafe/incomplete fixtures and rank them.
   - `dashboard`: serve case-level traceability for a run.
   - `export-dashboard`: write static HTML pages for a run.
   - `pr-comment`: render reusable GitHub PR Markdown for `report.json`, `ci_result.json`, `lift_report.json`, `matrix_report.json`, or eval pack review artifact directories.
   - `bundle`: build a publishable directory with static dashboard pages, PR comment Markdown, JUnit/SARIF when available, copied raw artifacts, and bundle manifests. Sources may be eval/CI run directories, matrix/lift/evolution reports, or eval pack review directories with `pack_review_ci_result.json`.
3. Prefer an explicit eval set when the user provides one. Otherwise use SkillBench's default case generator.
   - For third-party skill projects without their own eval set, start from `examples/eval_packs/generic-skill-smoke.json` or `examples/eval_packs/generic-skill-release.json`.
4. Use `judge-only` for fast regression. Use `full-agent` only when the user needs behavior evidence from a real agent run and a safe agent command is configured. Use `--agent-runner custom-command|codex-cli|claude-cli` for audit metadata, `--agent-command` or runner environment variables for execution, and `--agent-timeout` or `SKILLBENCH_AGENT_TIMEOUT_SEC` to bound full-agent commands.
5. Preserve all generated artifacts under `.skillbench/runs/` unless the user asks for another output directory.
6. For focused checks, pass case selection filters to `eval`, `ci`, `lift`, `harness-matrix`, or `evo`: `--case-id`, `--include-tag`, `--exclude-tag`, `--case-mode`, and `--limit`.
7. If a full-agent case times out, inspect the recorded `agent_runs/<case_id>/` artifacts; SkillBench records the timeout as evidence instead of treating it as a framework crash.
8. For cross-harness CI checks, pass `--min-total-lift`, `--min-mean-case-lift`, and optionally `--require-all-pass` to `harness-matrix`; inspect `matrix_report.json.gate` and `matrix_ci_result.json` when it exits non-zero.
9. For cost-normalized comparisons, pass `--harness-cost runner=usd`; inspect `matrix_report.json.harnesses[].efficiency`, `latency`, `confidence_summary`, and top-level `efficiency_ranking`.
10. For matrix gate artifacts, pass `--junit <path>` and `--sarif <path>` to `harness-matrix`.
11. If `custom-command` judge output fails, inspect `evidence.judge_error` in the case result and the persisted judge input/output artifacts.

## Runtime

From a plugin checkout:

```bash
PYTHONPATH=plugins/skillbench/runtime python -m skillbench eval <path-to-SKILL.md>
PYTHONPATH=plugins/skillbench/runtime python -m skillbench generate-cases <path-to-SKILL.md>
PYTHONPATH=plugins/skillbench/runtime python -m skillbench validate-cases <path-to-eval-set.json>
PYTHONPATH=plugins/skillbench/runtime python -m skillbench list-packs --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench bootstrap-pack generic-skill-smoke-v1 --target <path-to-skill-project> --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench pack-checklist <path-to-eval-set.json> --output .skillbench/eval-pack-checklist.md
PYTHONPATH=plugins/skillbench/runtime python -m skillbench pack-compare <left-eval-set.json> <right-eval-set.json> --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench pack-compare <left-eval-set.json> <right-eval-set.json> --output .skillbench/eval-pack-comparison.md
PYTHONPATH=plugins/skillbench/runtime python -m skillbench pack-compare <left-eval-set.json> <right-eval-set.json> --fail-on-removed-dimensions safety workflow_specificity --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench pack-compare <left-eval-set.json> <right-eval-set.json> --gate-policy .skillbench/pack-gate-policy.json --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench validate-cases plugins/skillbench/examples/eval_packs/generic-skill-smoke.json --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench list-cases <path-to-eval-set.json> --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench list-cases plugins/skillbench/examples/eval_packs/generic-skill-release.json --include-tag safety --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench report .skillbench/runs/latest --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench lift <path-to-SKILL.md> --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench harness-matrix <path-to-SKILL.md> --harness custom-command --harness codex-cli --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench harness-matrix <path-to-SKILL.md> --harness custom-command --harness-cost custom-command=0.02 --min-total-lift 0.1 --require-all-pass
PYTHONPATH=plugins/skillbench/runtime python -m skillbench harness-matrix <path-to-SKILL.md> --harness custom-command --min-total-lift 0.1 --junit .skillbench/matrix-junit.xml --sarif .skillbench/matrix.sarif
PYTHONPATH=plugins/skillbench/runtime python -m skillbench evo <path-to-SKILL.md> --rounds 3
PYTHONPATH=plugins/skillbench/runtime python -m skillbench calibrate <path-to-SKILL.md> --samples 3 --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench benchmark --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench ci <path-to-SKILL.md> --include-tag safety --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench pr-comment .skillbench/runs/latest --output .skillbench/skillbench-comment.md
PYTHONPATH=plugins/skillbench/runtime python -m skillbench bundle .skillbench/runs/latest --output .skillbench/report-bundle --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench dashboard .skillbench/runs/latest
PYTHONPATH=plugins/skillbench/runtime python -m skillbench export-dashboard .skillbench/runs/latest --output .skillbench/site
```

On Windows PowerShell:

```powershell
$env:PYTHONPATH = "plugins\skillbench\runtime"
python -m skillbench eval <path-to-SKILL.md>
```

## Output Expectations

Every eval/evo run should produce:

- `eval_set.json`
- `examples/eval_packs/generic-skill-smoke.json` and `examples/eval_packs/generic-skill-release.json` as reusable third-party skill eval templates
- `report.json`
- `case_results.jsonl`
- dimension-level `dimension_attributions` in case results and judge output artifacts
- candidate snapshots
- `lift_report.json` for `lift` runs, rendered in the dashboard and exported as static HTML
- `matrix_report.json` for `harness-matrix` runs, including `gate`, `confidence_summary`, `latency`, and `efficiency` results, rendered in the dashboard and exported as static HTML
- `matrix_ci_result.json` for `harness-matrix` gates, plus optional matrix JUnit and SARIF artifacts
- `timeline.json` for `evo` runs, rendered at `/timeline` and exported as `timeline/index.html`
- normalized `agent_audit.json` for each full-agent case
- optional `reflection.json` and mutation records
- `comet_offline.jsonl` when Comet ML is unavailable
- `ci_result.json` when using CI gates
- `skillbench-comment.md` or `skillbench-pack-review-comment.md` when using `pr-comment --output <path>` for GitHub PR summaries
- `pack_review_ci_result.json`, pack review JUnit, and pack review SARIF when using `pack-review-artifacts`
- `bundle_manifest.json`, `raw_artifacts.json`, copied `raw/` artifacts, and `dashboard/` when using `bundle --output <dir>`
- SARIF output when `ci --sarif <path>` is requested
- `.github/workflows/skillbench-pr-comment.yml` as an example PR comment workflow that delegates summary rendering to `skillbench pr-comment`
- `.github/workflows/skillbench-bundles.yml` as an example artifact workflow that uploads CI and harness matrix report bundles
- `.github/workflows/skillbench-pack-checklists.yml` as an example artifact workflow that uploads eval pack checklist Markdown, validation JSON, smoke-to-release comparison Markdown/JSON, coverage drift gate evidence, JUnit/SARIF pack review artifacts, dashboard-readable pack review evidence, a bundled eval pack review dashboard, and posts or updates a reusable pack review PR comment
- `comparison.json` when comparing runs, rendered at `/comparison` and exported as `comparison/index.html` when dashboard artifacts are built
- `calibration.json` when calibrating judge stability
- `benchmark.json` when running bundled quality fixtures
- `manifest.json` and static HTML pages when exporting dashboards

Use the dashboard or report files to explain failures with case IDs, dimensions, evidence, judge suggestions, raw artifacts, skill-lift deltas, matrix gate failures, harness efficiency, comparison deltas, eval pack review gates, and evolution timeline decisions. Dashboard report pages include case filters, an artifact browser at `/artifacts`, a lift report view for `lift` runs, a harness matrix view for `harness-matrix` runs, an eval pack review view when `pack_review_ci_result.json` exists, a timeline view for `evo` runs, and a comparison view when `comparison.json` exists.
When `validate-cases` reports `hints`, surface the concrete field, suggestion, and example so contributors can repair pack metadata without reverse-engineering the schema.
When `pack-checklist` is used, summarize the generated Markdown path and call out validation failures or repair hints that need action before CI.
When `pack-compare --output` is used, summarize added/removed cases, coverage changes, gate status, policy sources, and gate violations from the Markdown artifact path.
