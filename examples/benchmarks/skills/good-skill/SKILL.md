---
name: good-skill
description: "Use when evaluating Codex skill quality with SkillBench eval cases, reports, dashboards, CI gates, evidence traces, and safe GEPA-style skill evolution. Use this only for skill documentation audits or benchmark comparisons."
---

# Good Skill

Use this skill only when the request is about evaluating, comparing, gating, or improving a Codex `SKILL.md` document. Do not use it for generic README edits, casual rewriting, or unrelated coding tasks.

## Workflow

1. Load the target `SKILL.md`, its install notes, and any bundled references needed for the requested eval.
2. Select the smallest eval set that answers the question, including negative and safety cases when publishing or running CI.
3. Run `python -m skillbench eval <skill> --eval-set <cases>` for a judge-only regression, or use `--mode full-agent` only when behavior evidence is required.
4. Inspect `report.json`, `case_results.jsonl`, judge input/output artifacts, and dashboard traces for every failed case.
5. Summarize the total score, dimension scores, worst case, attribution, and concrete repair suggestions.

## Evidence

- Keep every report, trace, transcript, artifact, and dashboard page under `.skillbench/runs/`.
- Link each recommendation to a case id and a dimension attribution.
- Preserve approval and sandbox boundaries. Ask before running destructive commands or commands that need secrets.
- For CI, compare against a baseline report and fail only on configured score or safety thresholds.

## Commands

```bash
python -m skillbench eval path/to/SKILL.md --eval-set path/to/eval.json
python -m skillbench ci path/to/SKILL.md --eval-set path/to/eval.json --min-score 8 --min-safety 7
python -m skillbench dashboard .skillbench/runs/latest
python -m skillbench evo path/to/SKILL.md --rounds 3
```

## Maintenance

Keep the runtime version, eval set version, dashboard output, and benchmark report format explicit so reviewers can reproduce results across skill releases.
