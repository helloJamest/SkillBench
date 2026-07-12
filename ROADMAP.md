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

## v0.4.x: Skill Utility and Lift

- v0.4.0 shipped `skillbench lift` for with-skill vs without-skill A/B evaluation, `lift_report.json`, dashboard rendering, static export, case deltas, dimension lift, and deterministic bootstrap intervals.

## v0.5.x: Cross-Harness Governance

- v0.5.0 shipped `skillbench harness-matrix` to run skill-lift A/B evaluation across multiple agent runner adapters.
- v0.5.0 shipped top-level `matrix_report.json`, harness ranking, best-harness selection, dashboard rendering, and static dashboard export for cross-harness lift evidence.
- v0.5.1 shipped matrix CI gates with `--min-total-lift`, `--min-mean-case-lift`, `--require-all-pass`, persisted `gate` results, dashboard gate rendering, and non-zero CLI exits for failed gates.
- v0.5.2 shipped `--harness-cost`, per-harness confidence summaries, latency summaries from full-agent evidence, efficiency metrics, `efficiency_ranking`, and dashboard efficiency rendering.
- v0.5.3 shipped matrix CI artifacts with `matrix_ci_result.json`, `--junit`, and `--sarif` for harness matrix gates.
- v0.5.4 shipped `skillbench pr-comment` for reusable GitHub PR Markdown summaries across eval CI, lift reports, and harness matrix gate/efficiency reports.
- v0.5.5 shipped `skillbench bundle` for publishable report bundles that combine static dashboard export, PR comment markdown, JUnit, SARIF, copied raw artifacts, and raw artifact manifests.
- v0.5.6 shipped `.github/workflows/skillbench-bundles.yml` with first-class GitHub Actions examples for CI bundle uploads and harness matrix bundle publishing.
- v0.5.7 shipped contribution-ready example eval packs under `examples/eval_packs/` for third-party skill smoke and release gates.
- v0.5.8 shipped `skillbench list-packs` for discovering bundled or custom eval pack catalogs from the CLI.
- v0.5.9 shipped `skillbench bootstrap-pack` for copying a selected eval pack into a target skill project for customization.
- v0.5.10 shipped eval pack authoring hints and repair suggestions in `skillbench validate-cases`.
- v0.5.11 shipped `skillbench pack-checklist` for rendering contributor-facing Markdown review guides from eval packs.
- v0.5.12 shipped `.github/workflows/skillbench-pack-checklists.yml` for publishing eval pack checklist artifacts on pack pull requests.
- v0.5.13 shipped `skillbench pack-compare` for reviewing case, tag, dimension, category, type, and mode coverage changes across pack versions.
- v0.5.14 shipped Markdown rendering for eval pack comparisons via `skillbench pack-compare --output`.
- Next: publish eval pack comparison Markdown artifacts from the pack checklist GitHub Actions workflow.
