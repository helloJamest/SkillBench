from __future__ import annotations

from pathlib import Path
from typing import Any

from ..observability.logging_io import write_json


def build_harness_matrix_report(
    *,
    run_id: str,
    skill_path: str,
    eval_set_id: str | None,
    harness_results: list[dict[str, Any]],
    min_total_lift: float | None = None,
    min_mean_case_lift: float | None = None,
    require_all_pass: bool = False,
) -> dict[str, Any]:
    harnesses = [_summarize_harness(item) for item in harness_results]
    ranking = sorted(
        [
            {
                "rank": 0,
                "runner_name": item["runner_name"],
                "total_lift": item["total_lift"],
                "mean_case_lift": item["mean_case_lift"],
                "verdict": item["verdict"],
                "lift_report_json": item["lift_report_json"],
            }
            for item in harnesses
        ],
        key=lambda item: (-float(item["total_lift"]), -float(item["mean_case_lift"]), str(item["runner_name"])),
    )
    for index, item in enumerate(ranking, start=1):
        item["rank"] = index
    gate = build_harness_matrix_gate(
        harnesses,
        min_total_lift=min_total_lift,
        min_mean_case_lift=min_mean_case_lift,
        require_all_pass=require_all_pass,
    )
    return {
        "schema_version": "skillbench.harness-matrix.v1",
        "run_id": run_id,
        "skill_path": skill_path,
        "eval_set_id": eval_set_id,
        "harness_count": len(harnesses),
        "best_harness": ranking[0]["runner_name"] if ranking else None,
        "gate": gate,
        "harnesses": harnesses,
        "ranking": ranking,
    }


def build_harness_matrix_gate(
    harnesses: list[dict[str, Any]],
    *,
    min_total_lift: float | None = None,
    min_mean_case_lift: float | None = None,
    require_all_pass: bool = False,
) -> dict[str, Any]:
    checks = [_harness_gate_check(item, min_total_lift=min_total_lift, min_mean_case_lift=min_mean_case_lift) for item in harnesses]
    passing = [item for item in checks if item["passed"]]
    if not checks:
        passed = False
    elif require_all_pass:
        passed = len(passing) == len(checks)
    else:
        passed = bool(passing)
    failures = [failure for item in checks for failure in item["failures"]]
    return {
        "passed": passed,
        "mode": "all" if require_all_pass else "any",
        "thresholds": {
            "min_total_lift": min_total_lift,
            "min_mean_case_lift": min_mean_case_lift,
            "require_all_pass": require_all_pass,
        },
        "checked_harnesses": [item["runner_name"] for item in checks],
        "passing_harnesses": [item["runner_name"] for item in passing],
        "failures": [] if passed and not require_all_pass else failures,
    }


def write_harness_matrix_report(report: dict[str, Any], path: str | Path) -> Path:
    return write_json(path, report)


def _harness_gate_check(
    harness: dict[str, Any],
    *,
    min_total_lift: float | None,
    min_mean_case_lift: float | None,
) -> dict[str, Any]:
    runner_name = str(harness.get("runner_name", ""))
    failures: list[dict[str, Any]] = []
    total_lift = float(harness.get("total_lift", 0.0))
    mean_case_lift = float(harness.get("mean_case_lift", 0.0))
    if min_total_lift is not None and total_lift < min_total_lift:
        failures.append(
            {
                "type": "total_lift",
                "runner_name": runner_name,
                "message": f"{runner_name} total_lift {total_lift:.3f} below min_total_lift {min_total_lift:.3f}",
            }
        )
    if min_mean_case_lift is not None and mean_case_lift < min_mean_case_lift:
        failures.append(
            {
                "type": "mean_case_lift",
                "runner_name": runner_name,
                "message": f"{runner_name} mean_case_lift {mean_case_lift:.3f} below min_mean_case_lift {min_mean_case_lift:.3f}",
            }
        )
    return {
        "runner_name": runner_name,
        "passed": not failures,
        "failures": failures,
    }


def _summarize_harness(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "runner_name": result["runner_name"],
        "verdict": result.get("verdict"),
        "total_lift": result.get("total_lift", 0.0),
        "mean_case_lift": result.get("mean_case_lift", 0.0),
        "baseline_total_score": result.get("baseline", {}).get("total_score"),
        "candidate_total_score": result.get("candidate", {}).get("total_score"),
        "baseline_worst_case_id": result.get("baseline", {}).get("worst_case_id"),
        "candidate_worst_case_id": result.get("candidate", {}).get("worst_case_id"),
        "dimension_lifts": result.get("dimension_lifts", {}),
        "lift_report_json": result.get("artifacts", {}).get("lift_report_json", ""),
    }
