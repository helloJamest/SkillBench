from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .config import SkillBenchConfig, make_run_id, resolve_skill_file
from .lift import run_lift
from .observability.logging_io import ensure_dir, read_json, update_latest_pointer
from .reports.matrix import build_harness_matrix_report, write_harness_matrix_report
from .runners import AGENT_RUNNERS


def run_harness_matrix(
    skill_path: str | Path,
    eval_set_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    harnesses: list[str] | None = None,
    baseline_skill_path: str | Path | None = None,
    config: SkillBenchConfig | None = None,
    mode_override: str | None = None,
    min_lift: float = 0.1,
    bootstrap_samples: int = 500,
    harness_costs: dict[str, float] | None = None,
    min_total_lift: float | None = None,
    min_mean_case_lift: float | None = None,
    require_all_pass: bool = False,
    case_ids: list[str] | None = None,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    case_mode: str | None = None,
    limit: int | None = None,
) -> dict:
    config = config or SkillBenchConfig.from_env()
    skill_file = resolve_skill_file(skill_path)
    selected_harnesses = list(harnesses or AGENT_RUNNERS)
    _validate_harnesses(selected_harnesses)
    run_id = make_run_id("matrix")
    output_root = Path(output_dir) if output_dir else config.output_root
    run_dir = ensure_dir(output_root / run_id if output_root.name != run_id else output_root)
    update_latest_pointer(output_root, run_dir)

    results = []
    for harness in selected_harnesses:
        harness_config = replace(config, output_root=run_dir / harness, agent_runner=harness)
        result = run_lift(
            skill_file,
            eval_set_path=eval_set_path,
            output_dir=run_dir / harness,
            baseline_skill_path=baseline_skill_path,
            config=harness_config,
            mode_override=mode_override,
            min_lift=min_lift,
            bootstrap_samples=bootstrap_samples,
            case_ids=case_ids,
            include_tags=include_tags,
            exclude_tags=exclude_tags,
            case_mode=case_mode,
            limit=limit,
        )
        result["runner_name"] = harness
        result["latency"] = _lift_latency_summary(result)
        if harness_costs and harness in harness_costs:
            result["estimated_cost_usd"] = harness_costs[harness]
        results.append(result)

    eval_set_id = results[0].get("eval_set_id") if results else None
    matrix = build_harness_matrix_report(
        run_id=run_id,
        skill_path=str(skill_file),
        eval_set_id=eval_set_id,
        harness_results=results,
        harness_costs=harness_costs,
        min_total_lift=min_total_lift,
        min_mean_case_lift=min_mean_case_lift,
        require_all_pass=require_all_pass,
    )
    report_path = write_harness_matrix_report(matrix, run_dir / "matrix_report.json")
    matrix["artifacts"] = {"matrix_report_json": str(report_path)}
    write_harness_matrix_report(matrix, report_path)
    return matrix


def _validate_harnesses(harnesses: list[str]) -> None:
    for harness in harnesses:
        if harness not in AGENT_RUNNERS:
            raise ValueError(f"Unsupported harness: {harness}")


def _lift_latency_summary(result: dict) -> dict:
    baseline = _report_elapsed(result.get("artifacts", {}).get("baseline_report_json") or result.get("baseline", {}).get("report_json"))
    candidate = _report_elapsed(result.get("artifacts", {}).get("candidate_report_json") or result.get("candidate", {}).get("report_json"))
    return {
        "baseline_elapsed_sec": baseline["elapsed_sec"],
        "candidate_elapsed_sec": candidate["elapsed_sec"],
        "baseline_case_count": baseline["case_count"],
        "candidate_case_count": candidate["case_count"],
    }


def _report_elapsed(path_value) -> dict[str, float | int]:
    if not path_value:
        return {"elapsed_sec": 0.0, "case_count": 0}
    try:
        report = read_json(path_value)
    except Exception:
        return {"elapsed_sec": 0.0, "case_count": 0}
    elapsed_values = []
    for case in report.get("case_results", []):
        behavior = (case.get("evidence") or {}).get("behavior") or {}
        if "elapsed_sec" in behavior:
            elapsed_values.append(float(behavior.get("elapsed_sec") or 0.0))
    return {
        "elapsed_sec": round(sum(elapsed_values), 3),
        "case_count": len(elapsed_values),
    }
