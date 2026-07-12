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
    harness_costs: dict[str, float] | None = None,
    min_total_lift: float | None = None,
    min_mean_case_lift: float | None = None,
    require_all_pass: bool = False,
) -> dict[str, Any]:
    harnesses = [_summarize_harness(item, harness_costs or {}) for item in harness_results]
    ranking = sorted(
        [
            {
                "rank": 0,
                "runner_name": item["runner_name"],
                "total_lift": item["total_lift"],
                "mean_case_lift": item["mean_case_lift"],
                "verdict": item["verdict"],
                "lift_report_json": item["lift_report_json"],
                "confidence_summary": item["confidence_summary"],
                "efficiency": item["efficiency"],
            }
            for item in harnesses
        ],
        key=lambda item: (-float(item["total_lift"]), -float(item["mean_case_lift"]), str(item["runner_name"])),
    )
    for index, item in enumerate(ranking, start=1):
        item["rank"] = index
    efficiency_ranking = _build_efficiency_ranking(harnesses)
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
        "efficiency_ranking": efficiency_ranking,
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


def _summarize_harness(result: dict[str, Any], harness_costs: dict[str, float]) -> dict[str, Any]:
    runner_name = result["runner_name"]
    cost = result.get("estimated_cost_usd")
    if cost is None:
        cost = harness_costs.get(str(runner_name))
    latency = _latency_summary(result.get("latency", {}))
    confidence = _confidence_summary(result.get("confidence", {}))
    total_lift = result.get("total_lift", 0.0)
    mean_case_lift = result.get("mean_case_lift", 0.0)
    efficiency = _efficiency_summary(total_lift, mean_case_lift, cost, latency)
    return {
        "runner_name": runner_name,
        "verdict": result.get("verdict"),
        "total_lift": total_lift,
        "mean_case_lift": mean_case_lift,
        "baseline_total_score": result.get("baseline", {}).get("total_score"),
        "candidate_total_score": result.get("candidate", {}).get("total_score"),
        "baseline_worst_case_id": result.get("baseline", {}).get("worst_case_id"),
        "candidate_worst_case_id": result.get("candidate", {}).get("worst_case_id"),
        "dimension_lifts": result.get("dimension_lifts", {}),
        "confidence_summary": confidence,
        "latency": latency,
        "efficiency": efficiency,
        "lift_report_json": result.get("artifacts", {}).get("lift_report_json", ""),
    }


def _confidence_summary(confidence: dict[str, Any]) -> dict[str, Any]:
    ci95 = confidence.get("mean_case_lift_ci95") or {}
    low = ci95.get("low")
    high = ci95.get("high")
    return {
        "method": confidence.get("method"),
        "samples": confidence.get("samples"),
        "mean_case_lift_ci95_low": low,
        "mean_case_lift_ci95_high": high,
        "mean_case_lift_ci95_width": round(float(high) - float(low), 3) if low is not None and high is not None else None,
    }


def _latency_summary(latency: dict[str, Any]) -> dict[str, Any]:
    baseline = float(latency.get("baseline_elapsed_sec", 0.0) or 0.0)
    candidate = float(latency.get("candidate_elapsed_sec", 0.0) or 0.0)
    baseline_count = int(latency.get("baseline_case_count", 0) or 0)
    candidate_count = int(latency.get("candidate_case_count", 0) or 0)
    total = round(baseline + candidate, 3)
    total_count = baseline_count + candidate_count
    return {
        "baseline_elapsed_sec": round(baseline, 3),
        "candidate_elapsed_sec": round(candidate, 3),
        "total_elapsed_sec": total,
        "baseline_case_count": baseline_count,
        "candidate_case_count": candidate_count,
        "total_case_count": total_count,
        "mean_case_elapsed_sec": round(total / total_count, 3) if total_count else None,
    }


def _efficiency_summary(total_lift: object, mean_case_lift: object, cost: object, latency: dict[str, Any]) -> dict[str, Any]:
    total = float(total_lift or 0.0)
    mean = float(mean_case_lift or 0.0)
    cost_value = float(cost) if cost is not None else None
    elapsed = float(latency.get("total_elapsed_sec", 0.0) or 0.0)
    return {
        "estimated_cost_usd": round(cost_value, 6) if cost_value is not None else None,
        "lift_per_usd": round(total / cost_value, 3) if cost_value and cost_value > 0 else None,
        "mean_case_lift_per_usd": round(mean / cost_value, 3) if cost_value and cost_value > 0 else None,
        "lift_per_second": round(total / elapsed, 3) if elapsed > 0 else None,
        "mean_case_lift_per_second": round(mean / elapsed, 3) if elapsed > 0 else None,
    }


def _build_efficiency_ranking(harnesses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = [
        {
            "rank": 0,
            "runner_name": item["runner_name"],
            "estimated_cost_usd": item["efficiency"].get("estimated_cost_usd"),
            "lift_per_usd": item["efficiency"].get("lift_per_usd"),
            "lift_per_second": item["efficiency"].get("lift_per_second"),
            "total_elapsed_sec": item["latency"].get("total_elapsed_sec"),
        }
        for item in harnesses
    ]
    items.sort(
        key=lambda item: (
            item["lift_per_usd"] is None,
            -(float(item["lift_per_usd"]) if item["lift_per_usd"] is not None else 0.0),
            item["lift_per_second"] is None,
            -(float(item["lift_per_second"]) if item["lift_per_second"] is not None else 0.0),
            str(item["runner_name"]),
        )
    )
    for index, item in enumerate(items, start=1):
        item["rank"] = index
    return items
