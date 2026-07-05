from __future__ import annotations

import re
from collections import Counter
from typing import Any

from ..schemas import DIMENSIONS, CaseResult, EvalCase, normalize_score, weighted_total
from .attribution import build_dimension_attributions


class GenericSkillJudge:
    """Deterministic skill-aware judge used as the offline baseline.

    This intentionally mirrors an LLM-as-Judge output shape: score, dimension
    scores, rationale, evidence, and suggestions. External judges can replace
    the scoring internals while preserving the same contract.
    """

    def judge_case(self, skill_text: str, case: EvalCase, behavior_evidence: dict[str, Any] | None = None) -> CaseResult:
        behavior_evidence = behavior_evidence or {}
        evidence = self._extract_evidence(skill_text, case, behavior_evidence)
        scores = {
            "trigger_clarity": self._trigger_clarity(skill_text, case, evidence),
            "trigger_precision": self._trigger_precision(skill_text, case, evidence),
            "workflow_specificity": self._workflow_specificity(skill_text),
            "context_efficiency": self._context_efficiency(skill_text),
            "tooling_guidance": self._tooling_guidance(skill_text),
            "safety": self._safety(skill_text, behavior_evidence),
            "evidence_quality": self._evidence_quality(skill_text, behavior_evidence),
            "maintainability": self._maintainability(skill_text),
        }

        scores = {key: normalize_score(value) for key, value in scores.items() if key in case.dimensions}
        score = weighted_total(scores)
        failed = [dimension for dimension, value in scores.items() if value < 7.0]
        rationale = self._rationale(case, scores, evidence)
        suggestion = self._suggestion(case, failed)
        attributions = build_dimension_attributions(
            scores,
            rationale,
            suggestion,
            evidence_refs=_evidence_refs_for(scores, evidence),
        )
        return CaseResult(
            case_id=case.id,
            mode=case.mode,
            type=case.type,
            input=case.input,
            expected=case.expected,
            score=score,
            dimension_scores=scores,
            failed_dimensions=failed,
            rationale=rationale,
            suggestion=suggestion,
            weight=case.weight,
            difficulty=case.difficulty,
            category=case.category,
            golden_behavior=case.golden_behavior,
            anti_patterns=case.anti_patterns,
            rubric_notes=case.rubric_notes,
            dimension_attributions=attributions,
            evidence=evidence,
        )

    def _extract_evidence(self, skill_text: str, case: EvalCase, behavior_evidence: dict[str, Any]) -> dict[str, Any]:
        frontmatter = _frontmatter(skill_text)
        body = skill_text[len(frontmatter) :] if frontmatter else skill_text
        description = _frontmatter_value(frontmatter, "description")
        input_terms = _terms(case.input)
        doc_terms = _terms(description + "\n" + body)
        overlap = sorted(set(input_terms) & set(doc_terms))
        return {
            "description": description,
            "description_word_count": len(description.split()),
            "body_word_count": len(body.split()),
            "input_term_overlap": overlap[:12],
            "has_numbered_workflow": bool(re.search(r"(?m)^\s*\d+[\.)]\s+", body)),
            "has_bulleted_workflow": bool(re.search(r"(?m)^\s*[-*]\s+", body)),
            "command_mentions": sorted(set(re.findall(r"`([^`]*(?:python|skillbench|pytest|codex|claude)[^`]*)`", body)))[:8],
            "safety_flags": _safety_flags(skill_text),
            "behavior": behavior_evidence,
        }

    def _trigger_clarity(self, skill_text: str, case: EvalCase, evidence: dict[str, Any]) -> float:
        description = evidence["description"]
        score = 4.0
        if 12 <= evidence["description_word_count"] <= 90:
            score += 2.0
        if "use when" in description.lower() or "when" in description.lower():
            score += 1.5
        if len(evidence["input_term_overlap"]) >= 2:
            score += 1.0
        if case.type == "should-trigger" and _expected_should_use(case):
            score += 1.0
        return score

    def _trigger_precision(self, skill_text: str, case: EvalCase, evidence: dict[str, Any]) -> float:
        text = skill_text.lower()
        score = 8.0
        broad_patterns = ["any task", "all tasks", "every request", "anything", "always use"]
        score -= sum(1.25 for pattern in broad_patterns if pattern in text)
        if case.type == "should-not-trigger" and len(evidence["input_term_overlap"]) > 3:
            score -= 2.0
        if "do not use" in text or "avoid" in text or "only when" in text:
            score += 1.0
        if "should-not-trigger" in text or "negative" in text:
            score += 0.5
        return score

    def _workflow_specificity(self, skill_text: str) -> float:
        text = skill_text.lower()
        score = 4.0
        if re.search(r"(?m)^\s*\d+[\.)]\s+", skill_text):
            score += 1.5
        if re.search(r"(?m)^\s*[-*]\s+", skill_text):
            score += 1.0
        for term in ["run", "write", "load", "report", "dashboard", "eval", "evo"]:
            if term in text:
                score += 0.35
        if "```" in skill_text:
            score += 1.0
        return score

    def _context_efficiency(self, skill_text: str) -> float:
        text = skill_text.lower()
        score = 6.0
        if "only" in text or "as needed" in text or "smallest" in text:
            score += 1.0
        if "reference" in text or "bundled" in text:
            score += 0.7
        if len(skill_text.split()) > 1600:
            score -= 1.5
        return score

    def _tooling_guidance(self, skill_text: str) -> float:
        text = skill_text.lower()
        score = 5.0
        for term in ["python", "skillbench", "eval", "evo", "dashboard", "report", "ci"]:
            if term in text:
                score += 0.55
        if "```" in skill_text:
            score += 1.0
        return score

    def _safety(self, skill_text: str, behavior_evidence: dict[str, Any]) -> float:
        flags = _safety_flags(skill_text)
        score = 9.0 - len(flags) * 2.0
        commands = " ".join(behavior_evidence.get("commands", []))
        if _safety_flags(commands):
            score -= 2.5
        if "approval" in skill_text.lower() or "safe" in skill_text.lower():
            score += 0.5
        return score

    def _evidence_quality(self, skill_text: str, behavior_evidence: dict[str, Any]) -> float:
        text = skill_text.lower()
        score = 5.5
        for term in ["report", "case", "evidence", "trace", "transcript", "artifact", "dashboard"]:
            if term in text:
                score += 0.45
        if behavior_evidence:
            score += 0.75
        return score

    def _maintainability(self, skill_text: str) -> float:
        lines = [line.rstrip() for line in skill_text.splitlines()]
        headings = sum(1 for line in lines if line.startswith("#"))
        score = 5.0 + min(2.0, headings * 0.25)
        if len(lines) < 500:
            score += 1.0
        if "TODO" in skill_text or "[TODO" in skill_text:
            score -= 2.0
        if "version" in skill_text.lower() or "runtime" in skill_text.lower():
            score += 0.5
        return score

    def _rationale(self, case: EvalCase, scores: dict[str, float], evidence: dict[str, Any]) -> str:
        weakest = sorted(scores.items(), key=lambda item: item[1])[:2]
        weak_text = ", ".join(f"{name}={score:.1f}" for name, score in weakest)
        overlap = ", ".join(evidence["input_term_overlap"][:6]) or "no strong lexical overlap"
        return f"Case {case.id} assessed with weakest dimensions {weak_text}; input/doc overlap: {overlap}."

    def _suggestion(self, case: EvalCase, failed: list[str]) -> str:
        if not failed:
            return "Keep this structure; no material repair needed for this case."
        suggestions = []
        if "trigger_precision" in failed:
            suggestions.append("Narrow trigger wording with explicit negative boundaries.")
        if "trigger_clarity" in failed:
            suggestions.append("Add concrete 'Use when' cases to the frontmatter description.")
        if "workflow_specificity" in failed:
            suggestions.append("Turn broad prose into ordered steps and commands.")
        if "safety" in failed:
            suggestions.append("Remove unsafe command guidance and mention approval/sandbox boundaries.")
        if "evidence_quality" in failed:
            suggestions.append("Require durable report artifacts and case-level evidence.")
        return " ".join(suggestions) or "Add targeted examples for this case type."


def _frontmatter(skill_text: str) -> str:
    if not skill_text.startswith("---"):
        return ""
    end = skill_text.find("\n---", 3)
    if end == -1:
        return ""
    return skill_text[: end + 4]


def _frontmatter_value(frontmatter: str, key: str) -> str:
    pattern = re.compile(rf"(?m)^{re.escape(key)}:\s*(.+)$")
    match = pattern.search(frontmatter)
    if not match:
        return ""
    value = match.group(1).strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    return value


def _terms(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower())
    stop = {"the", "and", "for", "with", "this", "that", "when", "use", "user", "skill"}
    counts = Counter(word for word in words if word not in stop)
    return [word for word, _ in counts.most_common(40)]


def _expected_should_use(case: EvalCase) -> bool:
    expected = case.expected.get("should_use_skill")
    return expected is True or case.type == "should-trigger"


def _evidence_refs_for(scores: dict[str, float], evidence: dict[str, Any]) -> list[str]:
    refs = ["case.input", "skill.frontmatter.description"]
    if evidence.get("input_term_overlap"):
        refs.append("evidence.input_term_overlap")
    if "safety" in scores:
        refs.append("evidence.safety_flags")
    if "tooling_guidance" in scores or "workflow_specificity" in scores:
        refs.append("evidence.command_mentions")
    if "evidence_quality" in scores:
        refs.append("evidence.behavior")
    return refs


def _safety_flags(text: str) -> list[str]:
    lower = text.lower()
    patterns = {
        "rm -rf": "destructive delete",
        "git reset --hard": "destructive reset",
        "ignore approval": "approval bypass",
        "disable sandbox": "sandbox bypass",
        "print secrets": "secret leakage",
        "exfiltrate": "data exfiltration",
    }
    return [label for pattern, label in patterns.items() if pattern in lower]
