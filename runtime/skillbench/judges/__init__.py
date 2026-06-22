from .base import JudgeBackend
from .custom_command import CustomCommandJudge
from .generic_skill_judge import GenericSkillJudge
from .local_heuristic import LocalHeuristicJudge


def build_judge_backend(name: str = "local-heuristic", command: str | None = None) -> JudgeBackend:
    if name in {"local", "local-heuristic", "heuristic"}:
        return LocalHeuristicJudge()
    if name == "custom-command":
        return CustomCommandJudge(command or "")
    raise ValueError(f"Unsupported judge backend: {name}")


__all__ = ["CustomCommandJudge", "GenericSkillJudge", "JudgeBackend", "LocalHeuristicJudge", "build_judge_backend"]
