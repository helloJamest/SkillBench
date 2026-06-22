from __future__ import annotations

import json
import sys


def main() -> int:
    payload = json.load(sys.stdin)
    case = payload["case"]
    dimensions = case.get("dimensions") or ["safety"]
    scores = {dimension: 8.0 for dimension in dimensions}
    if "safety" in scores:
        scores["safety"] = 9.0
    json.dump(
        {
            "case_id": case["id"],
            "score": sum(scores.values()) / len(scores),
            "dimension_scores": scores,
            "rationale": "Fake judge example returned stable scores for integration testing.",
            "suggestion": "Replace this fake judge with a real LLM-as-Judge command.",
            "evidence_refs": [],
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

