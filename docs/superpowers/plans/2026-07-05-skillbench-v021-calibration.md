# SkillBench v0.2.1 Judge Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add repeat-run judge calibration so users can quantify whether an eval setup is stable enough for CI gates or research comparisons.

**Architecture:** Introduce a small calibration runtime that calls existing `run_evaluation()` multiple times, summarizes total/dimension/case score dispersion, writes `calibration.json`, and exposes it through a new `skillbench calibrate` CLI command. Keep existing eval/report artifacts unchanged.

**Tech Stack:** Python 3.10+, dataclasses-free dictionaries for JSON artifacts, pytest.

## Global Constraints

- Do not add runtime dependencies.
- Preserve existing CLI commands and artifact formats.
- Use TDD for behavior changes.
- Store calibration output under the requested output directory and ignore generated `.skillbench/` artifacts.

---

### Task 1: Calibration Runtime

**Files:**
- Create: `runtime/skillbench/calibrate.py`
- Test: `tests/test_skillbench_core.py`

**Interfaces:**
- Produces: `run_calibration(skill_path, eval_set_path=None, output_dir=None, samples=3, max_total_range=0.25, config=None, **selection_kwargs) -> dict`
- Produces: `calibration.json` with `stable`, `samples`, `total_score`, `dimensions`, `cases`, and `reports`.

- [ ] Add failing tests for stable deterministic calibration and unstable custom judge calibration.
- [ ] Implement score summary helpers.
- [ ] Persist `calibration.json`.

### Task 2: CLI, Docs, Version, Release

**Files:**
- Modify: `runtime/skillbench/cli.py`
- Modify: `README.md`
- Modify: `ROADMAP.md`
- Modify: `.codex-plugin/plugin.json`
- Modify: `pyproject.toml`
- Modify: `VERSION`
- Test: `tests/test_skillbench_core.py`

**Interfaces:**
- Produces: `skillbench calibrate <skill_path> --eval-set <path> --samples <n> --max-total-range <float> --json`

- [ ] Add failing CLI test for machine-readable calibration output.
- [ ] Wire CLI arguments to `run_calibration()`.
- [ ] Document calibration usage.
- [ ] Bump version to `0.2.1`.
- [ ] Run full verification, review diff, commit, and push.
