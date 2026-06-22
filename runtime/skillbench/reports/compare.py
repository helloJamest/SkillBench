from __future__ import annotations

from pathlib import Path
from typing import Any

from ..observability.logging_io import write_json


def build_comparison(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    dimensions = sorted(set(left.get("dimension_scores", {})) | set(right.get("dimension_scores", {})))
    return {
        "left_run_id": left.get("run_id"),
        "right_run_id": right.get("run_id"),
        "left_total_score": left.get("total_score"),
        "right_total_score": right.get("total_score"),
        "total_delta": round(float(right.get("total_score", 0.0)) - float(left.get("total_score", 0.0)), 3),
        "dimension_deltas": {
            name: round(
                float(right.get("dimension_scores", {}).get(name, 0.0))
                - float(left.get("dimension_scores", {}).get(name, 0.0)),
                3,
            )
            for name in dimensions
        },
        "left_worst_case_id": left.get("worst_case_id"),
        "right_worst_case_id": right.get("worst_case_id"),
    }


def write_comparison(comparison: dict[str, Any], path: str | Path) -> Path:
    return write_json(path, comparison)

