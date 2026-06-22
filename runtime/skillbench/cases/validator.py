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


def validate_eval_set(
    eval_set_path: str | Path,
    skill_path: str | Path | None = None,
    require_hash_match: bool = False,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    try:
        eval_set = load_eval_set_data(eval_set_path)
    except Exception as exc:
        return {
            "passed": False,
            "eval_set_path": str(eval_set_path),
            "errors": [{"type": "load-error", "message": str(exc)}],
            "warnings": [],
        }

    if not eval_set.id:
        errors.append({"type": "schema", "message": "eval set id is required"})
    if eval_set.profile not in VALID_PROFILES:
        warnings.append({"type": "profile", "message": f"unknown profile '{eval_set.profile}'"})
    if not eval_set.cases:
        errors.append({"type": "schema", "message": "eval set must contain at least one case"})

    seen: set[str] = set()
    for case in eval_set.cases:
        if not case.id:
            errors.append({"type": "case", "message": "case id is required"})
        if case.id in seen:
            errors.append({"type": "duplicate-case-id", "message": f"duplicate case id '{case.id}'"})
        seen.add(case.id)
        if not case.input.strip():
            errors.append({"type": "case-input", "message": f"case '{case.id}' input is empty"})
        if case.type not in VALID_TYPES:
            errors.append({"type": "case-type", "message": f"case '{case.id}' has invalid type '{case.type}'"})
        if case.mode not in VALID_MODES:
            errors.append({"type": "case-mode", "message": f"case '{case.id}' has invalid mode '{case.mode}'"})
        invalid_dimensions = [dimension for dimension in case.dimensions if dimension not in DIMENSIONS]
        if invalid_dimensions:
            errors.append(
                {
                    "type": "dimension",
                    "message": f"case '{case.id}' has invalid dimensions: {', '.join(invalid_dimensions)}",
                }
            )
        if not case.tags:
            warnings.append({"type": "tags", "message": f"case '{case.id}' has no tags"})

    expected_hash = _skill_hash(skill_path) if skill_path else None
    if expected_hash and eval_set.source_skill_hash and eval_set.source_skill_hash != expected_hash:
        message = "eval set source_skill_hash does not match the provided skill"
        if require_hash_match:
            errors.append({"type": "source-hash", "message": message})
        else:
            warnings.append({"type": "source-hash", "message": message})
    if skill_path and not eval_set.source_skill_hash:
        warnings.append({"type": "source-hash", "message": "eval set has no source_skill_hash"})

    return {
        "passed": not errors,
        "eval_set_id": eval_set.id,
        "eval_set_path": str(eval_set_path),
        "profile": eval_set.profile,
        "cases": len(eval_set.cases),
        "errors": errors,
        "warnings": warnings,
    }


def _skill_hash(skill_path: str | Path | None) -> str | None:
    if not skill_path:
        return None
    skill_file = resolve_skill_file(skill_path)
    return f"sha256:{hashlib.sha256(skill_file.read_bytes()).hexdigest()}"

