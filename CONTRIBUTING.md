# Contributing to SkillBench

Thanks for helping improve SkillBench. The project is still early, so the most valuable contributions are reproducible eval fixtures, judge backend integrations, dashboard traceability improvements, and CI governance examples.

## Local Setup

```bash
python -m pip install -e ".[dev,dashboard]"
python -m pytest tests -q
python -m compileall -q runtime
```

Run a smoke evaluation:

```bash
skillbench eval examples/skills/sample-skill/SKILL.md \
  --eval-set examples/eval_sets/basic-skill-eval.json
skillbench report .skillbench/runs/latest
```

## Pull Requests

- Keep changes focused on one behavior or integration.
- Add or update tests for runtime behavior changes.
- Preserve the existing artifact contract unless the PR explicitly migrates it.
- Do not commit local `.skillbench/` runs, caches, transcripts, API keys, or private skill documents.

## Design Principles

- Evidence first: every score should be traceable to case input, rubric, judge output, and agent artifacts when available.
- Open tools first: prefer standard JSON, JSONL, JUnit, SARIF, and static HTML artifacts over proprietary lock-in.
- CI friendly: commands should work in non-interactive environments.

