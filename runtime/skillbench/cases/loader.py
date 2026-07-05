from __future__ import annotations

from pathlib import Path

from ..observability.logging_io import read_json
from ..schemas import DIMENSIONS, EvalCase, EvalSet


def load_eval_set_data(path: str | Path) -> EvalSet:
    data = read_json(path)
    cases = [
        EvalCase(
            id=item["id"],
            input=item["input"],
            expected=item.get("expected", {}),
            mode=item.get("mode", "judge-only"),
            type=item.get("type", "should-trigger"),
            dimensions=item.get("dimensions", list(DIMENSIONS)),
            weight=float(item.get("weight", 1.0)),
            tags=item.get("tags", []),
            difficulty=item.get("difficulty", "medium"),
            category=item.get("category", "general"),
            golden_behavior=item.get("golden_behavior", []),
            anti_patterns=item.get("anti_patterns", []),
            rubric_notes=item.get("rubric_notes", []),
            metadata=item.get("metadata", {}),
        )
        for item in data.get("cases", [])
    ]
    return EvalSet(
        id=data.get("id", Path(path).stem),
        cases=cases,
        profile=data.get("profile", data.get("metadata", {}).get("profile", "custom")),
        source_skill_hash=data.get("source_skill_hash"),
        generator=data.get("generator", {}),
        metadata=data.get("metadata", {}),
    )
