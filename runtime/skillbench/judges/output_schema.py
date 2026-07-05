from __future__ import annotations

from typing import Any

from ..schemas import EvalCase, normalize_score


class JudgeOutputError(ValueError):
    pass


def validate_judge_output(data: dict[str, Any], case: EvalCase) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise JudgeOutputError("judge output must be a JSON object")
    case_id = str(data.get("case_id") or case.id)
    score = normalize_score(float(data.get("score", 0.0)))
    raw_dimensions = data.get("dimension_scores", {})
    if not isinstance(raw_dimensions, dict):
        raise JudgeOutputError("dimension_scores must be an object")
    dimensions = {
        str(name): normalize_score(float(value))
        for name, value in raw_dimensions.items()
        if str(name) in case.dimensions
    }
    if not dimensions:
        dimensions = {dimension: score for dimension in case.dimensions}
    rationale = data.get("rationale")
    suggestion = data.get("suggestion")
    if not isinstance(rationale, str) or not rationale.strip():
        raise JudgeOutputError("rationale must be a non-empty string")
    if not isinstance(suggestion, str) or not suggestion.strip():
        raise JudgeOutputError("suggestion must be a non-empty string")
    evidence_refs = data.get("evidence_refs", [])
    if not isinstance(evidence_refs, list):
        evidence_refs = []
    raw_attributions = data.get("dimension_attributions", {})
    if not isinstance(raw_attributions, dict):
        raw_attributions = {}
    dimension_attributions = {
        str(name): value
        for name, value in raw_attributions.items()
        if str(name) in dimensions and isinstance(value, dict)
    }
    return {
        "case_id": case_id,
        "score": score,
        "dimension_scores": dimensions,
        "failed_dimensions": [name for name, value in dimensions.items() if value < 7.0],
        "rationale": rationale.strip(),
        "suggestion": suggestion.strip(),
        "evidence_refs": [str(item) for item in evidence_refs],
        "dimension_attributions": dimension_attributions,
    }
