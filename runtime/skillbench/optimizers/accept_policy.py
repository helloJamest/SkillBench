from __future__ import annotations

from ..config import SkillBenchConfig
from ..schemas import AcceptDecision, EvalReport


class AcceptPolicy:
    def __init__(self, config: SkillBenchConfig) -> None:
        self.config = config

    def decide(self, parent: EvalReport | None, candidate: EvalReport) -> AcceptDecision:
        reasons: list[str] = []
        if parent is None:
            return AcceptDecision(candidate.candidate_id, None, True, ["initial candidate"], 0.0)

        delta = candidate.total_score - parent.total_score
        safety = candidate.dimension_scores.get("safety", 10.0)
        parent_safety = parent.dimension_scores.get("safety", 10.0)
        precision = candidate.dimension_scores.get("trigger_precision", 10.0)
        parent_precision = parent.dimension_scores.get("trigger_precision", 10.0)
        candidate_chars = float(candidate.metadata.get("candidate_char_count", 0.0) or 0.0)
        parent_chars = float(parent.metadata.get("candidate_char_count", 0.0) or 0.0)

        accepted = True
        if delta < self.config.min_total_delta:
            accepted = False
            reasons.append(f"total score delta {delta:.3f} is below threshold {self.config.min_total_delta:.3f}")
        if safety < self.config.min_safety_score:
            accepted = False
            reasons.append(f"safety {safety:.2f} is below gate {self.config.min_safety_score:.2f}")
        if safety + self.config.regression_tolerance < parent_safety:
            accepted = False
            reasons.append("safety regressed beyond tolerance")
        if precision + self.config.regression_tolerance < parent_precision:
            accepted = False
            reasons.append("trigger precision regressed beyond tolerance")
        if parent_chars > 0 and candidate_chars > parent_chars * self.config.max_doc_growth_ratio:
            accepted = False
            reasons.append("candidate document growth exceeded configured ratio")
        if accepted:
            reasons.append(f"candidate improved total score by {delta:.3f} without gated regressions")
        return AcceptDecision(candidate.candidate_id, parent.candidate_id, accepted, reasons, round(delta, 3))
