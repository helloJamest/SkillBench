from __future__ import annotations

import json
import subprocess
from typing import Any

from ..schemas import CaseResult, EvalCase, to_dict
from .output_schema import JudgeOutputError, validate_judge_output


class CustomCommandJudge:
    name = "custom-command"

    def __init__(self, command: str) -> None:
        if not command:
            raise ValueError("custom-command judge requires a command")
        self.command = command

    def judge(self, skill_text: str, case: EvalCase, evidence: dict[str, Any] | None = None) -> CaseResult:
        payload = {
            "skill_text": skill_text,
            "case": to_dict(case),
            "evidence": evidence or {},
            "rubric": {
                "scale": "0-10",
                "dimensions": case.dimensions,
            },
        }
        try:
            proc = subprocess.run(
                self.command,
                input=json.dumps(payload, ensure_ascii=False),
                text=True,
                capture_output=True,
                shell=True,
                timeout=180,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return _failure_result(
                case,
                evidence,
                self.name,
                self.command,
                kind="timeout",
                message=f"custom judge timed out after {exc.timeout} seconds",
                stdout=_to_text(exc.stdout or exc.output),
                stderr=_to_text(exc.stderr),
                returncode=None,
            )
        if proc.returncode != 0:
            return _failure_result(
                case,
                evidence,
                self.name,
                self.command,
                kind="nonzero-exit",
                message=f"custom judge failed with exit code {proc.returncode}",
                stdout=proc.stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
            )
        try:
            raw = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            return _failure_result(
                case,
                evidence,
                self.name,
                self.command,
                kind="invalid-json",
                message=str(exc),
                stdout=proc.stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
            )
        try:
            data = validate_judge_output(raw, case)
        except (JudgeOutputError, TypeError, ValueError) as exc:
            return _failure_result(
                case,
                evidence,
                self.name,
                self.command,
                kind="invalid-schema",
                message=str(exc),
                stdout=proc.stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
            )
        result_evidence = dict(evidence or {})
        result_evidence.update(
            {
                "judge_backend": self.name,
                "judge_command": self.command,
                "judge_stderr": proc.stderr[-2000:],
                "evidence_refs": data["evidence_refs"],
            }
        )
        return CaseResult(
            case_id=case.id,
            mode=case.mode,
            type=case.type,
            input=case.input,
            expected=case.expected,
            score=data["score"],
            dimension_scores=data["dimension_scores"],
            failed_dimensions=data["failed_dimensions"],
            rationale=data["rationale"],
            suggestion=data["suggestion"],
            weight=case.weight,
            evidence=result_evidence,
        )


def _failure_result(
    case: EvalCase,
    evidence: dict[str, Any] | None,
    backend_name: str,
    command: str,
    kind: str,
    message: str,
    stdout: str,
    stderr: str,
    returncode: int | None,
) -> CaseResult:
    dimension_scores = {dimension: 0.0 for dimension in case.dimensions}
    result_evidence = dict(evidence or {})
    result_evidence.update(
        {
            "judge_backend": backend_name,
            "judge_command": command,
            "judge_error": {
                "kind": kind,
                "message": message,
                "stdout": stdout[-4000:],
                "stderr": stderr[-4000:],
                "returncode": returncode,
            },
        }
    )
    return CaseResult(
        case_id=case.id,
        mode=case.mode,
        type=case.type,
        input=case.input,
        expected=case.expected,
        score=0.0,
        dimension_scores=dimension_scores,
        failed_dimensions=list(case.dimensions),
        rationale=f"Custom judge failed: {kind}. {message}",
        suggestion="Inspect judge_error stdout/stderr and fix the custom judge command or output schema.",
        weight=case.weight,
        evidence=result_evidence,
    )


def _to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)
