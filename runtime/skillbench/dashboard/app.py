from __future__ import annotations

import html
import json
from pathlib import Path

from ..observability.logging_io import read_json, resolve_run_dir


def render_dashboard_html(run_dir: str | Path) -> str:
    requested_path = Path(run_dir)
    route_case_id: str | None = None
    route_round_index: int | None = None
    if len(requested_path.parts) >= 2 and requested_path.parts[-2] == "cases":
        route_case_id = requested_path.parts[-1]
        requested_path = Path(*requested_path.parts[:-2])
    if len(requested_path.parts) >= 3 and requested_path.parts[-3] == "evolution" and requested_path.parts[-2] == "rounds":
        route_round_index = int(requested_path.parts[-1])
        requested_path = Path(*requested_path.parts[:-3])

    run_path = resolve_run_dir(requested_path)
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
    return _render_report(run_path, report)


def create_app(run_dir: str | Path):
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, JSONResponse
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Install fastapi and uvicorn to use the dashboard command.") from exc

    run_path = resolve_run_dir(run_dir)
    app = FastAPI(title="SkillBench Dashboard")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return render_dashboard_html(run_path)

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

    @app.get("/evolution/rounds/{round_index}", response_class=HTMLResponse)
    def evolution_round(round_index: int):
        evolution = run_path / "evolution.json"
        if evolution.exists():
            return _render_evolution_round(run_path, read_json(evolution), round_index)
        return _page("Evolution not found", "<p>No evolution.json found.</p>")

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


def _render_report(run_path: Path, report: dict) -> str:
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
        for case in report.get("case_results", [])
    )
    body = f"""
    <section class="summary">
      <h2>{html.escape(report.get('run_id', 'run'))}</h2>
      <p>Total <strong>{report.get('total_score')}</strong> Grade <strong>{html.escape(report.get('grade', ''))}</strong> Worst case <strong>{html.escape(str(report.get('worst_case_id')))}</strong></p>
      <p>Run directory: <code>{html.escape(str(run_path))}</code></p>
    </section>
    <section>
      <h2>Dimension Scores</h2>
      <table><tbody>{dimensions}</tbody></table>
    </section>
    <section>
      <h2>Cases</h2>
      <table><thead><tr><th>Case</th><th>Type</th><th>Score</th><th>Failed Dimensions</th></tr></thead><tbody>{cases}</tbody></table>
    </section>
    """
    return _page("SkillBench Report", body)


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
    </section>
    <section><h2>Candidates</h2><table><tbody>{candidates}</tbody></table></section>
    <section><h2>GEPA Steps</h2><table><tbody>{steps}</tbody></table></section>
    """
    return _page("SkillBench Evolution", body)


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
    <h2>Dimension Scores</h2>
    <table><tbody>{dims}</tbody></table>
    <h2>Evidence</h2>
    <pre>{evidence}</pre>
    {judge_error_section}
    {agent_sections}
    {judge_sections}
    """


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
    command_html = _artifact_pre(command)
    stdout_html = html.escape(str(stdout or ""))
    stderr_html = html.escape(str(stderr or ""))
    exit_code_html = html.escape(str(exit_code or ""))
    files_html = _artifact_pre(files)
    return f"""
    <section>
      <h2>Agent Run</h2>
      <p>Directory: <code>{html.escape(str(behavior.get('agent_run_dir', '')))}</code></p>
      <p>Return code: <code>{html.escape(str(behavior.get('returncode')))}</code> Timed out: <code>{html.escape(str(behavior.get('timed_out', False)))}</code></p>
      <h3>Agent Command</h3><pre>{command_html}</pre>
      <h3>Agent Stdout</h3><pre>{stdout_html}</pre>
      <h3>Agent Stderr</h3><pre>{stderr_html}</pre>
      <h3>Agent Exit Code</h3><pre>{exit_code_html}</pre>
      <h3>Agent Files</h3><pre>{files_html}</pre>
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
