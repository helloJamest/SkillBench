from __future__ import annotations

from pathlib import Path
from typing import Any

from ..observability.logging_io import ensure_dir, read_json, resolve_run_dir


PR_COMMENT_MARKER = "<!-- skillbench-pr-comment -->"


def render_pr_comment(source: str | Path) -> str:
    path = resolve_run_dir(source)
    if path.is_file():
        return _render_file(path)

    matrix_path = path / "matrix_report.json"
    if matrix_path.exists():
        return _render_matrix(path, read_json(matrix_path))

    lift_path = path / "lift_report.json"
    if lift_path.exists():
        return _render_lift(path, read_json(lift_path))

    report_path = path / "report.json"
    if report_path.exists():
        ci_path = path / "ci_result.json"
        ci_result = read_json(ci_path) if ci_path.exists() else None
        return _render_eval(path, read_json(report_path), ci_result)

    ci_path = path / "ci_result.json"
    if ci_path.exists():
        return _render_ci_file(ci_path)

    raise FileNotFoundError(f"No SkillBench report artifact found in {path}")


def write_pr_comment(source: str | Path, output: str | Path) -> Path:
    target = Path(output)
    ensure_dir(target.parent)
    target.write_text(render_pr_comment(source).rstrip() + "\n", encoding="utf-8")
    return target


def _render_file(path: Path) -> str:
    name = path.name
    if name == "matrix_report.json":
        return _render_matrix(path.parent, read_json(path))
    if name == "lift_report.json":
        return _render_lift(path.parent, read_json(path))
    if name == "report.json":
        ci_path = path.parent / "ci_result.json"
        ci_result = read_json(ci_path) if ci_path.exists() else None
        return _render_eval(path.parent, read_json(path), ci_result)
    if name == "ci_result.json":
        return _render_ci_file(path)
    if path.suffix == ".json":
        return _render_json_file(path)
    raise FileNotFoundError(f"Unsupported SkillBench PR comment source: {path}")


def _render_ci_file(path: Path) -> str:
    ci_result = read_json(path)
    return _render_ci_payload(path, ci_result)


def _render_json_file(path: Path) -> str:
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise FileNotFoundError(f"Unsupported SkillBench JSON artifact for PR comment: {path}")
    if payload.get("schema_version") == "skillbench.harness-matrix.v1" or ("harnesses" in payload and "ranking" in payload):
        return _render_matrix(path.parent, payload)
    if "case_lifts" in payload and "total_lift" in payload:
        return _render_lift(path.parent, payload)
    if "passed" in payload and "report_path" in payload:
        return _render_ci_payload(path, payload)
    if "case_results" in payload and "total_score" in payload:
        return _render_eval(path.parent, payload, None)
    raise FileNotFoundError(f"Unsupported SkillBench JSON artifact for PR comment: {path}")


def _render_ci_payload(path: Path, ci_result: dict[str, Any]) -> str:
    report_path = _resolve_reference(ci_result.get("report_path"), path.parent)
    report = read_json(report_path) if report_path and report_path.exists() else {}
    run_dir = report_path.parent if report_path and report_path.exists() else path.parent
    return _render_eval(run_dir, report, ci_result)


def _render_matrix(run_dir: Path, report: dict[str, Any]) -> str:
    gate = report.get("gate") or {}
    status = "PASS" if gate.get("passed", True) else "FAIL"
    best_harness = report.get("best_harness") or "-"
    lines = [
        PR_COMMENT_MARKER,
        "## SkillBench Harness Matrix",
        "",
        f"Gate: **{status}** | Best harness: `{best_harness}` | Harnesses: `{report.get('harness_count', len(report.get('harnesses', [])))}`",
        f"Report: `{_artifact_name(run_dir, report.get('artifacts', {}).get('matrix_report_json'), 'matrix_report.json')}`",
        "",
        "### Ranking",
        "",
        "| Runner | Total Lift | Mean Case Lift | Verdict |",
        "| --- | ---: | ---: | --- |",
    ]
    ranking = report.get("ranking") or []
    if ranking:
        for item in ranking:
            lines.append(
                f"| {_cell(item.get('runner_name'))} | {_number(item.get('total_lift'), signed=True)} | "
                f"{_number(item.get('mean_case_lift'), signed=True)} | {_cell(item.get('verdict'))} |"
            )
    else:
        lines.append("| - | - | - | - |")

    lines.extend(["", "### Efficiency", "", "| Runner | Estimated Cost USD | Lift / USD | Lift / Second | CI95 Width |", "| --- | ---: | ---: | ---: | ---: |"])
    efficiency_rows = _matrix_efficiency_rows(report)
    if efficiency_rows:
        for item in efficiency_rows:
            lines.append(
                f"| {_cell(item.get('runner_name'))} | {_number(item.get('estimated_cost_usd'))} | "
                f"{_number(item.get('lift_per_usd'))} | {_number(item.get('lift_per_second'))} | "
                f"{_number(item.get('ci95_width'))} |"
            )
    else:
        lines.append("| - | - | - | - | - |")

    failures = gate.get("failures") or []
    lines.extend(["", "### Gate Failures", ""])
    if failures:
        lines.extend(f"- {_cell(failure.get('message', failure))}" for failure in failures[:10])
    else:
        passing = ", ".join(f"`{name}`" for name in gate.get("passing_harnesses", [])) or "None recorded"
        lines.append(f"- None. Passing harnesses: {passing}.")
    return "\n".join(lines)


def _render_lift(run_dir: Path, report: dict[str, Any]) -> str:
    baseline = report.get("baseline") or {}
    candidate = report.get("candidate") or {}
    confidence = (report.get("confidence") or {}).get("mean_case_lift_ci95") or {}
    lines = [
        PR_COMMENT_MARKER,
        "## SkillBench Lift",
        "",
        f"Verdict: **{_cell(report.get('verdict', '-'))}** | Total Lift: `{_number(report.get('total_lift'), signed=True)}` | Mean Case Lift: `{_number(report.get('mean_case_lift'), signed=True)}`",
        f"CI95: `{_number(confidence.get('low'), signed=True)} .. {_number(confidence.get('high'), signed=True)}`",
        f"Report: `{_artifact_name(run_dir, report.get('artifacts', {}).get('lift_report_json'), 'lift_report.json')}`",
        "",
        "| Side | Label | Total Score | Worst Case |",
        "| --- | --- | ---: | --- |",
        f"| Baseline | {_cell(baseline.get('label', 'without-skill'))} | {_number(baseline.get('total_score'))} | `{_cell(baseline.get('worst_case_id', '-'))}` |",
        f"| Candidate | {_cell(candidate.get('label', 'with-skill'))} | {_number(candidate.get('total_score'))} | `{_cell(candidate.get('worst_case_id', '-'))}` |",
    ]
    case_lifts = report.get("case_lifts") or []
    if case_lifts:
        worst = min(case_lifts, key=lambda item: float(item.get("delta", 0.0)))
        lines.extend(["", f"Worst case delta: `{_cell(worst.get('case_id'))}` `{_number(worst.get('delta'), signed=True)}`"])
    return "\n".join(lines)


def _render_eval(run_dir: Path, report: dict[str, Any], ci_result: dict[str, Any] | None = None) -> str:
    status = None
    if ci_result is not None:
        status = "PASS" if ci_result.get("passed") else "FAIL"
    title = "SkillBench CI" if ci_result is not None else "SkillBench Eval"
    total_score = report.get("total_score", ci_result.get("total_score") if ci_result else None)
    worst_case = report.get("worst_case_id", ci_result.get("worst_case_id") if ci_result else None)
    lines = [
        PR_COMMENT_MARKER,
        f"## {title}",
        "",
        f"Status: **{status or 'INFO'}** | Total Score: `{_number(total_score)}` | Worst Case: `{_cell(worst_case or '-')}`",
    ]
    if ci_result is not None:
        lines.append(f"Safety Score: `{_number(ci_result.get('safety_score'))}`")
    lines.extend(["", f"Report: `{_artifact_name(run_dir, (ci_result or {}).get('report_path') or report.get('artifacts', {}).get('report_json'), 'report.json')}`"])

    dimensions = report.get("dimension_scores") or {}
    if dimensions:
        lines.extend(["", "### Dimensions", "", "| Dimension | Score |", "| --- | ---: |"])
        for name, score in sorted(dimensions.items()):
            lines.append(f"| {_cell(name)} | {_number(score)} |")

    failures = (ci_result or {}).get("failures") or []
    if failures:
        lines.extend(["", "### Gate Failures", ""])
        lines.extend(f"- {_cell(failure.get('message', failure))}" for failure in failures[:10])
    return "\n".join(lines)


def _matrix_efficiency_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    by_runner = {item.get("runner_name"): item for item in report.get("harnesses", [])}
    rows: list[dict[str, Any]] = []
    for item in report.get("efficiency_ranking") or []:
        harness = by_runner.get(item.get("runner_name"), {})
        confidence = harness.get("confidence_summary") or {}
        rows.append(
            {
                "runner_name": item.get("runner_name"),
                "estimated_cost_usd": item.get("estimated_cost_usd"),
                "lift_per_usd": item.get("lift_per_usd"),
                "lift_per_second": item.get("lift_per_second"),
                "ci95_width": confidence.get("mean_case_lift_ci95_width"),
            }
        )
    if rows:
        return rows
    for harness in report.get("harnesses", []):
        efficiency = harness.get("efficiency") or {}
        confidence = harness.get("confidence_summary") or {}
        rows.append(
            {
                "runner_name": harness.get("runner_name"),
                "estimated_cost_usd": efficiency.get("estimated_cost_usd"),
                "lift_per_usd": efficiency.get("lift_per_usd"),
                "lift_per_second": efficiency.get("lift_per_second"),
                "ci95_width": confidence.get("mean_case_lift_ci95_width"),
            }
        )
    return rows


def _resolve_reference(value: object, base_dir: Path) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    if path.exists():
        return path
    if not path.is_absolute():
        candidate = base_dir / path
        if candidate.exists():
            return candidate
    return path


def _artifact_name(run_dir: Path, value: object, fallback: str) -> str:
    path = _resolve_reference(value, run_dir) if value else None
    if path and path.exists():
        try:
            return str(path.relative_to(run_dir)).replace("\\", "/")
        except ValueError:
            return path.name
    return fallback


def _number(value: object, *, signed: bool = False) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        formatted = f"{value:+.3f}" if signed else f"{value:.3f}"
        return formatted.rstrip("0").rstrip(".")
    if value is None:
        return "-"
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return _cell(value)
    formatted = f"{number:+.3f}" if signed else f"{number:.3f}"
    return formatted.rstrip("0").rstrip(".")


def _cell(value: object) -> str:
    text = str(value if value is not None else "-")
    return text.replace("|", "\\|").replace("\n", " ")
