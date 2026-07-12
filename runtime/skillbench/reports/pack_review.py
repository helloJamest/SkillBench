from __future__ import annotations

from pathlib import Path
from typing import Any

from ..observability.logging_io import read_json, write_json


def build_pack_review_ci_result(review_dir: str | Path, *, output_path: str | Path | None = None) -> dict[str, Any]:
    root = Path(review_dir)
    report_path = Path(output_path) if output_path else root / "pack_review_ci_result.json"
    failures: list[dict[str, Any]] = []
    validations = []
    comparisons = []

    for path in sorted(root.glob("*.validation.json")):
        payload = read_json(path)
        validations.append(
            {
                "path": str(path),
                "passed": bool(payload.get("passed")),
                "eval_set_id": payload.get("eval_set_id"),
                "cases": payload.get("cases"),
            }
        )
        for error in payload.get("errors") or []:
            failures.append(
                {
                    "type": "validation",
                    "message": f"{payload.get('eval_set_id', path.stem)} validation failed: {error.get('message', error)}",
                    "artifact": str(path),
                    "eval_set_id": payload.get("eval_set_id"),
                    "field": error.get("field"),
                }
            )

    for path in sorted(root.glob("*.json")):
        if path.name.endswith(".validation.json") or path.name == report_path.name:
            continue
        payload = read_json(path)
        if payload.get("schema_version") != "skillbench.eval-pack-comparison.v1":
            continue
        gate = payload.get("gate") or {}
        comparisons.append(
            {
                "path": str(path),
                "passed": bool(gate.get("passed", True)),
                "case_delta": payload.get("case_delta"),
                "left_eval_set_id": (payload.get("left") or {}).get("eval_set_id"),
                "right_eval_set_id": (payload.get("right") or {}).get("eval_set_id"),
                "policy_sources": list(gate.get("policy_sources") or []),
            }
        )
        left = (payload.get("left") or {}).get("eval_set_id", "-")
        right = (payload.get("right") or {}).get("eval_set_id", "-")
        for violation in gate.get("violations") or []:
            values = ", ".join(str(value) for value in violation.get("values", [])) or "-"
            failures.append(
                {
                    "type": "coverage_drift",
                    "message": f"{left} -> {right} coverage drift: {violation.get('coverage')} {violation.get('reason')} {values}",
                    "artifact": str(path),
                    "coverage": violation.get("coverage"),
                    "reason": violation.get("reason"),
                    "values": list(violation.get("values") or []),
                }
            )

    return {
        "schema_version": "skillbench.pack-review-ci-result.v1",
        "passed": not failures,
        "report_path": str(report_path),
        "review_dir": str(root),
        "validation_count": len(validations),
        "comparison_count": len(comparisons),
        "validations": validations,
        "comparisons": comparisons,
        "failures": failures,
        "artifacts": {"pack_review_ci_result_json": str(report_path)},
    }


def write_pack_review_ci_result(review_dir: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    result = build_pack_review_ci_result(review_dir, output_path=output_path)
    write_json(result["report_path"], result)
    return result
