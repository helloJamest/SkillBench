from __future__ import annotations

from pathlib import Path
from typing import Any

from ..observability.logging_io import write_json


def build_sarif_report(ci_result: dict[str, Any]) -> dict[str, Any]:
    failures = ci_result.get("failures", [])
    rules = [_rule_for_type(kind) for kind in sorted({str(item.get("type", "failure")) for item in failures})]
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "SkillBench",
                        "informationUri": "https://github.com/openai/codex",
                        "rules": rules,
                    }
                },
                "results": [_result_for_failure(ci_result, failure, index) for index, failure in enumerate(failures, start=1)],
                "properties": {
                    "passed": bool(ci_result.get("passed")),
                    "total_score": ci_result.get("total_score"),
                    "safety_score": ci_result.get("safety_score"),
                    "worst_case_id": ci_result.get("worst_case_id"),
                    "thresholds": ci_result.get("thresholds", {}),
                    "baseline": ci_result.get("baseline"),
                    "regression": ci_result.get("regression"),
                },
            }
        ],
    }


def write_sarif_report(ci_result: dict[str, Any], path: str | Path) -> Path:
    return write_json(path, build_sarif_report(ci_result))


def _result_for_failure(ci_result: dict[str, Any], failure: dict[str, Any], index: int) -> dict[str, Any]:
    kind = str(failure.get("type", "failure"))
    return {
        "ruleId": f"skillbench.{kind}",
        "ruleIndex": index - 1,
        "level": "error",
        "message": {"text": str(failure.get("message", "SkillBench CI gate failed"))},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": _uri(ci_result.get("report_path", "report.json")),
                    }
                }
            }
        ],
        "properties": {
            "failure_type": kind,
            "worst_case_id": ci_result.get("worst_case_id"),
            "total_score": ci_result.get("total_score"),
            "safety_score": ci_result.get("safety_score"),
        },
    }


def _rule_for_type(kind: str) -> dict[str, Any]:
    readable = kind.replace("-", " ").replace("_", " ")
    return {
        "id": f"skillbench.{kind}",
        "name": f"SkillBench {readable}",
        "shortDescription": {"text": f"SkillBench {readable} gate"},
        "help": {"text": "Inspect the linked SkillBench report and case evidence to diagnose this gate failure."},
    }


def _uri(value: Any) -> str:
    return str(value or "report.json").replace("\\", "/")
