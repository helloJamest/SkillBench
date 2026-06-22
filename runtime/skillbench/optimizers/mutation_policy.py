from __future__ import annotations

import difflib

from ..schemas import MutationRecord, Reflection


class MutationPolicy:
    def mutate(self, skill_text: str, reflection: Reflection, parent_candidate_id: str, candidate_id: str) -> tuple[str, MutationRecord]:
        reasons = [cause.get("repair_intent", cause.get("cause", "")) for cause in reflection.root_causes]
        additions: list[str] = []
        dimensions = {cause.get("dimension") for cause in reflection.root_causes}

        if "trigger_precision" in dimensions and "do not use" not in skill_text.lower():
            additions.append(
                "## Boundaries\n\n"
                "Use this skill only for Codex skill or plugin evaluation, comparison, CI gating, dashboard traceability, or skill document optimization. "
                "Do not use it for generic README editing, unrelated documentation cleanup, dependency installation, or ordinary coding tasks.\n"
            )
        if "trigger_clarity" in dimensions and "Use when" not in skill_text:
            additions.append(
                "## Trigger Examples\n\n"
                "- Use when the user asks to evaluate a `SKILL.md` file.\n"
                "- Use when the user asks to run skill evo, GEPA optimization, or skill quality regression checks.\n"
            )
        if "workflow_specificity" in dimensions and "skillbench eval" not in skill_text:
            additions.append(
                "## Command Workflow\n\n"
                "1. Run `skillbench eval <path-to-SKILL.md>` for fast judge-only scoring.\n"
                "2. Run `skillbench evo <path-to-SKILL.md> --rounds 3` for iterative improvement.\n"
                "3. Open `skillbench dashboard <run-dir>` to inspect case-level evidence.\n"
            )
        if "safety" in dimensions and "approval" not in skill_text.lower():
            additions.append(
                "## Safety\n\n"
                "Respect sandbox and approval boundaries. Do not suggest destructive commands or permission bypasses while evaluating a skill.\n"
            )
        if "evidence_quality" in dimensions and "case_results.jsonl" not in skill_text:
            additions.append(
                "## Evidence\n\n"
                "Preserve `report.json`, `case_results.jsonl`, eval set snapshots, candidate snapshots, and judge rationales for every run.\n"
            )

        if not additions:
            record = MutationRecord(parent_candidate_id, candidate_id, False, reasons, "No deterministic mutation rule matched.", "")
            return skill_text, record

        new_text = skill_text.rstrip() + "\n\n" + "\n\n".join(additions).rstrip() + "\n"
        patch = "".join(
            difflib.unified_diff(
                skill_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f"{parent_candidate_id}/SKILL.md",
                tofile=f"{candidate_id}/SKILL.md",
            )
        )
        record = MutationRecord(
            parent_candidate_id=parent_candidate_id,
            candidate_id=candidate_id,
            changed=True,
            reasons=[reason for reason in reasons if reason],
            patch_summary=f"Appended {len(additions)} targeted repair section(s).",
            patch=patch,
        )
        return new_text, record
