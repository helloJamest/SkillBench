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

- v0.3.0 shipped first-class runner adapter metadata for `custom-command`, `codex-cli`, and `claude-cli` while keeping explicit command execution.
- v0.3.0 shipped normalized `agent_audit.json` with transcripts, touched files, command logs, status, and elapsed time.
- v0.3.1 shipped raw artifact browsing in the dashboard and static dashboard export.
- v0.3.2 shipped a GitHub Actions PR comment workflow example for SkillBench CI summaries.
- v0.3.3 shipped dashboard case filtering by query, failed-only, dimension, type, mode, and category.
- v0.3.4 shipped dashboard rendering and static export for run comparison reports.
- v0.3.5 shipped `timeline.json`, `/timeline`, and static timeline export for evolution run replay.
