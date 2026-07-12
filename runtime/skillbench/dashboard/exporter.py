from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from ..observability.logging_io import ensure_dir, read_json, resolve_run_dir, write_json
from .app import _artifact_rel, _iter_artifacts, render_dashboard_html


def export_dashboard(run_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    run_path = resolve_run_dir(run_dir).resolve()
    output = ensure_dir(Path(output_dir).resolve())
    pages: list[str] = []

    report_path = run_path / "report.json"
    evolution_path = run_path / "evolution.json"
    lift_path = run_path / "lift_report.json"
    matrix_path = run_path / "matrix_report.json"
    pack_review_path = run_path / "pack_review_ci_result.json"
    if report_path.exists():
        report = read_json(report_path)
        index_html = _rewrite_report_index(render_dashboard_html(run_path), report)
        _write_page(output / "index.html", index_html, pages, output)
        for case in report.get("case_results", []):
            case_id = str(case.get("case_id", "case"))
            case_html = render_dashboard_html(run_path / "cases" / case_id).replace('href="/">Back to report</a>', 'href="../../index.html">Back to report</a>')
            _write_page(output / "cases" / case_id / "index.html", case_html, pages, output)
        _write_artifact_pages(run_path, output, pages)
        _write_comparison_page(run_path, output, pages)
    elif evolution_path.exists():
        evolution = read_json(evolution_path)
        index_html = _rewrite_evolution_index(render_dashboard_html(run_path), evolution)
        _write_page(output / "index.html", index_html, pages, output)
        for step in evolution.get("steps", []):
            round_index = int(step.get("round_index", 0))
            round_html = render_dashboard_html(run_path / "evolution" / "rounds" / str(round_index)).replace(
                'href="/">Back to evolution</a>',
                'href="../../../index.html">Back to evolution</a>',
            )
            _write_page(output / "evolution" / "rounds" / str(round_index) / "index.html", round_html, pages, output)
        _write_timeline_page(run_path, evolution, output, pages)
        _write_artifact_pages(run_path, output, pages)
        _write_comparison_page(run_path, output, pages)
    elif lift_path.exists():
        index_html = render_dashboard_html(run_path)
        index_html = index_html.replace('href="/artifacts"', 'href="artifacts/index.html"')
        index_html = index_html.replace('href="/artifacts/lift_report.json"', 'href="artifacts/lift_report.json/index.html"')
        _write_page(output / "index.html", index_html, pages, output)
        _write_artifact_pages(run_path, output, pages)
    elif matrix_path.exists():
        index_html = _rewrite_matrix_index(run_path, render_dashboard_html(run_path))
        _write_page(output / "index.html", index_html, pages, output)
        _write_artifact_pages(run_path, output, pages)
    elif pack_review_path.exists():
        index_html = _rewrite_pack_review_index(run_path, render_dashboard_html(run_path))
        _write_page(output / "index.html", index_html, pages, output)
        _write_artifact_pages(run_path, output, pages)
    else:
        raise FileNotFoundError(f"No report.json, evolution.json, lift_report.json, matrix_report.json, or pack_review_ci_result.json found in {run_path}")

    manifest = {
        "run_dir": str(run_path),
        "output_dir": str(output),
        "pages": pages,
    }
    write_json(output / "manifest.json", manifest)
    return manifest


def _write_page(path: Path, html: str, pages: list[str], root: Path) -> None:
    ensure_dir(path.parent)
    path.write_text(html, encoding="utf-8")
    pages.append(path.relative_to(root).as_posix())


def _write_artifact_pages(run_path: Path, output: Path, pages: list[str]) -> None:
    index_html = _rewrite_artifact_index(run_path, render_dashboard_html(run_path / "artifacts"))
    _write_page(output / "artifacts" / "index.html", index_html, pages, output)
    for artifact in _iter_artifacts(run_path):
        rel = _artifact_rel(run_path, artifact)
        detail_html = render_dashboard_html(run_path / "artifacts" / Path(rel)).replace(
            'href="/artifacts">Back to artifacts</a>',
            f'href="{_artifact_back_href(rel)}">Back to artifacts</a>',
        )
        _write_page(output / "artifacts" / Path(rel) / "index.html", detail_html, pages, output)


def _write_comparison_page(run_path: Path, output: Path, pages: list[str]) -> None:
    if not (run_path / "comparison.json").exists():
        return
    comparison_html = (
        render_dashboard_html(run_path / "comparison")
        .replace('href="/">Back to report</a>', 'href="../index.html">Back to report</a>')
        .replace('href="/artifacts/comparison.json"', 'href="../artifacts/comparison.json/index.html"')
    )
    _write_page(output / "comparison" / "index.html", comparison_html, pages, output)


def _write_timeline_page(run_path: Path, evolution: dict[str, Any], output: Path, pages: list[str]) -> None:
    if not (run_path / "evolution.json").exists():
        return
    timeline_html = render_dashboard_html(run_path / "timeline").replace('href="/">Back to evolution</a>', 'href="../index.html">Back to evolution</a>')
    for step in evolution.get("steps", []):
        round_index = str(step.get("round_index", "0"))
        timeline_html = timeline_html.replace(
            f'href="/evolution/rounds/{round_index}"',
            f'href="../evolution/rounds/{round_index}/index.html"',
        )
    timeline_html = timeline_html.replace('href="/artifacts/timeline.json"', 'href="../artifacts/timeline.json/index.html"')
    _write_page(output / "timeline" / "index.html", timeline_html, pages, output)


def _rewrite_artifact_index(run_path: Path, html: str) -> str:
    html = html.replace('href="/">Back to report</a>', 'href="../index.html">Back to report</a>')
    for artifact in _iter_artifacts(run_path):
        rel = _artifact_rel(run_path, artifact)
        html = html.replace(f'href="/artifacts/{quote(rel, safe="/")}"', f'href="{rel}/index.html"')
    return html


def _artifact_back_href(rel: str) -> str:
    depth = len(Path(rel).parts)
    return "../" * depth + "index.html"


def _rewrite_report_index(html: str, report: dict[str, Any]) -> str:
    for case in report.get("case_results", []):
        case_id = str(case.get("case_id", ""))
        if case_id:
            html = html.replace(f'href="/cases/{case_id}"', f'href="cases/{case_id}/index.html"')
    html = html.replace('href="/artifacts"', 'href="artifacts/index.html"')
    html = html.replace('href="/comparison"', 'href="comparison/index.html"')
    return html


def _rewrite_evolution_index(html: str, evolution: dict[str, Any]) -> str:
    for step in evolution.get("steps", []):
        round_index = str(step.get("round_index", "0"))
        html = html.replace(
            f'href="/evolution/rounds/{round_index}"',
            f'href="evolution/rounds/{round_index}/index.html"',
        )
    html = html.replace('href="/timeline"', 'href="timeline/index.html"')
    return html


def _rewrite_matrix_index(run_path: Path, html: str) -> str:
    html = html.replace('href="/artifacts"', 'href="artifacts/index.html"')
    html = html.replace('href="/artifacts/matrix_report.json"', 'href="artifacts/matrix_report.json/index.html"')
    for artifact in _iter_artifacts(run_path):
        rel = _artifact_rel(run_path, artifact)
        html = html.replace(f'href="/artifacts/{quote(rel, safe="/")}"', f'href="artifacts/{rel}/index.html"')
    return html


def _rewrite_pack_review_index(run_path: Path, html: str) -> str:
    html = html.replace('href="/artifacts"', 'href="artifacts/index.html"')
    for artifact in _iter_artifacts(run_path):
        rel = _artifact_rel(run_path, artifact)
        html = html.replace(f'href="/artifacts/{quote(rel, safe="/")}"', f'href="artifacts/{rel}/index.html"')
    return html
