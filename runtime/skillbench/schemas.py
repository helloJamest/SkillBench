from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Literal


DIMENSIONS = [
    "trigger_clarity",
    "trigger_precision",
    "workflow_specificity",
    "context_efficiency",
    "tooling_guidance",
    "safety",
    "evidence_quality",
    "maintainability",
]

DIMENSION_WEIGHTS = {
    "trigger_clarity": 0.15,
    "trigger_precision": 0.15,
    "workflow_specificity": 0.15,
    "context_efficiency": 0.10,
    "tooling_guidance": 0.10,
    "safety": 0.20,
    "evidence_quality": 0.05,
    "maintainability": 0.10,
}


RunMode = Literal["judge-only", "full-agent"]
CaseType = Literal["should-trigger", "should-not-trigger", "ambiguous", "safety", "full-agent", "behavior"]


@dataclass
class EvalCase:
    id: str
    input: str
    expected: dict[str, Any] = field(default_factory=dict)
    mode: RunMode = "judge-only"
    type: CaseType = "should-trigger"
    dimensions: list[str] = field(default_factory=lambda: list(DIMENSIONS))
    weight: float = 1.0
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalSet:
    id: str
    cases: list[EvalCase]
    profile: str = "custom"
    source_skill_hash: str | None = None
    generator: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DimensionScore:
    dimension: str
    score: float
    rationale: str


@dataclass
class CaseResult:
    case_id: str
    mode: RunMode
    type: CaseType
    input: str
    expected: dict[str, Any]
    score: float
    dimension_scores: dict[str, float]
    failed_dimensions: list[str]
    rationale: str
    suggestion: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalReport:
    run_id: str
    candidate_id: str
    skill_path: str
    eval_set_id: str
    total_score: float
    grade: str
    accepted: bool
    dimension_scores: dict[str, float]
    worst_case_id: str | None
    case_results: list[CaseResult]
    artifacts: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Candidate:
    id: str
    path: str
    parent_id: str | None = None
    round_index: int = 0
    accepted: bool = False
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Reflection:
    candidate_id: str
    root_causes: list[dict[str, Any]]
    worst_case_id: str | None
    summary: str


@dataclass
class MutationRecord:
    parent_candidate_id: str
    candidate_id: str
    changed: bool
    reasons: list[str]
    patch_summary: str
    patch: str = ""


@dataclass
class AcceptDecision:
    candidate_id: str
    parent_candidate_id: str | None
    accepted: bool
    reasons: list[str]
    score_delta: float


@dataclass
class EvolutionStep:
    round_index: int
    selected_candidate_id: str
    report_path: str
    reflection_path: str
    mutation_path: str
    decision: AcceptDecision


@dataclass
class EvolutionReport:
    run_id: str
    skill_path: str
    eval_set_id: str
    best_candidate_id: str
    steps: list[EvolutionStep]
    candidates: list[Candidate]
    artifacts: dict[str, str] = field(default_factory=dict)


def to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_dict(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: to_dict(item) for key, item in value.items()}
    if isinstance(value, Path):
        return str(value)
    return value


def grade_for(score: float) -> str:
    if score >= 9:
        return "A"
    if score >= 8:
        return "B+"
    if score >= 7:
        return "B"
    if score >= 6:
        return "C"
    return "D"


def weighted_total(dimension_scores: dict[str, float]) -> float:
    total = 0.0
    weight_sum = 0.0
    for dimension, score in dimension_scores.items():
        weight = DIMENSION_WEIGHTS.get(dimension, 0.0)
        total += score * weight
        weight_sum += weight
    if weight_sum == 0:
        return 0.0
    return round(total / weight_sum, 3)


def normalize_score(score: float) -> float:
    return round(max(0.0, min(10.0, float(score))), 3)
