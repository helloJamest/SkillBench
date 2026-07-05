# SkillBench v0.2.2 Score Attribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every dimension score explainable with structured rationale, evidence references, and repair suggestions.

**Architecture:** Add a backward-compatible `dimension_attributions` field to `CaseResult`, populate it from the deterministic judge and custom-command judge output, persist it in `report.json`, `case_results.jsonl`, and judge output artifacts, and render it in dashboard case pages.

**Tech Stack:** Python 3.10+, dataclasses, existing JSON artifacts, pytest.

## Global Constraints

- Do not add runtime dependencies.
- Preserve existing CLI command names and report fields.
- Keep old reports readable by treating missing attributions as empty.
- Use TDD for behavior changes.

---

### Task 1: Attribution Data Contract

**Files:**
- Modify: `runtime/skillbench/schemas.py`
- Modify: `runtime/skillbench/judges/output_schema.py`
- Modify: `runtime/skillbench/judges/generic_skill_judge.py`
- Modify: `runtime/skillbench/judges/custom_command.py`
- Modify: `runtime/skillbench/evaluate_skill.py`
- Test: `tests/test_skillbench_core.py`

**Interfaces:**
- Produces: `CaseResult.dimension_attributions: dict[str, dict[str, object]]`
- Produces: optional custom judge `dimension_attributions` parsing.

- [ ] Add failing tests for persisted report attributions and custom-command attribution parsing.
- [ ] Add schema field with default `{}`.
- [ ] Populate attribution entries for each scored dimension.
- [ ] Include attributions in judge output artifacts.

### Task 2: Dashboard, Docs, Version, Release

**Files:**
- Modify: `runtime/skillbench/dashboard/app.py`
- Modify: `README.md`
- Modify: `ROADMAP.md`
- Modify: `.codex-plugin/plugin.json`
- Modify: `pyproject.toml`
- Modify: `VERSION`
- Test: `tests/test_skillbench_core.py`

**Interfaces:**
- Produces: dashboard case detail `Dimension Attribution` section.

- [ ] Add failing dashboard test for attribution rendering.
- [ ] Render dimension attribution table with score, status, rationale, evidence refs, and suggestion.
- [ ] Document attribution artifacts.
- [ ] Bump version to `0.2.2`.
- [ ] Run full verification, review diff, commit, and push.
