from __future__ import annotations

import html
import json
from pathlib import Path
from urllib.parse import parse_qs, quote

from ..observability.logging_io import read_json, resolve_run_dir
from ..reports.timeline import build_evolution_timeline


def render_dashboard_html(run_dir: str | Path) -> str:
    requested_path, filters = _split_path_query(run_dir)
    route_case_id: str | None = None
    route_comparison = False
    route_timeline = False
    route_round_index: int | None = None
    route_artifact: Path | None = None
    if "artifacts" in requested_path.parts:
        parts = requested_path.parts
        artifact_index = max(index for index, part in enumerate(parts) if part == "artifacts")
        route_artifact = Path(*parts[artifact_index + 1 :]) if artifact_index + 1 < len(parts) else Path()
        requested_path = Path(*parts[:artifact_index])
    if requested_path.name == "comparison" and not (requested_path / "report.json").exists() and not (requested_path / "evolution.json").exists():
        route_comparison = True
        requested_path = requested_path.parent
    if requested_path.name == "timeline" and not (requested_path / "report.json").exists() and not (requested_path / "evolution.json").exists():
        route_timeline = True
        requested_path = requested_path.parent
    if len(requested_path.parts) >= 2 and requested_path.parts[-2] == "cases":
        route_case_id = requested_path.parts[-1]
        requested_path = Path(*requested_path.parts[:-2])
    if len(requested_path.parts) >= 3 and requested_path.parts[-3] == "evolution" and requested_path.parts[-2] == "rounds":
        route_round_index = int(requested_path.parts[-1])
        requested_path = Path(*requested_path.parts[:-3])

    run_path = resolve_run_dir(requested_path)
    if route_artifact is not None:
        if route_artifact == Path():
            return _render_artifacts_index(run_path)
        return _render_artifact(run_path, route_artifact)
    if route_comparison:
        comparison_path = run_path / "comparison.json"
        if comparison_path.exists():
            return _render_comparison(run_path, read_json(comparison_path))
        return _page("Comparison not found", "<p>No comparison.json found.</p>")
    if route_timeline:
        evolution_path = run_path / "evolution.json"
        if evolution_path.exists():
            return _render_timeline(run_path, _load_timeline(run_path, read_json(evolution_path)))
        return _page("Timeline not found", "<p>No evolution.json found.</p>")

    report_path = run_path / "report.json"
    if not report_path.exists():
        evolution_path = run_path / "evolution.json"
        if evolution_path.exists():
            evolution = read_json(evolution_path)
            if route_round_index is not None:
                return _render_evolution_round(run_path, evolution, route_round_index)
            return _render_evolution(run_path, evolution)
        raise FileNotFoundError(f"No report.json or evolution.json found in {run_path}")
    report = read_json(report_path)
    if route_case_id:
        case = _find_case(report, route_case_id)
        if case:
            return _page(f"Case {html.escape(route_case_id)}", _case_html(case, run_path))
        return _page("Case not found", f"<p>No case named {html.escape(route_case_id)}.</p>")
    return _render_report(run_path, report, filters)


def create_app(run_dir: str | Path):
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import HTMLResponse, JSONResponse
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Install fastapi and uvicorn to use the dashboard command.") from exc

    run_path = resolve_run_dir(run_dir)
    app = FastAPI(title="SkillBench Dashboard")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        suffix = f"?{request.url.query}" if request.url.query else ""
        return render_dashboard_html(f"{run_path}{suffix}")

    @app.get("/api/report")
    def api_report():
        report = run_path / "report.json"
        if report.exists():
            return JSONResponse(read_json(report))
        evolution = run_path / "evolution.json"
        return JSONResponse(read_json(evolution))

    @app.get("/api/cases/{case_id}")
    def api_case(case_id: str):
        report = read_json(run_path / "report.json")
        case = _find_case(report, case_id)
        if case:
            return JSONResponse(case)
        return JSONResponse({"error": "case not found", "case_id": case_id}, status_code=404)

    @app.get("/api/evolution")
    def api_evolution():
        evolution = run_path / "evolution.json"
        if evolution.exists():
            return JSONResponse(read_json(evolution))
        return JSONResponse({"error": "evolution.json not found"}, status_code=404)

    @app.get("/api/evolution/rounds/{round_index}")
    def api_evolution_round(round_index: int):
        evolution = run_path / "evolution.json"
        if not evolution.exists():
            return JSONResponse({"error": "evolution.json not found"}, status_code=404)
        data = _load_evolution_round(run_path, read_json(evolution), round_index)
        if data:
            return JSONResponse(data)
        return JSONResponse({"error": "round not found", "round_index": round_index}, status_code=404)

    @app.get("/api/timeline")
    def api_timeline():
        evolution = run_path / "evolution.json"
        if evolution.exists():
            return JSONResponse(_load_timeline(run_path, read_json(evolution)))
        return JSONResponse({"error": "evolution.json not found"}, status_code=404)

    @app.get("/api/comparison")
    def api_comparison():
        comparison = run_path / "comparison.json"
        if comparison.exists():
            return JSONResponse(read_json(comparison))
        return JSONResponse({"error": "comparison.json not found"}, status_code=404)

    @app.get("/artifacts", response_class=HTMLResponse)
    def artifacts_index():
        return _render_artifacts_index(run_path)

    @app.get("/artifacts/{artifact_path:path}", response_class=HTMLResponse)
    def artifact_detail(artifact_path: str):
        return _render_artifact(run_path, Path(artifact_path))

    @app.get("/evolution/rounds/{round_index}", response_class=HTMLResponse)
    def evolution_round(round_index: int):
        evolution = run_path / "evolution.json"
        if evolution.exists():
            return _render_evolution_round(run_path, read_json(evolution), round_index)
        return _page("Evolution not found", "<p>No evolution.json found.</p>")

    @app.get("/timeline", response_class=HTMLResponse)
    def timeline():
        evolution = run_path / "evolution.json"
        if evolution.exists():
            return _render_timeline(run_path, _load_timeline(run_path, read_json(evolution)))
        return _page("Timeline not found", "<p>No evolution.json found.</p>")

    @app.get("/comparison", response_class=HTMLResponse)
    def comparison():
        comparison_path = run_path / "comparison.json"
        if comparison_path.exists():
            return _render_comparison(run_path, read_json(comparison_path))
        return _page("Comparison not found", "<p>No comparison.json found.</p>")

    @app.get("/cases/{case_id}", response_class=HTMLResponse)
    def case_detail(case_id: str):
        report = read_json(run_path / "report.json")
        case = _find_case(report, case_id)
        if case:
            return _page(f"Case {html.escape(case_id)}", _case_html(case, run_path))
        return _page("Case not found", f"<p>No case named {html.escape(case_id)}.</p>")

    return app


def serve(run_dir: str | Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    try:
        import uvicorn
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Install uvicorn to serve the dashboard.") from exc
    uvicorn.run(create_app(run_dir), host=host, port=port)


def _render_report(run_path: Path, report: dict, filters: dict[str, str] | None = None) -> str:
    filters = filters or {}
    all_cases = list(report.get("case_results", []))
    filtered_cases = _filter_cases(all_cases, filters)
    dimensions = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{score}</td></tr>"
        for name, score in sorted(report.get("dimension_scores", {}).items())
    )
    cases = "".join(
        "<tr>"
        f"<td><a href=\"/cases/{html.escape(case['case_id'])}\">{html.escape(case['case_id'])}</a></td>"
        f"<td>{html.escape(case.get('type', ''))}</td>"
        f"<td>{case.get('score')}</td>"
        f"<td>{html.escape(', '.join(case.get('failed_dimensions', [])))}</td>"
        "</tr>"
        for case in filtered_cases
    )
    if not cases:
        cases = "<tr><td colspan=\"4\">No cases match the active filters.</td></tr>"
    filters_html = _case_filters_html(all_cases, filters, len(filtered_cases))
    comparison_link = ""
    if (run_path / "comparison.json").exists():
        comparison_link = '<p><a href="/comparison">View run comparison</a></p>'
    body = f"""
    <section class="summary">
      <h2>{html.escape(report.get('run_id', 'run'))}</h2>
      <p>Total <strong>{report.get('total_score')}</strong> Grade <strong>{html.escape(report.get('grade', ''))}</strong> Worst case <strong>{html.escape(str(report.get('worst_case_id')))}</strong></p>
      <p>Run directory: <code>{html.escape(str(run_path))}</code></p>
      <p><a href="/artifacts">Browse raw artifacts</a></p>
      {comparison_link}
    </section>
    <section>
      <h2>Dimension Scores</h2>
      <table><tbody>{dimensions}</tbody></table>
    </section>
    {filters_html}
    <section>
      <h2>Cases</h2>
      <table><thead><tr><th>Case</th><th>Type</th><th>Score</th><th>Failed Dimensions</th></tr></thead><tbody>{cases}</tbody></table>
    </section>
    """
    return _page("SkillBench Report", body)


def _render_comparison(run_path: Path, comparison: dict) -> str:
    rows = ""
    for dimension, delta in sorted((comparison.get("dimension_deltas") or {}).items()):
        rows += (
            "<tr>"
            f"<td>{html.escape(str(dimension))}</td>"
            f"<td>{html.escape(_format_number(delta, signed=True))}</td>"
            "</tr>"
        )
    if not rows:
        rows = "<tr><td colspan=\"2\">No dimension deltas found.</td></tr>"
    body = f"""
    <p><a href="/">Back to report</a></p>
    <section class="summary">
      <h2>Total Delta <strong>{html.escape(_format_number(comparison.get('total_delta'), signed=True))}</strong></h2>
      <p>Run directory: <code>{html.escape(str(run_path))}</code></p>
      <p><a href="/artifacts/comparison.json">Open raw comparison.json</a></p>
      <table>
        <thead><tr><th></th><th>Left</th><th>Right</th></tr></thead>
        <tbody>
          <tr><th>Run ID</th><td>{html.escape(str(comparison.get('left_run_id', '')))}</td><td>{html.escape(str(comparison.get('right_run_id', '')))}</td></tr>
          <tr><th>Total Score</th><td>{html.escape(_format_number(comparison.get('left_total_score')))}</td><td>{html.escape(_format_number(comparison.get('right_total_score')))}</td></tr>
          <tr><th>Worst Case</th><td>{html.escape(str(comparison.get('left_worst_case_id', '')))}</td><td>{html.escape(str(comparison.get('right_worst_case_id', '')))}</td></tr>
        </tbody>
      </table>
    </section>
    <section>
      <h2>Dimension Deltas</h2>
      <table><thead><tr><th>Dimension</th><th>Delta</th></tr></thead><tbody>{rows}</tbody></table>
    </section>
    """
    return _page("SkillBench Comparison", body)


def _format_number(value: object, signed: bool = False) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        text = f"{value:.3f}".rstrip("0").rstrip(".")
        if text == "-0":
            text = "0"
        if signed and value > 0:
            return f"+{text}"
        return text
    if value is None:
        return ""
    return str(value)


def _load_timeline(run_path: Path, evolution: dict) -> dict:
    timeline_path = run_path / "timeline.json"
    if timeline_path.exists():
        return read_json(timeline_path)
    return build_evolution_timeline(evolution, run_path)


def _split_path_query(value: str | Path) -> tuple[Path, dict[str, str]]:
    text = str(value)
    if "?" not in text:
        return Path(value), {}
    path_text, query = text.split("?", 1)
    parsed = parse_qs(query, keep_blank_values=True)
    return Path(path_text), {key: values[-1] for key, values in parsed.items() if values}


def _filter_cases(cases: list[dict], filters: dict[str, str]) -> list[dict]:
    return [case for case in cases if _case_matches_filters(case, filters)]


def _case_matches_filters(case: dict, filters: dict[str, str]) -> bool:
    failed = filters.get("failed", "").lower() in {"1", "true", "yes", "on"}
    if failed and not case.get("failed_dimensions"):
        return False

    dimension = filters.get("dimension", "").strip()
    if dimension:
        dimensions = set(case.get("dimension_scores", {}).keys()) | set(case.get("failed_dimensions", [])) | set((case.get("dimension_attributions") or {}).keys())
        if dimension not in dimensions:
            return False

    case_type = filters.get("type", "").strip()
    if case_type and case.get("type") != case_type:
        return False

    mode = filters.get("mode", "").strip()
    if mode and case.get("mode") != mode:
        return False

    category = filters.get("category", "").strip()
    if category and case.get("category") != category:
        return False

    query = filters.get("q", "").strip().lower()
    if query:
        haystack = " ".join(
            [
                str(case.get("case_id", "")),
                str(case.get("type", "")),
                str(case.get("mode", "")),
                str(case.get("category", "")),
                str(case.get("input", "")),
                str(case.get("rationale", "")),
                " ".join(str(item) for item in case.get("failed_dimensions", [])),
            ]
        ).lower()
        if query not in haystack:
            return False
    return True


def _case_filters_html(cases: list[dict], filters: dict[str, str], filtered_count: int) -> str:
    dimensions = sorted({dimension for case in cases for dimension in case.get("dimension_scores", {}).keys()})
    types = sorted({str(case.get("type", "")) for case in cases if case.get("type")})
    modes = sorted({str(case.get("mode", "")) for case in cases if case.get("mode")})
    categories = sorted({str(case.get("category", "")) for case in cases if case.get("category")})
    failed_checked = " checked" if filters.get("failed", "").lower() in {"1", "true", "yes", "on"} else ""
    return f"""
    <section>
      <h2>Case Filters</h2>
      <form method="get" action="/">
        <label>Search <input name="q" value="{_attr(filters.get('q', ''))}"></label>
        <label>Dimension {_select_html("dimension", dimensions, filters.get("dimension", ""))}</label>
        <label>Type {_select_html("type", types, filters.get("type", ""))}</label>
        <label>Mode {_select_html("mode", modes, filters.get("mode", ""))}</label>
        <label>Category {_select_html("category", categories, filters.get("category", ""))}</label>
        <label><input type="checkbox" name="failed" value="1"{failed_checked}> Failed only</label>
        <button type="submit">Apply</button>
        <a href="/">Reset</a>
      </form>
      <p>Filtered Cases: {filtered_count} / {len(cases)}</p>
    </section>
    """


def _select_html(name: str, options: list[str], selected: str) -> str:
    body = [f'<option value="">All</option>']
    for option in options:
        marker = " selected" if option == selected else ""
        body.append(f'<option value="{_attr(option)}"{marker}>{html.escape(option)}</option>')
    return f'<select name="{_attr(name)}">{"".join(body)}</select>'


def _attr(value: str) -> str:
    return html.escape(str(value), quote=True)


def _render_artifacts_index(run_path: Path) -> str:
    rows = ""
    for path in _iter_artifacts(run_path):
        rel = _artifact_rel(run_path, path)
        rows += (
            "<tr>"
            f"<td><a href=\"/artifacts/{quote(rel, safe='/')}\">{html.escape(rel)}</a></td>"
            f"<td>{path.stat().st_size}</td>"
            "</tr>"
        )
    if not rows:
        rows = "<tr><td colspan=\"2\">No artifact files found.</td></tr>"
    body = f"""
    <p><a href="/">Back to report</a></p>
    <section>
      <h2>Raw Artifacts</h2>
      <p>Run directory: <code>{html.escape(str(run_path))}</code></p>
      <table><thead><tr><th>Artifact</th><th>Bytes</th></tr></thead><tbody>{rows}</tbody></table>
    </section>
    """
    return _page("Raw Artifacts", body)


def _render_artifact(run_path: Path, rel_path: Path) -> str:
    target = _safe_artifact_path(run_path, rel_path)
    rel = _artifact_rel(run_path, target)
    try:
        value = read_json(target)
        text = json.dumps(value, indent=2, ensure_ascii=False)
    except Exception:
        text = target.read_text(encoding="utf-8", errors="replace")
    body = f"""
    <p><a href="/artifacts">Back to artifacts</a></p>
    <section>
      <h2>Raw Artifact</h2>
      <p>Path: <code>{html.escape(rel)}</code></p>
      <p>Bytes: <code>{target.stat().st_size}</code></p>
      <pre>{html.escape(text)}</pre>
    </section>
    """
    return _page("Raw Artifact", body)


def _iter_artifacts(run_path: Path) -> list[Path]:
    if not run_path.exists():
        return []
    return sorted(path for path in run_path.rglob("*") if path.is_file())


def _artifact_rel(run_path: Path, path: Path) -> str:
    return path.relative_to(run_path).as_posix()


def _safe_artifact_path(run_path: Path, rel_path: Path) -> Path:
    if rel_path.is_absolute() or any(part in {"..", ""} for part in rel_path.parts):
        raise FileNotFoundError(f"Artifact path is outside the run directory: {rel_path}")
    root = run_path.resolve()
    target = (run_path / rel_path).resolve()
    if root != target and root not in target.parents:
        raise FileNotFoundError(f"Artifact path is outside the run directory: {rel_path}")
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(f"Artifact not found: {rel_path}")
    return target


def _render_evolution(run_path: Path, evolution: dict) -> str:
    candidates = "".join(
        f"<tr><td>{html.escape(c['id'])}</td><td>{html.escape(str(c.get('parent_id')))}</td><td>{c.get('score')}</td><td>{c.get('accepted')}</td></tr>"
        for c in evolution.get("candidates", [])
    )
    steps = "".join(
        f"<tr><td><a href=\"/evolution/rounds/{s['round_index']}\">{s['round_index']}</a></td><td>{html.escape(s['selected_candidate_id'])}</td><td>{s['decision']['accepted']}</td><td>{html.escape('; '.join(s['decision']['reasons']))}</td></tr>"
        for s in evolution.get("steps", [])
    )
    body = f"""
    <section class="summary">
      <h2>{html.escape(evolution.get('run_id', 'evolution'))}</h2>
      <p>Best candidate <strong>{html.escape(evolution.get('best_candidate_id', ''))}</strong></p>
      <p>Run directory: <code>{html.escape(str(run_path))}</code></p>
      <p><a href="/timeline">View evolution timeline</a></p>
    </section>
    <section><h2>Candidates</h2><table><tbody>{candidates}</tbody></table></section>
    <section><h2>GEPA Steps</h2><table><tbody>{steps}</tbody></table></section>
    """
    return _page("SkillBench Evolution", body)


def _render_timeline(run_path: Path, timeline: dict) -> str:
    rows = ""
    for item in timeline.get("rounds", []):
        round_index = int(item.get("round_index", 0))
        reasons = item.get("decision_reasons") or []
        rows += (
            "<tr>"
            f"<td><a href=\"/evolution/rounds/{round_index}\">Round {round_index}</a></td>"
            f"<td>{html.escape(str(item.get('selected_candidate_id', '')))}</td>"
            f"<td>{html.escape(str(item.get('mutated_candidate_id', '')))}</td>"
            f"<td>{html.escape(_format_number(item.get('selected_score')))}</td>"
            f"<td>{html.escape(_format_number(item.get('mutated_score')))}</td>"
            f"<td>{html.escape(_format_number(item.get('score_delta'), signed=True))}</td>"
            f"<td>{html.escape(str(item.get('accepted', False)))}</td>"
            f"<td>{html.escape(str(item.get('worst_case_id', '')))}</td>"
            f"<td>{html.escape(str(item.get('reflection_summary', '')))}</td>"
            f"<td>{html.escape(str(item.get('mutation_summary', '')))}</td>"
            f"<td>{html.escape('; '.join(str(reason) for reason in reasons))}</td>"
            "</tr>"
        )
    if not rows:
        rows = "<tr><td colspan=\"11\">No evolution rounds found.</td></tr>"
    raw_link = ""
    if (run_path / "timeline.json").exists():
        raw_link = '<p><a href="/artifacts/timeline.json">Open raw timeline.json</a></p>'
    body = f"""
    <p><a href="/">Back to evolution</a></p>
    <section class="summary">
      <h2>{html.escape(str(timeline.get('run_id', 'evolution')))}</h2>
      <p>Best candidate <strong>{html.escape(str(timeline.get('best_candidate_id', '')))}</strong> Rounds <strong>{html.escape(str(timeline.get('round_count', len(timeline.get('rounds', [])))))}</strong></p>
      <p>Run directory: <code>{html.escape(str(run_path))}</code></p>
      {raw_link}
    </section>
    <section>
      <h2>Decision Timeline</h2>
      <table>
        <thead><tr><th>Round</th><th>Selected</th><th>Mutated</th><th>Selected Score</th><th>Mutated Score</th><th>Delta</th><th>Accepted</th><th>Worst Case</th><th>Reflection</th><th>Mutation</th><th>Decision Reasons</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
    """
    return _page("SkillBench Evolution Timeline", body)


def _render_evolution_round(run_path: Path, evolution: dict, round_index: int) -> str:
    data = _load_evolution_round(run_path, evolution, round_index)
    if not data:
        return _page("Evolution Round Not Found", f"<p>No round {round_index}.</p>")
    step = data["step"]
    reflection = html.escape(json.dumps(data.get("reflection", {}), indent=2, ensure_ascii=False))
    mutation = html.escape(json.dumps(data.get("mutation", {}), indent=2, ensure_ascii=False))
    decision = html.escape(json.dumps(data.get("decision", step.get("decision", {})), indent=2, ensure_ascii=False))
    patch = html.escape(str(data.get("mutation", {}).get("patch", "")))
    body = f"""
    <p><a href="/">Back to evolution</a></p>
    <section>
      <h2>Round {round_index}</h2>
      <p>Selected candidate <code>{html.escape(step.get('selected_candidate_id', ''))}</code></p>
      <p>Mutated report <code>{html.escape(step.get('report_path', ''))}</code></p>
    </section>
    <section><h2>Reflection</h2><pre>{reflection}</pre></section>
    <section><h2>Mutation</h2><pre>{mutation}</pre></section>
    <section><h2>Patch</h2><pre>{patch}</pre></section>
    <section><h2>Decision</h2><pre>{decision}</pre></section>
    """
    return _page(f"Evolution Round {round_index}", body)


def _load_evolution_round(run_path: Path, evolution: dict, round_index: int) -> dict | None:
    for step in evolution.get("steps", []):
        if int(step.get("round_index", -1)) == round_index:
            return {
                "step": step,
                "reflection": _read_path_or_empty(run_path, step.get("reflection_path")),
                "mutation": _read_path_or_empty(run_path, step.get("mutation_path")),
                "decision": _read_path_or_empty(run_path, Path(f"round_{round_index:03d}") / "decision.json"),
            }
    return None


def _find_case(report: dict, case_id: str) -> dict | None:
    for case in report.get("case_results", []):
        if case.get("case_id") == case_id:
            return case
    return None


def _case_html(case: dict, run_path: Path | None = None) -> str:
    dims = "".join(f"<tr><td>{html.escape(k)}</td><td>{v}</td></tr>" for k, v in sorted(case.get("dimension_scores", {}).items()))
    evidence_data = dict(case.get("evidence", {}))
    judge_input = _read_artifact(run_path, evidence_data.get("judge_input_path")) if run_path else None
    judge_output = _read_artifact(run_path, evidence_data.get("judge_output_path")) if run_path else None
    agent_sections = _agent_html(run_path, evidence_data) if run_path else ""
    judge_error_section = _judge_error_html(evidence_data)
    trusted_metadata_section = _trusted_case_metadata_html(case)
    attribution_section = _dimension_attribution_html(case)
    evidence = html.escape(json.dumps(evidence_data, indent=2, ensure_ascii=False))
    judge_sections = ""
    if judge_input is not None:
        judge_sections += f"<h2>Judge Input</h2><pre>{html.escape(json.dumps(judge_input, indent=2, ensure_ascii=False))}</pre>"
    if judge_output is not None:
        judge_sections += f"<h2>Judge Output</h2><pre>{html.escape(json.dumps(judge_output, indent=2, ensure_ascii=False))}</pre>"
    return f"""
    <p><a href="/">Back to report</a></p>
    <p><strong>Input:</strong> {html.escape(case.get('input', ''))}</p>
    <p><strong>Score:</strong> {case.get('score')}</p>
    <p><strong>Rationale:</strong> {html.escape(case.get('rationale', ''))}</p>
    <p><strong>Suggestion:</strong> {html.escape(case.get('suggestion', ''))}</p>
    {trusted_metadata_section}
    <h2>Dimension Scores</h2>
    <table><tbody>{dims}</tbody></table>
    {attribution_section}
    <h2>Evidence</h2>
    <pre>{evidence}</pre>
    {judge_error_section}
    {agent_sections}
    {judge_sections}
    """


def _dimension_attribution_html(case: dict) -> str:
    attributions = case.get("dimension_attributions") or {}
    if not isinstance(attributions, dict) or not attributions:
        return ""
    rows = ""
    for dimension, attribution in sorted(attributions.items()):
        if not isinstance(attribution, dict):
            continue
        refs = attribution.get("evidence_refs") or []
        if not isinstance(refs, list):
            refs = [refs]
        rows += (
            "<tr>"
            f"<td>{html.escape(str(dimension))}</td>"
            f"<td>{html.escape(str(attribution.get('score', '')))}</td>"
            f"<td>{html.escape(str(attribution.get('status', '')))}</td>"
            f"<td>{html.escape(str(attribution.get('rationale', '')))}</td>"
            f"<td>{html.escape(', '.join(str(ref) for ref in refs))}</td>"
            f"<td>{html.escape(str(attribution.get('suggestion', '')))}</td>"
            "</tr>"
        )
    if not rows:
        return ""
    return f"""
    <section>
      <h2>Dimension Attribution</h2>
      <table><thead><tr><th>Dimension</th><th>Score</th><th>Status</th><th>Rationale</th><th>Evidence Refs</th><th>Suggestion</th></tr></thead><tbody>{rows}</tbody></table>
    </section>
    """


def _trusted_case_metadata_html(case: dict) -> str:
    golden = case.get("golden_behavior") or []
    anti = case.get("anti_patterns") or []
    notes = case.get("rubric_notes") or []
    if not golden and not anti and not notes and not case.get("category"):
        return ""
    return f"""
    <section>
      <h2>Trusted Case Metadata</h2>
      <p>Difficulty: <code>{html.escape(str(case.get('difficulty', 'medium')))}</code> Category: <code>{html.escape(str(case.get('category', 'general')))}</code></p>
      <h3>Golden Behavior</h3>{_list_html(golden)}
      <h3>Anti-Patterns</h3>{_list_html(anti)}
      <h3>Rubric Notes</h3>{_list_html(notes)}
    </section>
    """


def _list_html(items: list[str]) -> str:
    if not items:
        return "<p>-</p>"
    return "<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in items) + "</ul>"


def _judge_error_html(evidence_data: dict) -> str:
    error = evidence_data.get("judge_error")
    if not isinstance(error, dict):
        return ""
    details = html.escape(json.dumps(error, indent=2, ensure_ascii=False))
    return f"""
    <section>
      <h2>Judge Error</h2>
      <p>Kind: <code>{html.escape(str(error.get('kind', 'unknown')))}</code> Return code: <code>{html.escape(str(error.get('returncode')))}</code></p>
      <pre>{details}</pre>
    </section>
    """


def _agent_html(run_path: Path, evidence_data: dict) -> str:
    behavior = evidence_data.get("behavior")
    if not isinstance(behavior, dict):
        return ""
    artifacts = behavior.get("agent_artifacts")
    if not isinstance(artifacts, dict):
        return ""

    command = _read_artifact(run_path, artifacts.get("command"))
    stdout = _read_artifact(run_path, artifacts.get("stdout"))
    stderr = _read_artifact(run_path, artifacts.get("stderr"))
    exit_code = _read_artifact(run_path, artifacts.get("exit_code"))
    files = _read_artifact(run_path, artifacts.get("files"))
    audit = _read_artifact(run_path, artifacts.get("audit"))
    command_html = _artifact_pre(command)
    stdout_html = html.escape(str(stdout or ""))
    stderr_html = html.escape(str(stderr or ""))
    exit_code_html = html.escape(str(exit_code or ""))
    files_html = _artifact_pre(files)
    audit_html = _artifact_pre(audit)
    return f"""
    <section>
      <h2>Agent Run</h2>
      <p>Directory: <code>{html.escape(str(behavior.get('agent_run_dir', '')))}</code></p>
      <p>Runner: <code>{html.escape(str(behavior.get('runner_name', 'custom-command')))}</code> Status: <code>{html.escape(str(behavior.get('status', 'unknown')))}</code></p>
      <p>Return code: <code>{html.escape(str(behavior.get('returncode')))}</code> Timed out: <code>{html.escape(str(behavior.get('timed_out', False)))}</code> Elapsed: <code>{html.escape(str(behavior.get('elapsed_sec', 0)))}</code>s</p>
      <h3>Agent Command</h3><pre>{command_html}</pre>
      <h3>Agent Stdout</h3><pre>{stdout_html}</pre>
      <h3>Agent Stderr</h3><pre>{stderr_html}</pre>
      <h3>Agent Exit Code</h3><pre>{exit_code_html}</pre>
      <h3>Agent Files</h3><pre>{files_html}</pre>
      <h3>Agent Audit</h3><pre>{audit_html}</pre>
    </section>
    """


def _artifact_pre(value: object | None) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return html.escape(json.dumps(value, indent=2, ensure_ascii=False))
    return html.escape(str(value))


def _read_artifact(run_path: Path | None, rel_path) -> object | None:
    if not run_path or not rel_path:
        return None
    target = run_path / str(rel_path)
    if not target.exists():
        return None
    try:
        return read_json(target)
    except Exception:
        return target.read_text(encoding="utf-8")


def _read_path_or_empty(run_path: Path, path_value) -> object:
    if not path_value:
        return {}
    path = Path(path_value)
    candidates = [path]
    if not path.is_absolute():
        candidates.append(run_path / path)
        candidates.append(Path.cwd() / path)
    for candidate in candidates:
        if candidate.exists():
            try:
                return read_json(candidate)
            except Exception:
                return {"text": candidate.read_text(encoding="utf-8")}
    return {}


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: Inter, Segoe UI, Arial, sans-serif; margin: 0; color: #172033; background: #f6f7f9; }}
    header {{ background: #172033; color: white; padding: 20px 32px; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 24px; }}
    section {{ background: white; border: 1px solid #d9dee8; border-radius: 6px; padding: 18px; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid #e7ebf2; padding: 10px; text-align: left; vertical-align: top; }}
    code, pre {{ background: #eef1f6; border-radius: 4px; padding: 2px 5px; }}
    pre {{ padding: 12px; overflow: auto; }}
    a {{ color: #245fc7; }}
  </style>
</head>
<body>
  <header><h1>{html.escape(title)}</h1></header>
  <main>{body}</main>
</body>
</html>"""
