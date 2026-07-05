# SkillBench

[![CI](https://github.com/helloJamest/SkillBench/actions/workflows/ci.yml/badge.svg)](https://github.com/helloJamest/SkillBench/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

SkillBench is an evaluation and evolution framework for Codex skills. It generates or loads eval cases, scores `SKILL.md` quality with a judge-compatible rubric, records every case, and can run a GEPA-style optimization loop over candidate skill documents.

## What It Produces

Each `skillbench evo` run produces:

- An eval set describing which cases validate the skill document.
- A report with dimension scores, worst-case analysis, attribution, and suggestions.
- A local dashboard and optional Comet ML experiment artifacts for traceability.

## Quick Start

From the repository root:

```bash
python -m pip install -e ".[dev,dashboard]"
skillbench eval examples/skills/sample-skill/SKILL.md --eval-set examples/eval_sets/basic-skill-eval.json
skillbench report .skillbench/runs/latest
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

`eval`, `ci`, and `evo` can run a focused subset of an eval set:

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

List case IDs, tags, modes, and dimensions before choosing a focused run:

```powershell
python -m skillbench list-cases `
  .skillbench\evals\sample-skill.json `
  --json
```

`list-cases` accepts the same selection filters as `eval`, `ci`, and `evo`, so you can preview a focused subset:

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

`compare` also writes `comparison.json` next to the right-hand report.

## Artifacts

Every eval run writes:

- `eval_set.json`
- `report.json`
- `case_results.jsonl`
- `summary.md`
- `judge/<case_id>.input.json`
- `judge/<case_id>.output.json`
- `agent_runs/<case_id>/...` for full-agent cases
- `agent_runs/<case_id>/agent_audit.json` with runner name, status, elapsed time, transcript, command, files, and artifact links

The dashboard reads these files directly and does not recompute scores.
Case detail pages also render full-agent command, stdout, stderr, exit code, and produced file lists when `agent_runs/<case_id>/` artifacts exist.
When a custom judge fails, the same page shows a dedicated `Judge Error` section with kind, return code, stdout, and stderr.
Use the `Browse raw artifacts` link on the report page, or open `/artifacts`, to inspect every JSON, JSONL, TXT, and Markdown file in the run directory without leaving the dashboard.

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
Static exports include `artifacts/index.html` and raw artifact detail pages.

## Optional Integrations

- Comet ML: install `comet_ml` and configure `COMET_API_KEY`, `COMET_WORKSPACE`, and `COMET_PROJECT_NAME`.
- FastAPI dashboard: install `fastapi` and `uvicorn`.
- GEPA: install a compatible GEPA package; otherwise SkillBench uses its local mutation policy.
