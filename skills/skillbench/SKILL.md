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
   - `validate-cases`: validate eval set structure and optional source hash.
   - `list-cases`: inspect case IDs, tags, modes, and dimensions before filtering.
   - `eval`: score one candidate against an eval set.
   - `evo`: run select, execute, reflect, mutate, accept over candidate documents.
   - `calibrate`: repeat eval runs and summarize judge stability before CI or research comparisons.
   - `compare`: compare existing reports or run directories.
   - `ci`: enforce score and safety thresholds.
   - `benchmark`: run the bundled good/vague/unsafe/incomplete fixtures and rank them.
   - `dashboard`: serve case-level traceability for a run.
   - `export-dashboard`: write static HTML pages for a run.
3. Prefer an explicit eval set when the user provides one. Otherwise use SkillBench's default case generator.
4. Use `judge-only` for fast regression. Use `full-agent` only when the user needs behavior evidence from a real agent run and a safe agent command is configured. Use `--agent-runner custom-command|codex-cli|claude-cli` for audit metadata, `--agent-command` or runner environment variables for execution, and `--agent-timeout` or `SKILLBENCH_AGENT_TIMEOUT_SEC` to bound full-agent commands.
5. Preserve all generated artifacts under `.skillbench/runs/` unless the user asks for another output directory.
6. For focused checks, pass case selection filters to `eval`, `ci`, or `evo`: `--case-id`, `--include-tag`, `--exclude-tag`, `--case-mode`, and `--limit`.
7. If a full-agent case times out, inspect the recorded `agent_runs/<case_id>/` artifacts; SkillBench records the timeout as evidence instead of treating it as a framework crash.
8. If `custom-command` judge output fails, inspect `evidence.judge_error` in the case result and the persisted judge input/output artifacts.

## Runtime

From a plugin checkout:

```bash
PYTHONPATH=plugins/skillbench/runtime python -m skillbench eval <path-to-SKILL.md>
PYTHONPATH=plugins/skillbench/runtime python -m skillbench generate-cases <path-to-SKILL.md>
PYTHONPATH=plugins/skillbench/runtime python -m skillbench validate-cases <path-to-eval-set.json>
PYTHONPATH=plugins/skillbench/runtime python -m skillbench list-cases <path-to-eval-set.json> --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench report .skillbench/runs/latest --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench evo <path-to-SKILL.md> --rounds 3
PYTHONPATH=plugins/skillbench/runtime python -m skillbench calibrate <path-to-SKILL.md> --samples 3 --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench benchmark --json
PYTHONPATH=plugins/skillbench/runtime python -m skillbench ci <path-to-SKILL.md> --include-tag safety --json
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
- `report.json`
- `case_results.jsonl`
- dimension-level `dimension_attributions` in case results and judge output artifacts
- candidate snapshots
- normalized `agent_audit.json` for each full-agent case
- optional `reflection.json` and mutation records
- `comet_offline.jsonl` when Comet ML is unavailable
- `ci_result.json` when using CI gates
- SARIF output when `ci --sarif <path>` is requested
- `comparison.json` when comparing runs
- `calibration.json` when calibrating judge stability
- `benchmark.json` when running bundled quality fixtures
- `manifest.json` and static HTML pages when exporting dashboards

Use the dashboard or report files to explain failures with case IDs, dimensions, evidence, and judge suggestions.
