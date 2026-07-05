from __future__ import annotations

from pathlib import Path
from typing import Any

from .cases.loader import load_eval_set_data
from .config import SkillBenchConfig, make_run_id
from .evaluate_skill import run_evaluation
from .observability.logging_io import ensure_dir, update_latest_pointer, write_json


def discover_benchmark_fixtures(fixtures_dir: str | Path) -> list[tuple[str, Path]]:
    root = Path(fixtures_dir)
    if not root.exists():
        raise FileNotFoundError(f"Benchmark fixtures directory not found: {root}")
    fixtures = []
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        skill_path = child / "SKILL.md"
        if child.is_dir() and skill_path.exists():
            fixtures.append((child.name, skill_path))
    if not fixtures:
        raise ValueError(f"No benchmark fixtures containing SKILL.md found in: {root}")
    return fixtures


def run_benchmark(
    fixtures_dir: str | Path,
    eval_set_path: str | Path,
    output_dir: str | Path | None = None,
    config: SkillBenchConfig | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    config = config or SkillBenchConfig.from_env(output_dir or ".skillbench/benchmarks")
    output_root = ensure_dir(output_dir or config.output_root)
    run_id = run_id or make_run_id("benchmark")
    benchmark_dir = ensure_dir(output_root / run_id if output_root.name != run_id else output_root)
    eval_set = load_eval_set_data(eval_set_path)

    fixture_summaries = []
    for fixture_id, skill_path in discover_benchmark_fixtures(fixtures_dir):
        report = run_evaluation(
            skill_path,
            eval_set_path=eval_set_path,
            output_dir=benchmark_dir / "fixtures" / fixture_id,
            run_id=fixture_id,
            candidate_id=fixture_id,
            config=config,
        )
        fixture_summaries.append(
            {
                "fixture_id": fixture_id,
                "skill_path": str(skill_path),
                "run_id": report.run_id,
                "report_json": report.artifacts["report_json"],
                "total_score": report.total_score,
                "grade": report.grade,
                "accepted": report.accepted,
                "worst_case_id": report.worst_case_id,
                "dimension_scores": report.dimension_scores,
            }
        )

    ranking = [
        {
            "rank": index + 1,
            "fixture_id": fixture["fixture_id"],
            "total_score": fixture["total_score"],
            "grade": fixture["grade"],
            "accepted": fixture["accepted"],
            "worst_case_id": fixture["worst_case_id"],
        }
        for index, fixture in enumerate(
            sorted(fixture_summaries, key=lambda item: (-float(item["total_score"]), str(item["fixture_id"])))
        )
    ]

    result = {
        "benchmark_id": eval_set.id,
        "run_id": run_id,
        "fixtures_dir": str(fixtures_dir),
        "eval_set_path": str(eval_set_path),
        "fixture_count": len(fixture_summaries),
        "fixtures": fixture_summaries,
        "ranking": ranking,
        "artifacts": {},
    }
    benchmark_path = benchmark_dir / "benchmark.json"
    result["artifacts"] = {"benchmark_json": str(benchmark_path)}
    write_json(benchmark_path, result)
    update_latest_pointer(output_root, benchmark_dir)
    return result
