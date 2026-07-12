from __future__ import annotations

from pathlib import Path
from typing import Any

from .loader import load_eval_set_data


def compare_eval_packs(left_path: str | Path, right_path: str | Path) -> dict[str, Any]:
    left = load_eval_set_data(left_path)
    right = load_eval_set_data(right_path)
    left_summary = _pack_summary(left_path, left)
    right_summary = _pack_summary(right_path, right)
    changes = {
        "cases": _set_change(left_summary["case_ids"], right_summary["case_ids"]),
        "tags": _set_change(left_summary["tags"], right_summary["tags"]),
        "dimensions": _set_change(left_summary["dimensions"], right_summary["dimensions"]),
        "categories": _set_change(left_summary["categories"], right_summary["categories"]),
        "types": _set_change(left_summary["types"], right_summary["types"]),
        "modes": _set_change(left_summary["modes"], right_summary["modes"]),
    }
    return {
        "schema_version": "skillbench.eval-pack-comparison.v1",
        "left": left_summary,
        "right": right_summary,
        "case_delta": right_summary["case_count"] - left_summary["case_count"],
        "changes": changes,
    }


def _pack_summary(path: str | Path, eval_set) -> dict[str, Any]:
    return {
        "eval_set_id": eval_set.id,
        "profile": eval_set.profile,
        "path": str(path),
        "case_count": len(eval_set.cases),
        "case_ids": sorted({case.id for case in eval_set.cases}),
        "tags": sorted({tag for case in eval_set.cases for tag in case.tags}),
        "dimensions": sorted({dimension for case in eval_set.cases for dimension in case.dimensions}),
        "categories": sorted({case.category for case in eval_set.cases if case.category}),
        "types": sorted({case.type for case in eval_set.cases}),
        "modes": sorted({case.mode for case in eval_set.cases}),
    }


def _set_change(left: list[str], right: list[str]) -> dict[str, list[str]]:
    left_set = set(left)
    right_set = set(right)
    return {
        "added": sorted(right_set - left_set),
        "removed": sorted(left_set - right_set),
        "unchanged": sorted(left_set & right_set),
    }
