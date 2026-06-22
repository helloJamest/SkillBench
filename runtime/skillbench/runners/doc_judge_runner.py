from __future__ import annotations

from ..judges import GenericSkillJudge
from ..schemas import CaseResult, EvalCase


class DocJudgeRunner:
    def __init__(self, judge: GenericSkillJudge | None = None) -> None:
        self.judge = judge or GenericSkillJudge()

    def run_case(self, skill_text: str, case: EvalCase) -> CaseResult:
        if hasattr(self.judge, "judge"):
            return self.judge.judge(skill_text, case)  # type: ignore[attr-defined]
        return self.judge.judge_case(skill_text, case)
