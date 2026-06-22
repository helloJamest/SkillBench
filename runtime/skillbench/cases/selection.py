from __future__ import annotations

from dataclasses import dataclass, field

from ..schemas import EvalCase, EvalSet


@dataclass
class CaseSelection:
    case_ids: list[str] = field(default_factory=list)
    include_tags: list[str] = field(default_factory=list)
    exclude_tags: list[str] = field(default_factory=list)
    mode: str | None = None
    limit: int | None = None

    def normalized(self) -> "CaseSelection":
        return CaseSelection(
            case_ids=_dedupe(self.case_ids),
            include_tags=_dedupe(self.include_tags),
            exclude_tags=_dedupe(self.exclude_tags),
            mode=self.mode,
            limit=self.limit,
        )

    def is_active(self) -> bool:
        return bool(self.case_ids or self.include_tags or self.exclude_tags or self.mode or self.limit is not None)

    def to_metadata(self) -> dict:
        return {
            "case_ids": list(self.case_ids),
            "include_tags": list(self.include_tags),
            "exclude_tags": list(self.exclude_tags),
            "mode": self.mode,
            "limit": self.limit,
        }


def select_eval_cases(eval_set: EvalSet, selection: CaseSelection | None = None) -> EvalSet:
    criteria = (selection or CaseSelection()).normalized()
    if not criteria.is_active():
        return eval_set
    if criteria.limit is not None and criteria.limit < 1:
        raise ValueError("--limit must be greater than 0")

    selected = list(eval_set.cases)
    if criteria.case_ids:
        requested = set(criteria.case_ids)
        available = {case.id for case in selected}
        missing = sorted(requested - available)
        if missing:
            raise ValueError(f"Unknown case id(s): {', '.join(missing)}")
        selected = [case for case in selected if case.id in requested]
    if criteria.include_tags:
        include = set(criteria.include_tags)
        selected = [case for case in selected if include.intersection(_case_tags(case))]
    if criteria.exclude_tags:
        exclude = set(criteria.exclude_tags)
        selected = [case for case in selected if not exclude.intersection(_case_tags(case))]
    if criteria.mode:
        selected = [case for case in selected if case.mode == criteria.mode]
    if criteria.limit is not None:
        selected = selected[: criteria.limit]
    if not selected:
        raise ValueError("No eval cases matched the selection filters")

    metadata = dict(eval_set.metadata)
    metadata["selection"] = {
        **criteria.to_metadata(),
        "original_case_count": len(eval_set.cases),
        "selected_case_count": len(selected),
    }
    return EvalSet(
        id=eval_set.id,
        cases=selected,
        profile=eval_set.profile,
        source_skill_hash=eval_set.source_skill_hash,
        generator=dict(eval_set.generator),
        metadata=metadata,
    )


def _case_tags(case: EvalCase) -> set[str]:
    return set(case.tags or [])


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
