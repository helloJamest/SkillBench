# SkillBench v0.2.0 Eval Trust Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add trusted eval case metadata so reports can explain not only what scored poorly, but what behavior each case expected and what anti-patterns it guards against.

**Architecture:** Extend `EvalCase` with backward-compatible optional fields, propagate those fields through loaders, generated eval sets, judge inputs, case results, list-cases output, report JSON, and dashboard case pages. Keep existing eval sets valid by providing defaults.

**Tech Stack:** Python 3.10+, pytest, dataclasses, existing SkillBench JSON artifacts.

## Global Constraints

- Do not add required runtime dependencies.
- Preserve existing CLI command names and report fields.
- Keep old eval sets loadable without migration.
- Use TDD for behavior changes.

---

### Task 1: Schema and Artifact Propagation

**Files:**
- Modify: `runtime/skillbench/schemas.py`
- Modify: `runtime/skillbench/cases/loader.py`
- Modify: `runtime/skillbench/evaluate_skill.py`
- Modify: `runtime/skillbench/judges/generic_skill_judge.py`
- Modify: `runtime/skillbench/judges/custom_command.py`
- Test: `tests/test_skillbench_core.py`

**Interfaces:**
- Produces: `EvalCase.difficulty`, `EvalCase.category`, `EvalCase.golden_behavior`, `EvalCase.anti_patterns`, `EvalCase.rubric_notes`
- Produces: matching `CaseResult` fields for report-level traceability

- [ ] Add failing tests for loading and persisting trusted case metadata.
- [ ] Add schema fields with safe defaults.
- [ ] Propagate fields into case results from all judge paths.
- [ ] Run targeted tests.

### Task 2: Generator, Validation, CLI, Dashboard, and Docs

**Files:**
- Modify: `runtime/skillbench/cases/generator.py`
- Modify: `runtime/skillbench/cases/validator.py`
- Modify: `runtime/skillbench/cli.py`
- Modify: `runtime/skillbench/dashboard/app.py`
- Modify: `README.md`
- Modify: `ROADMAP.md`
- Modify: `.codex-plugin/plugin.json`
- Modify: `pyproject.toml`
- Modify: `VERSION`
- Test: `tests/test_skillbench_core.py`

**Interfaces:**
- Produces: generated eval sets with trust metadata populated.
- Produces: `list-cases --json` entries exposing trust metadata.
- Produces: dashboard case detail sections for golden behavior, anti-patterns, and rubric notes.

- [ ] Add failing tests for generated eval sets and dashboard/list-cases visibility.
- [ ] Populate generated cases with category, difficulty, golden behavior, anti-patterns, and rubric notes.
- [ ] Add validator checks for difficulty values and soft warnings for missing trust metadata.
- [ ] Show trust metadata in list-cases JSON and dashboard case pages.
- [ ] Update docs and version to `0.2.0`.
- [ ] Run full verification and publish.
