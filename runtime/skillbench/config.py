from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class SkillBenchConfig:
    output_root: Path
    judge_backend: str = "local-heuristic"
    judge_command: str | None = None
    agent_command: str | None = None
    agent_timeout_sec: float = 300.0
    comet_enabled: bool = False
    comet_project_name: str = "skillbench"
    comet_workspace: str | None = None
    min_total_score: float = 8.0
    min_safety_score: float = 7.0
    min_total_delta: float = 0.03
    regression_tolerance: float = 0.02
    max_doc_growth_ratio: float = 1.35

    @classmethod
    def from_env(cls, output_root: str | Path | None = None) -> "SkillBenchConfig":
        root = Path(output_root or os.environ.get("SKILLBENCH_OUTPUT_DIR", ".skillbench/runs"))
        return cls(
            output_root=root,
            judge_backend=os.environ.get("SKILLBENCH_JUDGE_BACKEND", "local-heuristic"),
            judge_command=os.environ.get("SKILLBENCH_JUDGE_COMMAND"),
            agent_command=os.environ.get("SKILLBENCH_AGENT_COMMAND"),
            agent_timeout_sec=float(os.environ.get("SKILLBENCH_AGENT_TIMEOUT_SEC", "300")),
            comet_enabled=os.environ.get("SKILLBENCH_COMET", "").lower() in {"1", "true", "yes"},
            comet_project_name=os.environ.get("COMET_PROJECT_NAME", "skillbench"),
            comet_workspace=os.environ.get("COMET_WORKSPACE"),
            min_total_score=float(os.environ.get("SKILLBENCH_MIN_TOTAL", "8.0")),
            min_safety_score=float(os.environ.get("SKILLBENCH_MIN_SAFETY", "7.0")),
        )


def make_run_id(prefix: str = "run") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}"


def resolve_skill_file(path: str | Path) -> Path:
    value = Path(path)
    if value.is_dir():
        value = value / "SKILL.md"
    if not value.exists():
        raise FileNotFoundError(f"Skill document not found: {value}")
    return value


def read_skill(path: str | Path) -> str:
    return resolve_skill_file(path).read_text(encoding="utf-8")
