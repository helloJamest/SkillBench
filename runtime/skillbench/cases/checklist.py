from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .loader import load_eval_set_data
from .validator import validate_eval_set


def render_eval_pack_checklist(eval_set_path: str | Path, skill_path: str | Path | None = None) -> str:
    validation = validate_eval_set(eval_set_path, skill_path=skill_path)
    try:
        eval_set = load_eval_set_data(eval_set_path)
    except Exception:
        return _render_load_error_checklist(eval_set_path, validation)

    lines = [
        "# SkillBench Eval Pack Authoring Checklist",
        "",
        f"Eval set: `{eval_set.id}`",
        f"Profile: `{eval_set.profile}`",
        f"Path: `{eval_set_path}`",
        f"Cases: {len(eval_set.cases)}",
        f"Validation: {'PASS' if validation['passed'] else 'FAIL'}",
        "",
        "## Coverage Summary",
        "",
        f"- Types: {_join_sorted(case.type for case in eval_set.cases)}",
        f"- Modes: {_join_sorted(case.mode for case in eval_set.cases)}",
        f"- Difficulties: {_join_sorted(case.difficulty for case in eval_set.cases)}",
        f"- Categories: {_join_sorted(case.category for case in eval_set.cases)}",
        f"- Tags: {_join_sorted(tag for case in eval_set.cases for tag in case.tags)}",
        f"- Dimensions: {_join_sorted(dimension for case in eval_set.cases for dimension in case.dimensions)}",
        "",
        "## Review Checklist",
        "",
        "- [ ] Every case has a stable id and non-empty input.",
        "- [ ] Trigger, negative, ambiguous, safety, workflow, tooling, evidence, and maintenance risks are covered where relevant.",
        "- [ ] Each case includes category, golden_behavior, anti_patterns, and rubric_notes.",
        "- [ ] Tags support focused CI slices such as smoke, release, safety, trigger, workflow, and evidence.",
        "- [ ] Dimensions match the behavior being judged and avoid unrelated rubric noise.",
        "- [ ] Full-agent cases document runnable evidence expectations and bounded commands.",
        "",
    ]
    lines.extend(_validation_findings(validation))
    lines.extend(_repair_hints(validation))
    lines.extend(_case_sections(eval_set.cases))
    return "\n".join(lines).rstrip() + "\n"


def _render_load_error_checklist(eval_set_path: str | Path, validation: dict[str, Any]) -> str:
    lines = [
        "# SkillBench Eval Pack Authoring Checklist",
        "",
        f"Eval set: `{Path(eval_set_path).name}`",
        f"Path: `{eval_set_path}`",
        "Validation: FAIL",
        "",
    ]
    lines.extend(_validation_findings(validation))
    lines.extend(_repair_hints(validation))
    return "\n".join(lines).rstrip() + "\n"


def _validation_findings(validation: dict[str, Any]) -> list[str]:
    lines = ["## Validation Findings", ""]
    errors = validation.get("errors", [])
    warnings = validation.get("warnings", [])
    if not errors and not warnings:
        lines.append("No validation errors or warnings.")
        lines.append("")
        return lines
    for error in errors:
        lines.append(f"- ERROR [{error.get('type', 'unknown')}] {error.get('message', '')}")
    for warning in warnings:
        lines.append(f"- WARN [{warning.get('type', 'unknown')}] {warning.get('message', '')}")
    lines.append("")
    return lines


def _repair_hints(validation: dict[str, Any]) -> list[str]:
    lines = ["## Repair Hints", ""]
    hints = validation.get("hints", [])
    if not hints:
        lines.append("No repair hints.")
        lines.append("")
        return lines
    for hint in hints:
        lines.append(f"- HINT [{hint.get('type', 'unknown')}] `{hint.get('field', '')}`: {hint.get('suggestion', '')}")
        if "example" in hint:
            lines.append(f"  Example: `{json.dumps(hint['example'], ensure_ascii=False)}`")
    lines.append("")
    return lines


def _case_sections(cases: list[Any]) -> list[str]:
    lines = ["## Cases", ""]
    if not cases:
        lines.append("No cases found.")
        lines.append("")
        return lines
    for case in cases:
        lines.extend(
            [
                f"### `{case.id}`",
                "",
                f"- Type: `{case.type}`",
                f"- Mode: `{case.mode}`",
                f"- Difficulty: `{case.difficulty}`",
                f"- Category: `{case.category}`",
                f"- Tags: {_join_sorted(case.tags)}",
                f"- Dimensions: {_join_sorted(case.dimensions)}",
                "- Golden behavior:",
            ]
        )
        lines.extend(_bullet_items(case.golden_behavior))
        lines.append("- Anti-patterns:")
        lines.extend(_bullet_items(case.anti_patterns))
        lines.append("- Rubric notes:")
        lines.extend(_bullet_items(case.rubric_notes))
        lines.append("")
    return lines


def _bullet_items(values: list[str]) -> list[str]:
    if not values:
        return ["  - Missing."]
    return [f"  - {value}" for value in values]


def _join_sorted(values) -> str:
    items = sorted({str(value) for value in values if str(value)})
    return ", ".join(items) if items else "-"
