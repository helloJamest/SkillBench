from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..observability.logging_io import ensure_dir, read_json, resolve_run_dir, write_json
from .junit import write_junit_xml
from .matrix import build_harness_matrix_ci_result
from .pr_comment import write_pr_comment
from .sarif import write_sarif_report


RAW_ARTIFACT_SUFFIXES = {".json", ".jsonl", ".md", ".txt", ".xml", ".sarif"}


def build_report_bundle(source: str | Path, output_dir: str | Path) -> dict[str, Any]:
    from ..dashboard import export_dashboard

    source_info = _resolve_source(source)
    output = ensure_dir(output_dir)
    dashboard_dir = output / "dashboard"
    raw_dir = output / "raw"

    dashboard_manifest = export_dashboard(source_info["run_dir"], dashboard_dir)
    comment_path = write_pr_comment(source_info["comment_source"], output / "skillbench-comment.md") if source_info.get("comment_source") else None
    raw_manifest = _write_raw_artifacts(source_info["run_dir"], raw_dir, output / "raw_artifacts.json", output)

    artifacts: dict[str, str] = {
        "dashboard_dir": str(dashboard_dir),
        "dashboard_manifest_json": str(dashboard_dir / "manifest.json"),
        "raw_dir": str(raw_dir),
        "raw_artifacts_json": str(output / "raw_artifacts.json"),
    }
    if comment_path:
        artifacts["pr_comment_md"] = str(comment_path)

    ci_result = source_info.get("ci_result")
    if ci_result:
        junit_path = write_junit_xml(ci_result, output / "junit.xml")
        sarif_path = write_sarif_report(ci_result, output / "skillbench.sarif")
        artifacts["junit_xml"] = str(junit_path)
        artifacts["sarif_json"] = str(sarif_path)

    manifest = {
        "schema_version": "skillbench.report-bundle.v1",
        "source": {
            "kind": source_info["kind"],
            "source": str(resolve_run_dir(source)),
            "run_dir": str(source_info["run_dir"]),
            "ci_result_path": str(source_info["ci_result_path"]) if source_info.get("ci_result_path") else None,
        },
        "output_dir": str(output),
        "dashboard": dashboard_manifest,
        "raw_artifacts": {
            "count": len(raw_manifest["artifacts"]),
            "manifest_json": str(output / "raw_artifacts.json"),
        },
        "artifacts": artifacts,
    }
    manifest_path = write_json(output / "bundle_manifest.json", manifest)
    manifest["artifacts"]["manifest_json"] = str(manifest_path)
    write_json(manifest_path, manifest)
    return manifest


def _resolve_source(source: str | Path) -> dict[str, Any]:
    path = resolve_run_dir(source)
    if path.is_dir():
        return _resolve_run_dir_source(path)
    if path.is_file():
        return _resolve_file_source(path)
    raise FileNotFoundError(f"SkillBench bundle source not found: {path}")


def _resolve_run_dir_source(run_dir: Path) -> dict[str, Any]:
    matrix_path = run_dir / "matrix_report.json"
    if matrix_path.exists():
        matrix_report = read_json(matrix_path)
        ci_path = run_dir / "matrix_ci_result.json"
        ci_result = read_json(ci_path) if ci_path.exists() else _matrix_ci_result(matrix_report, matrix_path)
        return _source_info("matrix", run_dir, run_dir, ci_result, ci_path if ci_path.exists() else None)

    lift_path = run_dir / "lift_report.json"
    if lift_path.exists():
        return _source_info("lift", run_dir, run_dir, None, None)

    report_path = run_dir / "report.json"
    if report_path.exists():
        ci_path = run_dir / "ci_result.json"
        ci_result = read_json(ci_path) if ci_path.exists() else None
        return _source_info("ci" if ci_result else "eval", run_dir, run_dir, ci_result, ci_path if ci_result else None)

    evolution_path = run_dir / "evolution.json"
    if evolution_path.exists():
        return _source_info("evolution", run_dir, None, None, None)

    raise FileNotFoundError(f"No SkillBench report artifact found in {run_dir}")


def _resolve_file_source(path: Path) -> dict[str, Any]:
    payload = read_json(path) if path.suffix == ".json" else None
    if path.name == "ci_result.json" or _looks_like_ci_result(payload):
        ci_result = payload
        report_path = _resolve_reference(ci_result.get("report_path"), path.parent)
        run_dir = report_path.parent if report_path and report_path.exists() else path.parent
        kind = "matrix" if ci_result.get("matrix") else "ci"
        return _source_info(kind, run_dir, path, ci_result, path)

    if path.name == "matrix_report.json" or _looks_like_matrix_report(payload):
        matrix_report = payload
        ci_path = path.parent / "matrix_ci_result.json"
        ci_result = read_json(ci_path) if ci_path.exists() else _matrix_ci_result(matrix_report, path)
        return _source_info("matrix", path.parent, path, ci_result, ci_path if ci_path.exists() else None)

    if path.name == "lift_report.json" or _looks_like_lift_report(payload):
        return _source_info("lift", path.parent, path, None, None)

    if path.name == "report.json" or _looks_like_eval_report(payload):
        ci_path = path.parent / "ci_result.json"
        ci_result = read_json(ci_path) if ci_path.exists() else None
        return _source_info("ci" if ci_result else "eval", path.parent, path, ci_result, ci_path if ci_result else None)

    if path.name == "evolution.json":
        return _source_info("evolution", path.parent, None, None, None)

    raise FileNotFoundError(f"Unsupported SkillBench bundle source: {path}")


def _source_info(kind: str, run_dir: Path, comment_source: str | Path | None, ci_result: dict[str, Any] | None, ci_result_path: Path | None) -> dict[str, Any]:
    return {
        "kind": kind,
        "run_dir": run_dir,
        "comment_source": comment_source,
        "ci_result": ci_result,
        "ci_result_path": ci_result_path,
    }


def _matrix_ci_result(matrix_report: dict[str, Any], report_path: Path) -> dict[str, Any]:
    report = dict(matrix_report)
    artifacts = dict(report.get("artifacts") or {})
    artifacts.setdefault("matrix_report_json", str(report_path))
    report["artifacts"] = artifacts
    return build_harness_matrix_ci_result(report)


def _write_raw_artifacts(run_dir: Path, raw_dir: Path, manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    copied: list[dict[str, Any]] = []
    output_resolved = output_dir.resolve()
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in RAW_ARTIFACT_SUFFIXES:
            continue
        if _is_relative_to(path.resolve(), output_resolved):
            continue
        rel = path.relative_to(run_dir)
        target = raw_dir / rel
        ensure_dir(target.parent)
        shutil.copy2(path, target)
        copied.append(
            {
                "path": rel.as_posix(),
                "bundle_path": str(target.relative_to(manifest_path.parent)).replace("\\", "/"),
                "size": path.stat().st_size,
            }
        )
    manifest = {
        "schema_version": "skillbench.raw-artifacts.v1",
        "run_dir": str(run_dir),
        "raw_dir": str(raw_dir),
        "artifacts": copied,
    }
    write_json(manifest_path, manifest)
    return manifest


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


def _looks_like_ci_result(payload: Any) -> bool:
    return isinstance(payload, dict) and "passed" in payload and "report_path" in payload


def _looks_like_matrix_report(payload: Any) -> bool:
    return isinstance(payload, dict) and (payload.get("schema_version") == "skillbench.harness-matrix.v1" or ("harnesses" in payload and "ranking" in payload))


def _looks_like_lift_report(payload: Any) -> bool:
    return isinstance(payload, dict) and "case_lifts" in payload and "total_lift" in payload


def _looks_like_eval_report(payload: Any) -> bool:
    return isinstance(payload, dict) and "case_results" in payload and "total_score" in payload


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
