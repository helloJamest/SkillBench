from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

from .config import SkillBenchConfig, make_run_id
from .evaluate_skill import run_evaluation
from .observability.logging_io import ensure_dir, write_json


def run_calibration(
    skill_path: str | Path,
    eval_set_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    samples: int = 3,
    max_total_range: float = 0.25,
    config: SkillBenchConfig | None = None,
    mode_override: str | None = None,
    case_ids: list[str] | None = None,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    case_mode: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    sample_count = max(1, int(samples))
    config = config or SkillBenchConfig.from_env(output_dir)
    output_root = ensure_dir(output_dir or config.output_root)
    run_id = make_run_id("calibration")
    calibration_dir = ensure_dir(output_root / run_id if output_root.name != run_id else output_root)

    reports = []
    for index in range(sample_count):
        sample_dir = calibration_dir / f"sample_{index + 1:03d}"
        report = run_evaluation(
            skill_path,
            eval_set_path=eval_set_path,
            output_dir=sample_dir,
            run_id=sample_dir.name,
            candidate_id=f"candidate_calibration_{index + 1:03d}",
            config=config,
            mode_override=mode_override,
            case_ids=case_ids,
            include_tags=include_tags,
            exclude_tags=exclude_tags,
            case_mode=case_mode,
            limit=limit,
        )
        reports.append(
            {
                "run_id": report.run_id,
                "total_score": report.total_score,
                "report_json": report.artifacts["report_json"],
                "dimension_scores": report.dimension_scores,
                "case_scores": {case.case_id: case.score for case in report.case_results},
            }
        )

    total_summary = _score_summary([report["total_score"] for report in reports])
    dimension_names = sorted({name for report in reports for name in report["dimension_scores"]})
    dimensions = {
        name: _score_summary([report["dimension_scores"].get(name, 0.0) for report in reports])
        for name in dimension_names
    }
    case_ids_seen = sorted({case_id for report in reports for case_id in report["case_scores"]})
    cases = {
        case_id: _score_summary([report["case_scores"].get(case_id, 0.0) for report in reports])
        for case_id in case_ids_seen
    }
    stable = (
        total_summary["range"] <= max_total_range
        and all(summary["range"] <= max_total_range for summary in dimensions.values())
        and all(summary["range"] <= max_total_range for summary in cases.values())
    )
    result = {
        "run_id": run_id,
        "stable": stable,
        "samples": sample_count,
        "max_total_range": max_total_range,
        "total_score": total_summary,
        "dimensions": dimensions,
        "cases": cases,
        "reports": reports,
        "artifacts": {},
    }
    calibration_path = write_json(calibration_dir / "calibration.json", result)
    result["artifacts"] = {"calibration_json": str(calibration_path)}
    write_json(calibration_path, result)
    return result


def _score_summary(scores: list[float]) -> dict[str, float | list[float]]:
    values = [round(float(score), 3) for score in scores]
    if not values:
        return {"values": [], "mean": 0.0, "min": 0.0, "max": 0.0, "range": 0.0, "stdev": 0.0}
    minimum = min(values)
    maximum = max(values)
    return {
        "values": values,
        "mean": round(statistics.fmean(values), 3),
        "min": minimum,
        "max": maximum,
        "range": round(maximum - minimum, 3),
        "stdev": round(statistics.pstdev(values), 3) if len(values) > 1 else 0.0,
    }
