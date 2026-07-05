# SkillBench Roadmap

SkillBench is moving from a working MVP toward a trustworthy, reproducible Agent evaluation toolkit.

## v0.1.x: Open Source Adoption

- Keep install, smoke eval, report, and dashboard commands easy to run from a fresh clone.
- Maintain GitHub Actions coverage for tests, compile checks, and smoke evaluation.
- Improve contribution, security, and issue reporting guidance.
- Preserve stable JSON, JSONL, JUnit, SARIF, and static dashboard artifacts.

## v0.2.x: Evaluation Trust

- Extend eval cases with difficulty, category, golden behavior, anti-patterns, and rubric notes.
- Add judge calibration metrics for multi-judge or repeated judging consistency.
- Improve score attribution so every dimension score points back to evidence and rubric decisions.
- Expand benchmark fixtures for good, vague, unsafe, and incomplete skills.

## v0.3.x: Full-Agent Auditing

- Add first-class adapters for common agent runners while keeping `custom-command` support.
- Normalize transcripts, touched files, command logs, elapsed time, and optional cost metadata.
- Strengthen dashboard filtering, run comparison, evolution timelines, and raw artifact browsing.
- Provide CI examples that comment SkillBench summaries on pull requests.
