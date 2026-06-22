---
name: sample-skill
description: "Evaluate and improve Codex skill documents. Use when the user asks for skill eval, skill evo, skill quality reports, GEPA-style document optimization, or dashboard traceability for skill cases."
---

# Sample Skill

Use this sample when testing SkillBench itself.

## Workflow

1. Run `skillbench eval <path-to-SKILL.md>` to score the document.
2. Run `skillbench evo <path-to-SKILL.md> --rounds 2` to iterate candidates.
3. Open `skillbench dashboard <run-dir>` to inspect case-level evidence.

## Boundaries

Do not use this skill for generic README editing, dependency installation, or unrelated code changes.

## Safety

Respect approval and sandbox boundaries. Preserve report artifacts for every case.

