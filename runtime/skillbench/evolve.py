from __future__ import annotations

from pathlib import Path

from .config import SkillBenchConfig, make_run_id, read_skill, resolve_skill_file
from .cases.selection import CaseSelection, select_eval_cases
from .evaluate_skill import load_eval_set, run_evaluation
from .observability.comet_logger import CometLogger
from .observability.logging_io import ensure_dir, update_latest_pointer, write_json
from .optimizers import AcceptPolicy, CandidatePool
from .optimizers.gepa_adapter import GepaAdapter
from .schemas import EvolutionReport, EvolutionStep, Reflection


def run_evolution(
    skill_path: str | Path,
    eval_set_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    rounds: int = 3,
    config: SkillBenchConfig | None = None,
    case_ids: list[str] | None = None,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    case_mode: str | None = None,
    limit: int | None = None,
) -> EvolutionReport:
    config = config or SkillBenchConfig.from_env()
    skill_file = resolve_skill_file(skill_path)
    skill_text = read_skill(skill_file)
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
    run_id = make_run_id("evo")
    output_root = Path(output_dir) if output_dir else config.output_root
    run_dir = ensure_dir(output_root / run_id if output_root.name != run_id else output_root)
    update_latest_pointer(output_root, run_dir)

    pool = CandidatePool(run_dir)
    initial = pool.add_initial(skill_text)
    accept_policy = AcceptPolicy(config)
    optimizer = GepaAdapter()
    steps: list[EvolutionStep] = []
    reports_by_candidate = {}

    comet = CometLogger(
        run_dir,
        enabled=config.comet_enabled,
        project_name=config.comet_project_name,
        workspace=config.comet_workspace,
        experiment_name=f"skillbench/{run_id}",
    )
    comet.log_parameters({"skill_path": str(skill_file), "eval_set_id": eval_set.id, "rounds": rounds})
    selection_kwargs = {
        "case_ids": case_ids,
        "include_tags": include_tags,
        "exclude_tags": exclude_tags,
        "case_mode": case_mode,
        "limit": limit,
    }

    for round_index in range(rounds):
        selected = pool.select()
        selected_report = reports_by_candidate.get(selected.id)
        if selected_report is None:
            selected_report = run_evaluation(
                selected.path,
                eval_set_path=eval_set_path,
                output_dir=run_dir / f"round_{round_index:03d}" / "selected",
                run_id="selected",
                candidate_id=selected.id,
                config=config,
                **selection_kwargs,
            )
            reports_by_candidate[selected.id] = selected_report
            pool.update(selected.id, score=selected_report.total_score)

        reflection = reflect(selected.id, selected_report)
        reflection_path = write_json(run_dir / f"round_{round_index:03d}" / "reflection.json", reflection)

        next_candidate_id = f"candidate_{len(pool.candidates):03d}"
        selected_text = Path(selected.path).read_text(encoding="utf-8")
        mutated_text, mutation = optimizer.mutate(selected_text, reflection, selected.id, next_candidate_id)
        mutation_path = write_json(run_dir / f"round_{round_index:03d}" / "mutation.json", mutation)
        mutated = pool.add_candidate(mutated_text, parent_id=selected.id, round_index=round_index + 1)

        mutated_report = run_evaluation(
            mutated.path,
            eval_set_path=eval_set_path,
            output_dir=run_dir / f"round_{round_index:03d}" / "mutated",
            run_id="mutated",
            candidate_id=mutated.id,
            config=config,
            **selection_kwargs,
        )
        reports_by_candidate[mutated.id] = mutated_report
        pool.update(mutated.id, score=mutated_report.total_score)

        decision = accept_policy.decide(selected_report, mutated_report)
        pool.update(mutated.id, accepted=decision.accepted)
        if decision.accepted:
            pool.update(selected.id, accepted=True)

        decision_path = write_json(run_dir / f"round_{round_index:03d}" / "decision.json", decision)
        step = EvolutionStep(
            round_index=round_index,
            selected_candidate_id=selected.id,
            report_path=str(Path(mutated_report.artifacts["report_json"])),
            reflection_path=str(reflection_path),
            mutation_path=str(mutation_path),
            decision=decision,
        )
        steps.append(step)

        comet.log_metric("selected_total_score", selected_report.total_score, step=round_index)
        comet.log_metric("mutated_total_score", mutated_report.total_score, step=round_index)
        comet.log_metric("accepted", 1.0 if decision.accepted else 0.0, step=round_index)
        comet.log_asset(decision_path)
        comet.log_asset(reflection_path)
        comet.log_asset(mutation_path)

    best = pool.select()
    evolution = EvolutionReport(
        run_id=run_id,
        skill_path=str(skill_file),
        eval_set_id=eval_set.id,
        best_candidate_id=best.id,
        steps=steps,
        candidates=pool.candidates,
        artifacts={
            "evolution_json": str(run_dir / "evolution.json"),
            "candidates_json": str(run_dir / "candidates.json"),
        },
    )
    evolution_path = write_json(run_dir / "evolution.json", evolution)
    comet.log_asset(evolution_path)
    comet.end()
    return evolution


def reflect(candidate_id: str, report) -> Reflection:
    low_cases = sorted(report.case_results, key=lambda item: item.score)[:3]
    root_causes = []
    for case in low_cases:
        for dimension in case.failed_dimensions or ["overall"]:
            root_causes.append(
                {
                    "dimension": dimension,
                    "cases": [case.case_id],
                    "cause": case.rationale,
                    "repair_intent": case.suggestion,
                }
            )
    if not root_causes and low_cases:
        root_causes.append(
            {
                "dimension": "overall",
                "cases": [low_cases[0].case_id],
                "cause": "No dimension failed below threshold; preserve current structure.",
                "repair_intent": "Avoid unnecessary mutation.",
            }
        )
    summary = f"Candidate {candidate_id} worst case is {report.worst_case_id}; {len(root_causes)} repair signal(s) extracted."
    return Reflection(candidate_id=candidate_id, root_causes=root_causes, worst_case_id=report.worst_case_id, summary=summary)
