from __future__ import annotations

from pathlib import Path

from .cases.selection import CaseSelection, select_eval_cases
from .config import SkillBenchConfig, make_run_id, resolve_skill_file
from .evaluate_skill import load_eval_set, run_evaluation
from .observability.logging_io import ensure_dir, update_latest_pointer
from .reports.lift import build_lift_report, write_lift_report


def run_lift(
    skill_path: str | Path,
    eval_set_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    baseline_skill_path: str | Path | None = None,
    config: SkillBenchConfig | None = None,
    mode_override: str | None = None,
    min_lift: float = 0.1,
    bootstrap_samples: int = 500,
    case_ids: list[str] | None = None,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    case_mode: str | None = None,
    limit: int | None = None,
) -> dict:
    config = config or SkillBenchConfig.from_env()
    skill_file = resolve_skill_file(skill_path)
    run_id = make_run_id("lift")
    output_root = Path(output_dir) if output_dir else config.output_root
    run_dir = ensure_dir(output_root / run_id if output_root.name != run_id else output_root)
    update_latest_pointer(output_root, run_dir)

    eval_set = load_eval_set(eval_set_path)
    eval_set = select_eval_cases(
        eval_set,
        CaseSelection(
            case_ids=list(case_ids or []),
            include_tags=list(include_tags or []),
            exclude_tags=list(exclude_tags or []),
            mode=case_mode,
            limit=limit,
        ),
    )
    selected_eval_set_path = write_selected_eval_set(run_dir, eval_set)
    baseline_skill = _baseline_skill(run_dir, baseline_skill_path)
    selection_kwargs = {
        "case_ids": case_ids,
        "include_tags": include_tags,
        "exclude_tags": exclude_tags,
        "case_mode": case_mode,
        "limit": limit,
    }

    baseline_report = run_evaluation(
        baseline_skill,
        eval_set_path=selected_eval_set_path,
        output_dir=run_dir / "without_skill",
        run_id="without-skill",
        candidate_id="without-skill",
        config=config,
        mode_override=mode_override,
        **selection_kwargs,
    )
    candidate_report = run_evaluation(
        skill_file,
        eval_set_path=selected_eval_set_path,
        output_dir=run_dir / "with_skill",
        run_id="with-skill",
        candidate_id="with-skill",
        config=config,
        mode_override=mode_override,
        **selection_kwargs,
    )

    lift_report = build_lift_report(
        baseline_report,
        candidate_report,
        run_id=run_id,
        skill_path=str(skill_file),
        baseline_skill_path=str(baseline_skill),
        min_lift=min_lift,
        bootstrap_samples=bootstrap_samples,
    )
    report_path = write_lift_report(lift_report, run_dir / "lift_report.json")
    lift_report["artifacts"] = {
        "lift_report_json": str(report_path),
        "baseline_report_json": baseline_report.artifacts["report_json"],
        "candidate_report_json": candidate_report.artifacts["report_json"],
        "eval_set_json": str(selected_eval_set_path),
    }
    write_lift_report(lift_report, report_path)
    return lift_report


def write_selected_eval_set(run_dir: Path, eval_set) -> Path:
    from .observability.logging_io import write_json

    return write_json(run_dir / "eval_set.json", eval_set)


def _baseline_skill(run_dir: Path, baseline_skill_path: str | Path | None) -> Path:
    if baseline_skill_path:
        return resolve_skill_file(baseline_skill_path)
    target = ensure_dir(run_dir / "baseline_skill") / "SKILL.md"
    target.write_text(
        "---\n"
        "name: no-skill-baseline\n"
        "description: Baseline document with no specialized SkillBench guidance.\n"
        "---\n\n"
        "# No Skill Baseline\n\n"
        "This baseline intentionally contains no task-specific workflow, trigger guidance, commands, or evaluation policy.\n",
        encoding="utf-8",
    )
    return target
