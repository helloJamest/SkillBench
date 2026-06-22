from __future__ import annotations

from typing import Any, Protocol

from ..schemas import CaseResult, EvalCase


class JudgeBackend(Protocol):
    name: str

    def judge(self, skill_text: str, case: EvalCase, evidence: dict[str, Any] | None = None) -> CaseResult:
        ...

