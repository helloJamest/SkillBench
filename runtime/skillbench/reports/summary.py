from __future__ import annotations

from pathlib import Path

from ..observability.logging_io import ensure_dir
from ..schemas import EvalReport


def write_summary(report: EvalReport, path: str | Path) -> Path:
    target = Path(path)
    ensure_dir(target.parent)
    lines = [
        f"# SkillBench Report: {report.run_id}",
        "",
        f"- Candidate: `{report.candidate_id}`",
        f"- Skill: `{report.skill_path}`",
        f"- Eval set: `{report.eval_set_id}`",
        f"- Total score: `{report.total_score}`",
        f"- Grade: `{report.grade}`",
        f"- Worst case: `{report.worst_case_id}`",
        "",
        "## Dimension Scores",
        "",
        "| Dimension | Score |",
        "| --- | ---: |",
    ]
    for dimension, score in sorted(report.dimension_scores.items()):
        lines.append(f"| `{dimension}` | {score} |")
    lines.extend(["", "## Cases", "", "| Case | Score | Failed Dimensions |", "| --- | ---: | --- |"])
    for case in report.case_results:
        failed = ", ".join(case.failed_dimensions) if case.failed_dimensions else ""
        lines.append(f"| `{case.case_id}` | {case.score} | {failed} |")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target

