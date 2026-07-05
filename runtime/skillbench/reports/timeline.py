from __future__ import annotations

from pathlib import Path
from typing import Any

from ..observability.logging_io import read_json, write_json
from ..schemas import to_dict


def build_evolution_timeline(evolution: Any, run_dir: str | Path) -> dict[str, Any]:
    run_path = Path(run_dir)
    data = to_dict(evolution)
    candidates = {str(candidate.get("id")): candidate for candidate in data.get("candidates", [])}
    rounds = []
    for step in data.get("steps", []):
        round_index = int(step.get("round_index", len(rounds)))
        decision = step.get("decision") or {}
        reflection = _read_json_or_empty(run_path, step.get("reflection_path"))
        mutation = _read_json_or_empty(run_path, step.get("mutation_path"))
        report = _read_json_or_empty(run_path, step.get("report_path"))
        selected_id = str(step.get("selected_candidate_id", ""))
        mutated_id = str(decision.get("candidate_id") or report.get("candidate_id") or "")
        selected = candidates.get(selected_id, {})
        mutated = candidates.get(mutated_id, {})
        rounds.append(
            {
                "round_index": round_index,
                "selected_candidate_id": selected_id,
                "mutated_candidate_id": mutated_id,
                "parent_candidate_id": decision.get("parent_candidate_id"),
                "selected_score": selected.get("score"),
                "mutated_score": mutated.get("score", report.get("total_score")),
                "score_delta": float(decision.get("score_delta", _score_delta(selected, mutated, report))),
                "accepted": bool(decision.get("accepted", False)),
                "worst_case_id": reflection.get("worst_case_id") or report.get("worst_case_id"),
                "reflection_summary": reflection.get("summary", ""),
                "root_causes": reflection.get("root_causes", []),
                "mutation_changed": bool(mutation.get("changed", False)),
                "mutation_summary": mutation.get("patch_summary", ""),
                "mutation_reasons": mutation.get("reasons", []),
                "decision_reasons": decision.get("reasons", []),
                "report_path": step.get("report_path", ""),
                "reflection_path": step.get("reflection_path", ""),
                "mutation_path": step.get("mutation_path", ""),
                "decision_path": str(run_path / f"round_{round_index:03d}" / "decision.json"),
            }
        )
    return {
        "run_id": data.get("run_id"),
        "skill_path": data.get("skill_path"),
        "eval_set_id": data.get("eval_set_id"),
        "best_candidate_id": data.get("best_candidate_id"),
        "round_count": len(rounds),
        "rounds": rounds,
    }


def write_evolution_timeline(timeline: dict[str, Any], path: str | Path) -> Path:
    return write_json(path, timeline)


def _read_json_or_empty(run_path: Path, path_value: object) -> dict[str, Any]:
    if not path_value:
        return {}
    path = Path(str(path_value))
    candidates = [path]
    if not path.is_absolute():
        candidates.append(run_path / path)
        candidates.append(Path.cwd() / path)
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            try:
                value = read_json(candidate)
            except Exception:
                return {}
            return value if isinstance(value, dict) else {}
    return {}


def _score_delta(selected: dict[str, Any], mutated: dict[str, Any], report: dict[str, Any]) -> float:
    selected_score = selected.get("score")
    mutated_score = mutated.get("score", report.get("total_score"))
    if selected_score is None or mutated_score is None:
        return 0.0
    return round(float(mutated_score) - float(selected_score), 3)
