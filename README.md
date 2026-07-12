# SkillBench

[![CI](https://github.com/helloJamest/SkillBench/actions/workflows/ci.yml/badge.svg)](https://github.com/helloJamest/SkillBench/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

SkillBench is an evaluation and evolution framework for Codex skills. It generates or loads eval cases, scores `SKILL.md` quality with a judge-compatible rubric, records every case, and can run a GEPA-style optimization loop over candidate skill documents.

## What It Produces

Each `skillbench evo` run produces:

- An eval set describing which cases validate the skill document.
- A report with dimension scores, worst-case analysis, attribution, and suggestions.
- A skill-lift A/B report comparing with-skill and without-skill runs.
- A harness matrix ranking multiple agent adapters by measured skill lift.
- A local dashboard, evolution timeline, and optional Comet ML experiment artifacts for traceability.

## Quick Start

From the repository root:

```bash
python -m pip install -e ".[dev,dashboard]"
skillbench eval examples/skills/sample-skill/SKILL.md --eval-set examples/eval_sets/basic-skill-eval.json
skillbench report .skillbench/runs/latest
skillbench list-packs --json
skillbench bootstrap-pack generic-skill-smoke-v1 --target path/to/your-skill --json
skillbench pack-checklist examples/eval_packs/generic-skill-smoke.json --output .skillbench/eval-pack-checklist.md
skillbench pack-compare examples/eval_packs/generic-skill-smoke.json examples/eval_packs/generic-skill-release.json --json
skillbench pack-compare examples/eval_packs/generic-skill-smoke.json examples/eval_packs/generic-skill-release.json --output .skillbench/eval-pack-comparison.md
skillbench pack-review-artifacts .skillbench/pack-checklists --junit .skillbench/pack-review-junit.xml --sarif .skillbench/pack-review.sarif --json
skillbench pack-review-smoke examples/eval_packs/generic-skill-smoke.json examples/eval_packs/generic-skill-release.json --json
skillbench validate-cases examples/eval_packs/generic-skill-smoke.json --json
skillbench lift examples/skills/sample-skill/SKILL.md --eval-set examples/eval_sets/basic-skill-eval.json --json
skillbench harness-matrix examples/skills/sample-skill/SKILL.md --eval-set examples/eval_sets/basic-skill-eval.json --harness custom-command --harness codex-cli --json
skillbench harness-matrix examples/skills/sample-skill/SKILL.md --eval-set examples/eval_sets/basic-skill-eval.json --harness custom-command --harness-cost custom-command=0.02 --min-total-lift 0.1 --require-all-pass
skillbench pr-comment .skillbench/runs/latest --output .skillbench/skillbench-comment.md
skillbench bundle .skillbench/runs/latest --output .skillbench/report-bundle
skillbench benchmark --json
```

Start the local dashboard for the latest run:

```bash
skillbench dashboard .skillbench/runs/latest
```

Then open `http://127.0.0.1:8765`.

For a Codex plugin checkout that is not installed as a package, set `PYTHONPATH` to the runtime directory:

```powershell
$env:PYTHONPATH = "runtime"
python -m skillbench eval examples\skills\sample-skill\SKILL.md --eval-set examples\eval_sets\basic-skill-eval.json
```

## Modes

- `judge-only`: Static, low-cost evaluation of eval cases against the skill document.
- `full-agent`: Runs a configured agent command, captures evidence, then judges the behavior.
- `lift`: Runs with-skill vs without-skill A/B evaluation and reports score deltas.
- `harness-matrix`: Runs `lift` across multiple agent adapters and ranks the measured skill utility.
- `evo`: Runs select, execute, reflect, mutate, and accept over a candidate pool.

In `full-agent` mode, command timeouts are recorded as case evidence instead of aborting the whole run. The case directory still contains `stdout.txt`, `stderr.txt`, `exit_code.txt`, `files.json`, and `agent_audit.json`; `exit_code.txt` is set to `timeout`.

Set the full-agent timeout with `--agent-timeout <seconds>` on `eval`, `ci`, or `evo`, or with `SKILLBENCH_AGENT_TIMEOUT_SEC`.

Choose an audit adapter with `--agent-runner custom-command|codex-cli|claude-cli`. SkillBench does not guess unsafe default commands for external CLIs; provide a command with `--agent-command`, `SKILLBENCH_AGENT_COMMAND`, `SKILLBENCH_CODEX_COMMAND`, or `SKILLBENCH_CLAUDE_COMMAND`. The command receives the case input on stdin.

```powershell
python -m skillbench eval `
  examples\skills\sample-skill\SKILL.md `
  --eval-set examples\eval_sets\basic-skill-eval.json `
  --mode full-agent `
  --agent-runner codex-cli `
  --agent-command "python path\to\safe_agent_harness.py"
```

## Case Selection

`eval`, `ci`, `lift`, `harness-matrix`, and `evo` can run a focused subset of an eval set:

```powershell
python -m skillbench eval `
  examples\skills\sample-skill\SKILL.md `
  --eval-set .skillbench\evals\sample-skill.json `
  --include-tag safety
```

Available filters:

- `--case-id <id>`: run a specific case; repeat for multiple cases.
- `--include-tag <tag>`: keep cases with any included tag; repeat for OR matching.
- `--exclude-tag <tag>`: skip cases with any excluded tag.
- `--case-mode judge-only|full-agent`: keep cases declared with that mode.
- `--limit <n>`: cap the selected set after filtering.

The written `eval_set.json` records the applied selection metadata, so reports and dashboard artifacts are reproducible.

## Generate Eval Cases

```powershell
$env:PYTHONPATH = "runtime"

python -m skillbench generate-cases `
  examples\skills\sample-skill\SKILL.md `
  --profile smoke `
  --output .skillbench\evals\sample-skill.json
```

Generated eval sets include `profile`, `source_skill_hash`, generator metadata, case tags, and should-trigger / should-not-trigger / ambiguous / safety cases.

## Example Eval Packs

Contribution-ready eval packs live in `examples/eval_packs/`:

- `generic-skill-smoke.json`: fast checks for trigger routing, negative boundaries, safety, and evidence.
- `generic-skill-release.json`: broader release gate coverage for trigger precision, ambiguous routing, workflow depth, tooling, safety, evidence, and maintainability.

Use them directly or copy them into your own skill repo and adapt the case inputs:

```powershell
python -m skillbench list-packs --json

python -m skillbench list-packs `
  --packs-dir examples\eval_packs

python -m skillbench bootstrap-pack `
  generic-skill-smoke-v1 `
  --target path\to\your-skill `
  --json

python -m skillbench bootstrap-pack `
  generic-skill-release-v1 `
  --target path\to\your-skill `
  --output evals\skill-release.json `
  --force

python -m skillbench pack-checklist `
  examples\eval_packs\generic-skill-smoke.json `
  --output .skillbench\eval-pack-checklist.md

python -m skillbench pack-compare `
  examples\eval_packs\generic-skill-smoke.json `
  examples\eval_packs\generic-skill-release.json `
  --json

python -m skillbench pack-compare `
  examples\eval_packs\generic-skill-smoke.json `
  examples\eval_packs\generic-skill-release.json `
  --output .skillbench\eval-pack-comparison.md

python -m skillbench validate-cases `
  examples\eval_packs\generic-skill-smoke.json `
  --json

python -m skillbench list-cases `
  examples\eval_packs\generic-skill-release.json `
  --include-tag safety `
  --json

python -m skillbench ci `
  path\to\SKILL.md `
  --eval-set examples\eval_packs\generic-skill-release.json `
  --min-score 8.0 `
  --min-safety 8.0
```

## Trusted Eval Metadata

SkillBench eval cases can describe the intent behind each score, not just the prompt to run:

- `difficulty`: `easy`, `medium`, or `hard`.
- `category`: a stable grouping such as `trigger`, `safety`, `workflow`, or `evidence`.
- `golden_behavior`: behaviors the skill or agent should demonstrate.
- `anti_patterns`: behaviors that should lower the score.
- `rubric_notes`: case-specific scoring guidance for judges and reviewers.

These fields are written into generated eval sets, judge input artifacts, `report.json`, `case_results.jsonl`, `list-cases --json`, and dashboard case pages. Older eval sets that omit them still load with safe defaults.

## Score Attribution

Each case result includes `dimension_attributions` for every scored dimension. An attribution records:

- normalized score and pass/fail status
- dimension-level rationale
- evidence references used by the judge
- targeted repair suggestion

Attributions are persisted in `report.json`, `case_results.jsonl`, and `judge/<case_id>.output.json`, and they are rendered on dashboard case detail pages.

Validate an eval set before using it in CI:

```powershell
python -m skillbench validate-cases `
  .skillbench\evals\sample-skill.json `
  --skill-path examples\skills\sample-skill\SKILL.md `
  --require-hash-match `
  --json
```

Validation results include `hints` with machine-readable repair guidance for eval pack authors. Each hint includes `type`, `severity`, `field`, `message`, `suggestion`, and an `example`; case-specific hints also include `case_id`. In text mode, SkillBench prints matching `HINT [...]` lines after errors and warnings.

Render a contributor-facing Markdown checklist before submitting a new or customized eval pack:

```powershell
python -m skillbench pack-checklist `
  .skillbench\evals\my-skill-release.json `
  --output .skillbench\eval-pack-checklist.md
```

Compare two eval packs to review coverage drift before a pack version changes:

```powershell
python -m skillbench pack-compare `
  examples\eval_packs\generic-skill-smoke.json `
  examples\eval_packs\generic-skill-release.json `
  --json
```

Use `--output .skillbench\eval-pack-comparison.md` to publish the same comparison as a human-readable Markdown artifact. When a coverage drift gate is active, the Markdown includes gate status, policy sources, and violations.

Add `metadata.coverage_drift_gate` to the right-hand eval pack, pass `--gate-policy policy.json`, or use `--fail-on-removed-dimensions`, `--fail-on-removed-tags`, `--fail-on-removed-categories`, `--fail-on-removed-types`, or `--fail-on-removed-modes` when a comparison should act as a CI coverage drift gate. Policies are merged from pack metadata, policy files, and CLI flags; the command emits JSON with a `gate` block and exits non-zero when a required coverage item was removed.

```json
{
  "coverage_drift_gate": {
    "fail_on_removed_dimensions": ["safety", "workflow_specificity"],
    "fail_on_removed_types": ["safety", "should-trigger", "should-not-trigger"],
    "fail_on_removed_modes": ["judge-only"]
  }
}
```

```powershell
python -m skillbench pack-compare `
  examples\eval_packs\generic-skill-smoke.json `
  examples\eval_packs\generic-skill-release.json `
  --gate-policy .skillbench\pack-gate-policy.json `
  --json
```

List case IDs, tags, modes, and dimensions before choosing a focused run:

```powershell
python -m skillbench list-cases `
  .skillbench\evals\sample-skill.json `
  --json
```

`list-cases` accepts the same selection filters as `eval`, `ci`, `lift`, `harness-matrix`, and `evo`, so you can preview a focused subset:

```powershell
python -m skillbench list-cases `
  .skillbench\evals\sample-skill.json `
  --include-tag safety
```

## Judge Backends

The default backend is `local-heuristic` and requires no credentials:

```powershell
python -m skillbench eval `
  examples\skills\sample-skill\SKILL.md `
  --judge-backend local-heuristic
```

Use `custom-command` to plug in a JSON judge. The command receives JSON on stdin and must return JSON on stdout:

```powershell
python -m skillbench eval `
  examples\skills\sample-skill\SKILL.md `
  --eval-set .skillbench\evals\sample-skill.json `
  --judge-backend custom-command `
  --judge-command "python examples\judges\fake_json_judge.py"
```

If a custom judge exits non-zero, times out, returns invalid JSON, or misses required fields, SkillBench records a score-0 case result with `evidence.judge_error` instead of aborting the whole run.

## CI Gates

```powershell
python -m skillbench ci `
  examples\skills\sample-skill\SKILL.md `
  --eval-set .skillbench\evals\sample-skill.json `
  --min-score 8.5 `
  --min-safety 9.0 `
  --json
```

Regression gates compare the current run to a baseline report or run directory:

```powershell
python -m skillbench ci `
  examples\skills\sample-skill\SKILL.md `
  --eval-set .skillbench\evals\sample-skill.json `
  --baseline .skillbench\runs\baseline `
  --fail-on-regression `
  --max-regression 0.05 `
  --junit .skillbench\reports\skillbench-junit.xml
```

For GitHub code scanning or other SARIF-compatible tooling, also write SARIF:

```powershell
python -m skillbench ci `
  examples\skills\sample-skill\SKILL.md `
  --eval-set .skillbench\evals\sample-skill.json `
  --min-score 8.5 `
  --sarif .skillbench\reports\skillbench.sarif
```

CI writes `ci_result.json` in the run directory and exits non-zero on threshold or regression failures. Text-mode CI also writes `junit.xml` in the run directory by default; use `--junit` and `--sarif` to choose explicit artifact paths for CI uploads.

Render a reusable Markdown PR summary from any eval run, `ci_result.json`, `lift_report.json`, `matrix_report.json`, or eval pack review artifact directory:

```powershell
python -m skillbench pr-comment `
  .skillbench\runs\latest `
  --output .skillbench\reports\skillbench-comment.md
```

For eval pack review artifacts, point `pr-comment` at a directory containing `*.validation.json` and `*comparison.json` files. The summary includes validation status, coverage drift gate status, policy sources, and violations.

The repository also includes `.github/workflows/skillbench-pr-comment.yml`, an example pull request workflow that runs `skillbench ci`, renders `skillbench pr-comment`, and posts or updates a sticky SkillBench summary comment on the PR.

Run the full eval pack review smoke locally with one command:

```powershell
python -m skillbench pack-review-smoke `
  examples\eval_packs\generic-skill-smoke.json `
  examples\eval_packs\generic-skill-release.json `
  --review-dir .skillbench\pack-review-smoke `
  --bundle-output .skillbench\pack-review-bundle `
  --clean `
  --json
```

This writes validation JSON, comparison JSON/Markdown, `pack_review_ci_result.json`, JUnit, SARIF, and a bundled dashboard for local inspection. The command prints a compact summary with validation/comparison counts, gate failures, and artifact hints; `--json` follows `docs/schemas/pack-review-smoke-result.schema.json`. Add `--clean` when repeated local runs should remove stale review and bundle artifacts before rebuilding.
For a schema-validation CI example and troubleshooting notes, see `.github/workflows/skillbench-pack-review-smoke.yml` and `docs/eval-pack-review-bundles.md`.

Build one uploadable report bundle for CI artifacts or release evidence:

```powershell
python -m skillbench bundle `
  .skillbench\runs\latest `
  --output .skillbench\report-bundle `
  --json
```

The bundle contains `dashboard/` static HTML, `skillbench-comment.md`, `raw/` copied run artifacts, `raw_artifacts.json`, `bundle_manifest.json`, and JUnit/SARIF files when the source run has `ci_result.json`, `matrix_ci_result.json`, or `pack_review_ci_result.json`.

For a complete GitHub Actions artifact template, see `.github/workflows/skillbench-bundles.yml`. It runs both `skillbench ci` and `skillbench harness-matrix`, builds report bundles, uploads `ci-report-bundle` and `matrix-report-bundle` with `actions/upload-artifact`, then fails the job only after the evidence is uploaded.

For eval pack pull requests, see `.github/workflows/skillbench-pack-checklists.yml`. It renders `skillbench pack-checklist` Markdown and `validate-cases --json` output for every `examples/eval_packs/*.json` file, adds smoke-to-release `pack-compare` Markdown/JSON coverage drift artifacts with gate status and policy sources, renders `skillbench-pack-review-comment.md`, writes `pack_review_ci_result.json`, JUnit, and SARIF artifacts, posts or updates a sticky eval pack review PR comment, applies the right-hand pack metadata gate, uploads raw `eval-pack-checklists` artifacts, builds an `eval-pack-review-bundle`, then fails only after the review evidence is available. Run `skillbench dashboard .skillbench/pack-checklists`, `skillbench export-dashboard .skillbench/pack-checklists --output <site>`, or `skillbench bundle .skillbench/pack-checklists --output <bundle>` to review the same pack evidence visually. See `docs/eval-pack-review-bundles.md` for the artifact layout and CI consumption workflow.

Harness matrix runs can also act as CI gates for cross-agent utility. By default, a matrix gate passes when any selected harness meets the configured lift thresholds. Add `--require-all-pass` when every selected harness must meet them:

```powershell
python -m skillbench harness-matrix `
  examples\skills\sample-skill\SKILL.md `
  --eval-set examples\eval_sets\basic-skill-eval.json `
  --harness custom-command `
  --harness codex-cli `
  --harness-cost custom-command=0.02 `
  --harness-cost codex-cli=0.15 `
  --min-total-lift 0.1 `
  --min-mean-case-lift 0.05 `
  --require-all-pass `
  --junit .skillbench\reports\matrix-junit.xml `
  --sarif .skillbench\reports\matrix.sarif `
  --json
```

The command writes `gate` into `matrix_report.json` with `passed`, `thresholds`, `passing_harnesses`, and `failures`, writes `matrix_ci_result.json`, and exits non-zero when the gate fails. Use `--junit` and `--sarif` to emit uploadable matrix gate artifacts for CI systems. When `--harness-cost runner=usd` is supplied, the same report includes cost-normalized lift metrics.

## Skill Lift A/B Evaluation

Use `lift` to measure whether a skill document improves the judged outcome compared with a no-skill baseline:

```powershell
python -m skillbench lift `
  examples\skills\sample-skill\SKILL.md `
  --eval-set examples\eval_sets\basic-skill-eval.json `
  --json
```

`lift` writes `lift_report.json` with baseline and candidate report paths, total lift, dimension lifts, case-level deltas, a deterministic bootstrap interval over case deltas, and a `HELPS`, `PLACEBO`, or `HARMS` verdict. Pass `--baseline-skill <path>` to compare against an explicit baseline document instead of the generated no-skill baseline.

## Harness Matrix

Use `harness-matrix` to compare how much a skill helps under different agent runner adapters:

```powershell
python -m skillbench harness-matrix `
  examples\skills\sample-skill\SKILL.md `
  --eval-set examples\eval_sets\basic-skill-eval.json `
  --harness custom-command `
  --harness codex-cli `
  --harness-cost custom-command=0.02 `
  --harness-cost codex-cli=0.15 `
  --json
```

The matrix command runs one `lift` evaluation per harness, writes each nested `lift_report.json`, then writes a top-level `matrix_report.json` with harness scores, ranking, best harness, gate result, confidence summary, latency summary, efficiency ranking, and links to the underlying lift artifacts. It accepts the same case selection filters as `eval`, `ci`, `lift`, and `evo`.

Matrix efficiency fields include:

- `confidence_summary`: bootstrap CI method, sample count, CI95 low/high, and CI95 width for mean case lift.
- `latency`: baseline/candidate elapsed seconds and case counts inferred from full-agent case evidence.
- `efficiency`: estimated cost, lift per USD, mean case lift per USD, lift per second, and mean case lift per second.
- `efficiency_ranking`: harness ranking by available lift-per-cost and lift-per-second metrics.

## Judge Calibration

Use `calibrate` to run the same skill/eval set repeatedly and measure judge stability before trusting a CI threshold or research comparison:

```powershell
python -m skillbench calibrate `
  examples\skills\sample-skill\SKILL.md `
  --eval-set examples\eval_sets\basic-skill-eval.json `
  --samples 3 `
  --max-total-range 0.25 `
  --json
```

Calibration writes `calibration.json` with total score, dimension, and case-level score ranges, standard deviations, links to each sample report, and a `stable` boolean. Text mode exits non-zero when the run is unstable; JSON mode prints the full artifact path for scripts.

## Benchmark Fixtures

Use the bundled benchmark to sanity-check judge behavior and compare representative skill quality patterns:

```powershell
python -m skillbench benchmark `
  --fixtures examples\benchmarks\skills `
  --eval-set examples\benchmarks\eval_sets\skill-quality-benchmark.json `
  --output-dir .skillbench\benchmarks `
  --json
```

The benchmark evaluates four fixtures: `good-skill`, `vague-skill`, `unsafe-skill`, and `incomplete-skill`. It writes a top-level `benchmark.json` with fixture scores, ranking, worst cases, dimension scores, and links to each fixture's normal `report.json`.

Compare two reports or run directories and emit machine-readable JSON for scripts:

```powershell
python -m skillbench compare .skillbench\runs\baseline .skillbench\runs\candidate --json
```

`compare` also writes `comparison.json` next to the right-hand report. When that file is present, the dashboard exposes `/comparison` with total-score delta, run IDs, worst cases, and dimension deltas.

## Artifacts

Every eval run writes:

- `eval_set.json`
- `examples/eval_packs/*.json` as reusable smoke and release eval templates for third-party skills
- `report.json`
- `case_results.jsonl`
- `summary.md`
- `lift_report.json` for `skillbench lift` A/B runs
- `matrix_report.json` for `skillbench harness-matrix` cross-harness lift runs
- `matrix_ci_result.json` for `skillbench harness-matrix` CI gates
- `skillbench-comment.md` or `skillbench-pack-review-comment.md` when `skillbench pr-comment --output <path>` is requested
- `pack_review_ci_result.json`, `pack-review-junit.xml`, and `pack-review.sarif` when `skillbench pack-review-artifacts` is requested
- `.skillbench/pack-review-smoke/` and `.skillbench/pack-review-bundle/` when `skillbench pack-review-smoke` is used for local pack review smoke checks
- `bundle_manifest.json`, `raw_artifacts.json`, copied `raw/` artifacts, `dashboard/`, and generated `skillbench-comment.md`/JUnit/SARIF when `skillbench bundle --output <dir>` is requested
- `.github/workflows/skillbench-bundles.yml` as an example workflow for uploading CI and harness matrix report bundles
- `.github/workflows/skillbench-pack-checklists.yml` as an example workflow for uploading eval pack checklist/comparison artifacts, JUnit/SARIF pack review artifacts, a bundled eval pack review dashboard, and posting a sticky eval pack review PR comment
- `timeline.json` for `skillbench evo` runs
- `judge/<case_id>.input.json`
- `judge/<case_id>.output.json`
- `agent_runs/<case_id>/...` for full-agent cases
- `agent_runs/<case_id>/agent_audit.json` with runner name, status, elapsed time, transcript, command, files, and artifact links

The dashboard reads these files directly and does not recompute scores.
Eval pack review directories that contain `pack_review_ci_result.json` render as a dashboard with validation status, coverage drift, policy sources, gate failures, and raw artifact links.
Case detail pages also render full-agent command, stdout, stderr, exit code, and produced file lists when `agent_runs/<case_id>/` artifacts exist.
When a custom judge fails, the same page shows a dedicated `Judge Error` section with kind, return code, stdout, and stderr.
Use the `Browse raw artifacts` link on the report page, or open `/artifacts`, to inspect every JSON, JSONL, TXT, and Markdown file in the run directory without leaving the dashboard.
The report page also includes case filters. You can combine query parameters such as `?failed=1&dimension=safety&type=safety&q=approval` to focus the case table while preserving the run summary.
Lift dashboards render `lift_report.json` with with-skill / without-skill totals, dimension lift, case lift, and verdict evidence.
Harness matrix dashboards render `matrix_report.json` with harness ranking, best harness, gate status, efficiency metrics, confidence width, lift verdicts, and links to each nested lift report.
Evolution dashboards expose `/timeline` to trace each select, reflect, mutate, and accept round with selected/mutated candidates, scores, deltas, reflection summaries, mutation summaries, and decision reasons.

Print a compact report for humans, or the persisted JSON for scripts:

```powershell
python -m skillbench report .skillbench\runs\latest
python -m skillbench report .skillbench\runs\latest --json
```

Export the dashboard as static HTML for CI artifacts or sharing:

```powershell
python -m skillbench export-dashboard `
  .skillbench\runs\latest `
  --output .skillbench\dashboard-site
```

Open `.skillbench\dashboard-site\index.html` to inspect the report without running a server.
Static exports include `artifacts/index.html`, raw artifact detail pages, harness matrix pages for `matrix_report.json`, eval pack review pages for `pack_review_ci_result.json`, `timeline/index.html` for evolution runs, and `comparison/index.html` when `comparison.json` exists.

Package the dashboard together with PR comment text, CI outputs, and copied raw artifacts:

```powershell
python -m skillbench bundle `
  .skillbench\runs\latest `
  --output .skillbench\report-bundle
```

Eval pack review artifact directories can be bundled the same way after `pack-review-artifacts` writes `pack_review_ci_result.json`:

```powershell
python -m skillbench bundle `
  .skillbench\pack-checklists `
  --output .skillbench\pack-review-bundle
```

For GitHub Actions download and triage instructions, see `docs/eval-pack-review-bundles.md`.

## Optional Integrations

- Comet ML: install `comet_ml` and configure `COMET_API_KEY`, `COMET_WORKSPACE`, and `COMET_PROJECT_NAME`.
- FastAPI dashboard: install `fastapi` and `uvicorn`.
- GEPA: install a compatible GEPA package; otherwise SkillBench uses its local mutation policy.
