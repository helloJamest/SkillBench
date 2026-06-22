from __future__ import annotations

from typing import Any

from ..schemas import CaseResult, EvalCase
from .generic_skill_judge import GenericSkillJudge


class LocalHeuristicJudge:
    name = "local-heuristic"

    def __init__(self) -> None:
        self._judge = GenericSkillJudge()

    def judge(self, skill_text: str, case: EvalCase, evidence: dict[str, Any] | None = None) -> CaseResult:
        return self._judge.judge_case(skill_text, case, evidence)

    def judge_case(self, skill_text: str, case: EvalCase, behavior_evidence: dict[str, Any] | None = None) -> CaseResult:
        return self.judge(skill_text, case, behavior_evidence)

