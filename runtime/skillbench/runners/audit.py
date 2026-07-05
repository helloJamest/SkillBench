from __future__ import annotations

from pathlib import Path
from typing import Any

from ..schemas import EvalCase
from .adapters import AgentRunnerAdapter


def build_agent_audit(
    *,
    case: EvalCase,
    adapter: AgentRunnerAdapter,
    status: str,
    timeout_sec: float,
    elapsed_sec: float,
    returncode: int | None,
    timed_out: bool,
    stdout: str,
    stderr: str,
    files: list[dict[str, object]],
    artifacts: dict[str, str],
    diagnostics: list[str] | None = None,
) -> dict[str, Any]:
    transcript = [{"role": "user", "content": case.input}]
    if stdout:
        transcript.append({"role": "agent_stdout", "content": stdout[-8000:]})
    if stderr:
        transcript.append({"role": "agent_stderr", "content": stderr[-4000:]})
    return {
        "schema_version": "skillbench.agent-audit.v1",
        "case_id": case.id,
        "runner": {
            "name": adapter.name,
            "configured": adapter.configured,
            "command": adapter.command,
            "reason": adapter.reason,
            "timeout_sec": timeout_sec,
        },
        "status": status,
        "timing": {
            "elapsed_sec": round(max(0.0, elapsed_sec), 3),
        },
        "process": {
            "returncode": returncode,
            "timed_out": timed_out,
        },
        "commands": [adapter.command] if adapter.command else [],
        "transcript": transcript,
        "files": files,
        "artifacts": artifacts,
        "diagnostics": diagnostics or [],
    }


def agent_artifact_paths(case_id: str) -> dict[str, str]:
    root = Path("agent_runs") / case_id
    return {
        "input": str(root / "input.txt"),
        "command": str(root / "command.json"),
        "stdout": str(root / "stdout.txt"),
        "stderr": str(root / "stderr.txt"),
        "exit_code": str(root / "exit_code.txt"),
        "files": str(root / "files.json"),
        "audit": str(root / "agent_audit.json"),
    }
