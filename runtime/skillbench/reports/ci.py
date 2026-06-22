from __future__ import annotations

from pathlib import Path
from typing import Any

from ..observability.logging_io import write_json
from ..schemas import EvalReport


def build_ci_result(
    report: EvalReport,
    min_score: float,
    min_safety: float,
    baseline: dict[str, Any] | None = None,
    fail_on_regression: bool = False,
    max_regression: float = 0.0,
) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    safety = report.dimension_scores.get("safety", 10.0)
    if report.total_score < min_score:
        failures.append(
            {
                "type": "threshold",
                "message": f"total_score {report.total_score:.3f} below min_score {min_score:.3f}",
            }
        )
    if safety < min_safety:
        failures.append(
            {
                "type": "threshold",
                "message": f"safety {safety:.3f} below min_safety {min_safety:.3f}",
            }
        )
    regression = None
    if baseline:
        regression = _build_regression(report, baseline)
        if fail_on_regression:
            if regression["total_delta"] < -abs(max_regression):
                failures.append(
                    {
                        "type": "regression",
                        "message": (
                            f"total_score regressed by {regression['total_delta']:.3f} "
                            f"from baseline {baseline.get('run_id', 'baseline')}"
                        ),
                    }
                )
            for dimension, delta in regression["dimension_deltas"].items():
                if delta < -abs(max_regression):
                    failures.append(
                        {
                            "type": "regression",
                            "message": (
                                f"{dimension} regressed by {delta:.3f} "
                                f"from baseline {baseline.get('run_id', 'baseline')}"
                            ),
                        }
                    )
    return {
        "passed": not failures,
        "total_score": report.total_score,
        "safety_score": safety,
        "thresholds": {
            "min_score": min_score,
            "min_safety": min_safety,
        },
        "failures": failures,
        "report_path": report.artifacts.get("report_json", "report.json"),
        "worst_case_id": report.worst_case_id,
        "baseline": baseline_summary(baseline) if baseline else None,
        "regression": regression,
    }


def write_ci_result(result: dict[str, Any], path: str | Path) -> Path:
    return write_json(path, result)


def baseline_summary(baseline: dict[str, Any] | None) -> dict[str, Any] | None:
    if not baseline:
        return None
    return {
        "run_id": baseline.get("run_id"),
        "total_score": baseline.get("total_score"),
        "dimension_scores": baseline.get("dimension_scores", {}),
        "report_path": baseline.get("artifacts", {}).get("report_json"),
    }


def _build_regression(report: EvalReport, baseline: dict[str, Any]) -> dict[str, Any]:
    baseline_dimensions = baseline.get("dimension_scores", {})
    dimensions = sorted(set(report.dimension_scores) | set(baseline_dimensions))
    return {
        "baseline_run_id": baseline.get("run_id"),
        "current_run_id": report.run_id,
        "total_delta": round(float(report.total_score) - float(baseline.get("total_score", 0.0)), 3),
        "dimension_deltas": {
            dimension: round(
                float(report.dimension_scores.get(dimension, 0.0)) - float(baseline_dimensions.get(dimension, 0.0)),
                3,
            )
            for dimension in dimensions
        },
    }
