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
    return {
        "schema_version": "skillbench.harness-matrix.v1",
        "run_id": run_id,
        "skill_path": skill_path,
        "eval_set_id": eval_set_id,
        "harness_count": len(harnesses),
        "best_harness": ranking[0]["runner_name"] if ranking else None,
        "harnesses": harnesses,
        "ranking": ranking,
    }


def write_harness_matrix_report(report: dict[str, Any], path: str | Path) -> Path:
    return write_json(path, report)


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
