from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from ..observability.logging_io import write_json
from ..schemas import EvalReport


def build_lift_report(
    baseline: EvalReport,
    candidate: EvalReport,
    *,
    run_id: str,
    skill_path: str,
    baseline_skill_path: str,
    min_lift: float = 0.1,
    bootstrap_samples: int = 500,
) -> dict[str, Any]:
    baseline_cases = {case.case_id: case for case in baseline.case_results}
    case_lifts = []
    for case in candidate.case_results:
        baseline_case = baseline_cases.get(case.case_id)
        baseline_score = baseline_case.score if baseline_case else 0.0
        case_lifts.append(
            {
                "case_id": case.case_id,
                "baseline_score": baseline_score,
                "candidate_score": case.score,
                "delta": round(float(case.score) - float(baseline_score), 3),
                "baseline_failed_dimensions": list(baseline_case.failed_dimensions) if baseline_case else [],
                "candidate_failed_dimensions": list(case.failed_dimensions),
            }
        )

    dimensions = sorted(set(baseline.dimension_scores) | set(candidate.dimension_scores))
    total_lift = round(float(candidate.total_score) - float(baseline.total_score), 3)
    case_deltas = [float(item["delta"]) for item in case_lifts]
    confidence = _bootstrap_ci(case_deltas, bootstrap_samples)
    return {
        "schema_version": "skillbench.lift.v1",
        "run_id": run_id,
        "skill_path": skill_path,
        "baseline_skill_path": baseline_skill_path,
        "eval_set_id": candidate.eval_set_id,
        "verdict": _verdict(total_lift, min_lift),
        "total_lift": total_lift,
        "mean_case_lift": round(sum(case_deltas) / len(case_deltas), 3) if case_deltas else 0.0,
        "min_lift": min_lift,
        "confidence": {
            "method": "deterministic-bootstrap-over-case-deltas",
            "samples": bootstrap_samples,
            "mean_case_lift_ci95": confidence,
        },
        "baseline": {
            "label": "without-skill",
            "run_id": baseline.run_id,
            "candidate_id": baseline.candidate_id,
            "total_score": baseline.total_score,
            "grade": baseline.grade,
            "worst_case_id": baseline.worst_case_id,
            "report_json": baseline.artifacts.get("report_json", ""),
        },
        "candidate": {
            "label": "with-skill",
            "run_id": candidate.run_id,
            "candidate_id": candidate.candidate_id,
            "total_score": candidate.total_score,
            "grade": candidate.grade,
            "worst_case_id": candidate.worst_case_id,
            "report_json": candidate.artifacts.get("report_json", ""),
        },
        "dimension_lifts": {
            dimension: round(float(candidate.dimension_scores.get(dimension, 0.0)) - float(baseline.dimension_scores.get(dimension, 0.0)), 3)
            for dimension in dimensions
        },
        "case_lifts": case_lifts,
    }


def write_lift_report(report: dict[str, Any], path: str | Path) -> Path:
    return write_json(path, report)


def _verdict(total_lift: float, min_lift: float) -> str:
    if total_lift >= abs(min_lift):
        return "HELPS"
    if total_lift <= -abs(min_lift):
        return "HARMS"
    return "PLACEBO"


def _bootstrap_ci(values: list[float], samples: int) -> dict[str, float | None]:
    if not values:
        return {"low": None, "high": None}
    if samples <= 0:
        mean = round(sum(values) / len(values), 3)
        return {"low": mean, "high": mean}
    rng = random.Random(1729)
    means = []
    count = len(values)
    for _ in range(samples):
        draw = [values[rng.randrange(count)] for _ in range(count)]
        means.append(sum(draw) / count)
    means.sort()
    low = means[int((len(means) - 1) * 0.025)]
    high = means[int((len(means) - 1) * 0.975)]
    return {"low": round(low, 3), "high": round(high, 3)}
