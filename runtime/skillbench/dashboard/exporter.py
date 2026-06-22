from __future__ import annotations

from pathlib import Path
from typing import Any

from ..observability.logging_io import ensure_dir, read_json, resolve_run_dir, write_json
from .app import render_dashboard_html


def export_dashboard(run_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    run_path = resolve_run_dir(run_dir)
    output = ensure_dir(output_dir)
    pages: list[str] = []

    report_path = run_path / "report.json"
    evolution_path = run_path / "evolution.json"
    if report_path.exists():
        report = read_json(report_path)
        index_html = _rewrite_report_index(render_dashboard_html(run_path), report)
        _write_page(output / "index.html", index_html, pages, output)
        for case in report.get("case_results", []):
            case_id = str(case.get("case_id", "case"))
            case_html = render_dashboard_html(run_path / "cases" / case_id).replace('href="/">Back to report</a>', 'href="../../index.html">Back to report</a>')
            _write_page(output / "cases" / case_id / "index.html", case_html, pages, output)
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
    else:
        raise FileNotFoundError(f"No report.json or evolution.json found in {run_path}")

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
    pages.append(str(path.relative_to(root)))


def _rewrite_report_index(html: str, report: dict[str, Any]) -> str:
    for case in report.get("case_results", []):
        case_id = str(case.get("case_id", ""))
        if case_id:
            html = html.replace(f'href="/cases/{case_id}"', f'href="cases/{case_id}/index.html"')
    return html


def _rewrite_evolution_index(html: str, evolution: dict[str, Any]) -> str:
    for step in evolution.get("steps", []):
        round_index = str(step.get("round_index", "0"))
        html = html.replace(
            f'href="/evolution/rounds/{round_index}"',
            f'href="evolution/rounds/{round_index}/index.html"',
        )
    return html
