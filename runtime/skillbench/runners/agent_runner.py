from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..judges import GenericSkillJudge
from ..observability.logging_io import ensure_dir, write_json
from ..schemas import CaseResult, EvalCase


class FullAgentRunner:
    """Execute a configured agent command and judge its evidence.

    The command receives the case input on stdin. This is deliberately generic
    so users can plug in `codex`, `claude`, or a local harness without changing
    SkillBench's report model.
    """

    def __init__(self, command: str | None = None, judge: GenericSkillJudge | None = None, timeout_sec: float = 300) -> None:
        self.command = command
        self.judge = judge or GenericSkillJudge()
        self.timeout_sec = timeout_sec

    def run_case(self, skill_text: str, case: EvalCase, run_dir: str | Path) -> CaseResult:
        evidence: dict[str, object] = {
            "runner": "full-agent",
            "configured": bool(self.command),
        }
        if not self.command:
            evidence["warning"] = "SKILLBENCH_AGENT_COMMAND is not configured; judged documentation only."
            return _judge_case(self.judge, skill_text, case, evidence)

        case_dir = ensure_dir(Path(run_dir) / "agent_runs" / case.id)
        (case_dir / "input.txt").write_text(case.input, encoding="utf-8")
        write_json(case_dir / "command.json", {"command": self.command, "timeout_sec": self.timeout_sec})
        timed_out = False
        try:
            proc = subprocess.run(
                self.command,
                input=case.input,
                text=True,
                capture_output=True,
                cwd=case_dir,
                shell=True,
                timeout=self.timeout_sec,
                check=False,
            )
            stdout = proc.stdout
            stderr = proc.stderr
            returncode = proc.returncode
            exit_code_text = str(proc.returncode)
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = _to_text(exc.stdout or exc.output)
            stderr = _to_text(exc.stderr)
            timeout_message = f"Command timed out after {self.timeout_sec} seconds."
            stderr = f"{stderr}\n{timeout_message}".strip()
            returncode = None
            exit_code_text = "timeout"

        (case_dir / "stdout.txt").write_text(stdout, encoding="utf-8")
        (case_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
        (case_dir / "exit_code.txt").write_text(exit_code_text, encoding="utf-8")
        files = _list_files(case_dir)
        write_json(case_dir / "files.json", files)
        evidence.update(
            {
                "workdir": str(case_dir),
                "returncode": returncode,
                "timed_out": timed_out,
                "stdout": stdout[-8000:],
                "stderr": stderr[-4000:],
                "commands": [self.command],
                "files": files,
                "agent_run_dir": str(Path("agent_runs") / case.id),
                "agent_artifacts": {
                    "input": str(Path("agent_runs") / case.id / "input.txt"),
                    "command": str(Path("agent_runs") / case.id / "command.json"),
                    "stdout": str(Path("agent_runs") / case.id / "stdout.txt"),
                    "stderr": str(Path("agent_runs") / case.id / "stderr.txt"),
                    "exit_code": str(Path("agent_runs") / case.id / "exit_code.txt"),
                    "files": str(Path("agent_runs") / case.id / "files.json"),
                },
            }
        )
        return _judge_case(self.judge, skill_text, case, evidence)


def _list_files(case_dir: Path) -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    for path in sorted(case_dir.rglob("*")):
        if path.is_file():
            files.append(
                {
                    "path": str(path.relative_to(case_dir)),
                    "size": path.stat().st_size,
                }
            )
    return files


def _to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _judge_case(judge, skill_text: str, case: EvalCase, evidence: dict[str, object]) -> CaseResult:
    if hasattr(judge, "judge"):
        return judge.judge(skill_text, case, evidence)
    return judge.judge_case(skill_text, case, evidence)
