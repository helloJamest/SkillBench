from __future__ import annotations

from typing import Any


def build_dimension_attributions(
    dimension_scores: dict[str, float],
    rationale: str,
    suggestion: str,
    evidence_refs: list[str] | None = None,
    raw_attributions: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    refs = [str(item) for item in (evidence_refs or [])]
    raw_attributions = raw_attributions or {}
    result: dict[str, dict[str, Any]] = {}
    for dimension, score in dimension_scores.items():
        raw = raw_attributions.get(dimension, {})
        if not isinstance(raw, dict):
            raw = {}
        raw_refs = raw.get("evidence_refs", refs)
        if not isinstance(raw_refs, list):
            raw_refs = refs
        result[dimension] = {
            "score": score,
            "status": "pass" if score >= 7.0 else "fail",
            "rationale": str(raw.get("rationale") or rationale),
            "evidence_refs": [str(item) for item in raw_refs],
            "suggestion": str(raw.get("suggestion") or suggestion),
        }
    return result
