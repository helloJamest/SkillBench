# SkillBench Roadmap

SkillBench is moving from a working MVP toward a trustworthy, reproducible Agent evaluation toolkit.

## v0.1.x: Open Source Adoption

- Keep install, smoke eval, report, and dashboard commands easy to run from a fresh clone.
- Maintain GitHub Actions coverage for tests, compile checks, and smoke evaluation.
- Improve contribution, security, and issue reporting guidance.
- Preserve stable JSON, JSONL, JUnit, SARIF, and static dashboard artifacts.

## v0.2.x: Evaluation Trust

- v0.2.0 shipped eval cases with difficulty, category, golden behavior, anti-patterns, and rubric notes.
- v0.2.1 shipped repeated-run judge calibration with score ranges, standard deviations, sample reports, and stability gates.
- v0.2.2 shipped dimension-level score attribution with rationale, evidence refs, and repair suggestions.
- v0.2.3 shipped benchmark fixtures for good, vague, unsafe, and incomplete skills plus a `benchmark` CLI summary.

## v0.3.x: Full-Agent Auditing

- Add first-class adapters for common agent runners while keeping `custom-command` support.
- Normalize transcripts, touched files, command logs, elapsed time, and optional cost metadata.
- Strengthen dashboard filtering, run comparison, evolution timelines, and raw artifact browsing.
- Provide CI examples that comment SkillBench summaries on pull requests.
