from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ..config import resolve_skill_file
from ..schemas import DIMENSIONS
from .loader import load_eval_set_data


VALID_TYPES = {"should-trigger", "should-not-trigger", "ambiguous", "safety", "full-agent", "behavior"}
VALID_MODES = {"judge-only", "full-agent"}
VALID_PROFILES = {"smoke", "release", "stress", "custom"}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}


def validate_eval_set(
    eval_set_path: str | Path,
    skill_path: str | Path | None = None,
    require_hash_match: bool = False,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    hints: list[dict[str, Any]] = []
    try:
        eval_set = load_eval_set_data(eval_set_path)
    except Exception as exc:
        return {
            "passed": False,
            "eval_set_path": str(eval_set_path),
            "errors": [{"type": "load-error", "message": str(exc)}],
            "warnings": [],
            "hints": [
                _hint(
                    "load-error",
                    "error",
                    "eval_set",
                    str(exc),
                    "Check that the eval set is valid JSON and matches the SkillBench eval set shape.",
                    {"id": "my-skill-smoke-v1", "cases": []},
                )
            ],
        }

    if not eval_set.id:
        errors.append({"type": "schema", "message": "eval set id is required"})
        hints.append(
            _hint(
                "schema",
                "error",
                "id",
                "eval set id is required",
                "Set a stable eval set id, usually '<skill-name>-<profile>-v1'.",
                {"id": "my-skill-smoke-v1"},
            )
        )
    if eval_set.profile not in VALID_PROFILES:
        warnings.append({"type": "profile", "message": f"unknown profile '{eval_set.profile}'"})
        hints.append(
            _hint(
                "profile",
                "warning",
                "profile",
                f"unknown profile '{eval_set.profile}'",
                "Use one of: smoke, release, stress, custom.",
                {"profile": "smoke"},
            )
        )
    if not eval_set.cases:
        errors.append({"type": "schema", "message": "eval set must contain at least one case"})
        hints.append(
            _hint(
                "schema",
                "error",
                "cases",
                "eval set must contain at least one case",
                "Add at least one case with id, input, type, dimensions, and trusted metadata.",
                {
                    "cases": [
                        {
                            "id": "trigger-basic",
                            "input": "Ask the agent to perform the skill's core workflow.",
                            "type": "should-trigger",
                            "dimensions": ["trigger_clarity", "workflow_specificity"],
                        }
                    ]
                },
            )
        )

    seen: set[str] = set()
    for case in eval_set.cases:
        case_id = case.id or "<missing-id>"
        if not case.id:
            errors.append({"type": "case", "message": "case id is required"})
            hints.append(
                _hint(
                    "case",
                    "error",
                    "cases[].id",
                    "case id is required",
                    "Set a short stable id that explains the scenario.",
                    {"id": "safety-boundary"},
                )
            )
        if case.id in seen:
            errors.append({"type": "duplicate-case-id", "message": f"duplicate case id '{case.id}'"})
            hints.append(
                _hint(
                    "duplicate-case-id",
                    "error",
                    _case_field(case_id, "id"),
                    f"duplicate case id '{case.id}'",
                    "Make every case id unique so reports and dashboard links are stable.",
                    {"id": f"{case_id}-2"},
                    case_id=case.id,
                )
            )
        seen.add(case.id)
        if not case.input.strip():
            errors.append({"type": "case-input", "message": f"case '{case.id}' input is empty"})
            hints.append(
                _hint(
                    "case-input",
                    "error",
                    _case_field(case_id, "input"),
                    f"case '{case.id}' input is empty",
                    "Write the user/task prompt that should exercise this skill behavior.",
                    {"input": "Use the skill to complete the expected workflow and cite evidence."},
                    case_id=case.id,
                )
            )
        if case.type not in VALID_TYPES:
            errors.append({"type": "case-type", "message": f"case '{case.id}' has invalid type '{case.type}'"})
            hints.append(
                _hint(
                    "case-type",
                    "error",
                    _case_field(case_id, "type"),
                    f"case '{case.id}' has invalid type '{case.type}'",
                    "Use one of: should-trigger, should-not-trigger, ambiguous, safety, full-agent, behavior.",
                    {"type": "should-trigger"},
                    case_id=case.id,
                )
            )
        if case.mode not in VALID_MODES:
            errors.append({"type": "case-mode", "message": f"case '{case.id}' has invalid mode '{case.mode}'"})
            hints.append(
                _hint(
                    "case-mode",
                    "error",
                    _case_field(case_id, "mode"),
                    f"case '{case.id}' has invalid mode '{case.mode}'",
                    "Use judge-only for static review or full-agent when the case requires a real agent run.",
                    {"mode": "judge-only"},
                    case_id=case.id,
                )
            )
        if case.difficulty not in VALID_DIFFICULTIES:
            errors.append({"type": "difficulty", "message": f"case '{case.id}' has invalid difficulty '{case.difficulty}'"})
            hints.append(
                _hint(
                    "difficulty",
                    "error",
                    _case_field(case_id, "difficulty"),
                    f"case '{case.id}' has invalid difficulty '{case.difficulty}'",
                    "Use one of: easy, medium, hard.",
                    {"difficulty": "medium"},
                    case_id=case.id,
                )
            )
        invalid_dimensions = [dimension for dimension in case.dimensions if dimension not in DIMENSIONS]
        if invalid_dimensions:
            errors.append(
                {
                    "type": "dimension",
                    "message": f"case '{case.id}' has invalid dimensions: {', '.join(invalid_dimensions)}",
                }
            )
            hints.append(
                _hint(
                    "dimension",
                    "error",
                    _case_field(case_id, "dimensions"),
                    f"case '{case.id}' has invalid dimensions: {', '.join(invalid_dimensions)}",
                    f"Use SkillBench rubric dimensions such as: {', '.join(sorted(DIMENSIONS)[:5])}.",
                    {"dimensions": ["trigger_clarity", "workflow_specificity", "safety"]},
                    case_id=case.id,
                )
            )
        if not case.tags:
            warnings.append({"type": "tags", "message": f"case '{case.id}' has no tags"})
            hints.append(
                _hint(
                    "tags",
                    "warning",
                    _case_field(case_id, "tags"),
                    f"case '{case.id}' has no tags",
                    "Add tags for selection and CI slicing, for example profile, category, and risk tags.",
                    {"tags": ["smoke", "trigger"]},
                    case_id=case.id,
                )
            )
        if case.category == "general" or not case.golden_behavior or not case.anti_patterns or not case.rubric_notes:
            warnings.append({"type": "trust-metadata", "message": f"case '{case.id}' is missing trusted evaluation metadata"})
            hints.append(
                _hint(
                    "trust-metadata",
                    "warning",
                    f"cases[{case_id}].{{category,golden_behavior,anti_patterns,rubric_notes}}",
                    f"case '{case.id}' is missing trusted evaluation metadata",
                    "Add category, golden_behavior, anti_patterns, and rubric_notes so judges know what good and bad behavior means.",
                    {
                        "category": "trigger-routing",
                        "golden_behavior": ["The agent selects this skill only when the request matches its purpose."],
                        "anti_patterns": ["The agent uses this skill for adjacent or unrelated tasks."],
                        "rubric_notes": ["Lower trigger_precision when the skill would route unrelated tasks."],
                    },
                    case_id=case.id,
                )
            )

    expected_hash = _skill_hash(skill_path) if skill_path else None
    if expected_hash and eval_set.source_skill_hash and eval_set.source_skill_hash != expected_hash:
        message = "eval set source_skill_hash does not match the provided skill"
        if require_hash_match:
            errors.append({"type": "source-hash", "message": message})
            severity = "error"
        else:
            warnings.append({"type": "source-hash", "message": message})
            severity = "warning"
        hints.append(
            _hint(
                "source-hash",
                severity,
                "source_skill_hash",
                message,
                "Regenerate or update source_skill_hash after changing the source SKILL.md.",
                {"source_skill_hash": expected_hash},
            )
        )
    if skill_path and not eval_set.source_skill_hash:
        warnings.append({"type": "source-hash", "message": "eval set has no source_skill_hash"})
        hints.append(
            _hint(
                "source-hash",
                "warning",
                "source_skill_hash",
                "eval set has no source_skill_hash",
                "Add the current skill hash when this eval set is tied to one source skill.",
                {"source_skill_hash": expected_hash},
            )
        )

    return {
        "passed": not errors,
        "eval_set_id": eval_set.id,
        "eval_set_path": str(eval_set_path),
        "profile": eval_set.profile,
        "cases": len(eval_set.cases),
        "errors": errors,
        "warnings": warnings,
        "hints": hints,
    }


def _skill_hash(skill_path: str | Path | None) -> str | None:
    if not skill_path:
        return None
    skill_file = resolve_skill_file(skill_path)
    return f"sha256:{hashlib.sha256(skill_file.read_bytes()).hexdigest()}"


def _case_field(case_id: str, field: str) -> str:
    return f"cases[{case_id}].{field}"


def _hint(
    kind: str,
    severity: str,
    field: str,
    message: str,
    suggestion: str,
    example: Any,
    *,
    case_id: str | None = None,
) -> dict[str, Any]:
    hint = {
        "type": kind,
        "severity": severity,
        "field": field,
        "message": message,
        "suggestion": suggestion,
        "example": example,
    }
    if case_id:
        hint["case_id"] = case_id
    return hint
