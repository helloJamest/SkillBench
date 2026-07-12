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
- v0.5.15 shipped eval pack comparison Markdown/JSON artifacts from the pack checklist GitHub Actions workflow.
- v0.5.16 shipped `pack-compare --fail-on-removed-*` coverage drift gates and wired required dimension/type/mode gates into the pack checklist workflow.
- v0.5.17 shipped coverage drift gate policy loading from right-hand eval pack metadata and `--gate-policy` JSON files.
- v0.5.18 shipped coverage drift gate status, policy sources, and violations in Markdown comparison artifacts.
- v0.5.19 shipped reusable PR comment rendering for eval pack checklist, validation, and coverage drift review artifacts.
- v0.5.20 shipped an example GitHub workflow step that posts or updates the eval pack review PR comment.
- v0.5.21 shipped JUnit/SARIF-style CI artifacts for eval pack validation and coverage drift gates.
- v0.5.22 shipped dashboard and static HTML rendering for eval pack review artifacts.
- v0.5.23 shipped eval pack review report bundles and uploaded bundle artifacts from the pack checklist workflow.
- v0.5.24 shipped release-quality docs for consuming eval pack review bundles from CI.
- v0.5.25 shipped `skillbench pack-review-smoke` as a compact local command for producing eval pack review evidence bundles.
- v0.5.26 shipped `pack-review-smoke --clean` for repeated local runs without stale artifacts.
- v0.5.27 shipped richer pack review smoke summaries with top gate failures and artifact hints.
- v0.5.28 shipped JSON schema documentation for `pack-review-smoke --json` output.
- v0.5.29 shipped a GitHub Actions example for validating `pack-review-smoke --json` against its schema.
- v0.5.30 shipped concise troubleshooting docs for schema validation failures.
- v0.5.31 shipped a machine-readable changelog for pack review output contracts.
- v0.5.32 shipped contract metadata emission in `pack-review-smoke --json`.
- v0.5.33 shipped a contract-aware consumer example for validating smoke JSON.
- Next: add a small compatibility guard example for rejecting unsupported contract major versions.
