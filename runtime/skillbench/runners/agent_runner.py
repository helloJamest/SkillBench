from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from ..judges import GenericSkillJudge
from ..observability.logging_io import ensure_dir, write_json
from ..schemas import CaseResult, EvalCase
from .adapters import build_agent_adapter
from .audit import agent_artifact_paths, build_agent_audit


class FullAgentRunner:
    """Execute a configured agent command and judge its evidence.

    The command receives the case input on stdin. This is deliberately generic
    so users can plug in `codex`, `claude`, or a local harness without changing
    SkillBench's report model.
    """

    def __init__(
        self,
        command: str | None = None,
        judge: GenericSkillJudge | None = None,
        timeout_sec: float = 300,
        runner_name: str = "custom-command",
    ) -> None:
        self.adapter = build_agent_adapter(runner_name, command)
        self.command = self.adapter.command
        self.judge = judge or GenericSkillJudge()
        self.timeout_sec = timeout_sec

    def run_case(self, skill_text: str, case: EvalCase, run_dir: str | Path) -> CaseResult:
        case_dir = ensure_dir(Path(run_dir) / "agent_runs" / case.id)
        artifacts = agent_artifact_paths(case.id)
        (case_dir / "input.txt").write_text(case.input, encoding="utf-8")
        write_json(
            case_dir / "command.json",
            {
                "runner_name": self.adapter.name,
                "configured": self.adapter.configured,
                "command": self.command,
                "timeout_sec": self.timeout_sec,
                "reason": self.adapter.reason,
            },
        )
        evidence: dict[str, object] = {
            "runner": "full-agent",
            "runner_name": self.adapter.name,
            "configured": self.adapter.configured,
        }
        if not self.command:
            stdout = ""
            stderr = ""
            returncode = None
            timed_out = False
            elapsed_sec = 0.0
            status = "not-configured"
            exit_code_text = "not-configured"
            diagnostic = f"{self.adapter.reason} SKILLBENCH_AGENT_COMMAND is the portable override for all runners."
            (case_dir / "stdout.txt").write_text(stdout, encoding="utf-8")
            (case_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
            (case_dir / "exit_code.txt").write_text(exit_code_text, encoding="utf-8")
            files = _list_files(case_dir)
            write_json(case_dir / "files.json", files)
            audit = build_agent_audit(
                case=case,
                adapter=self.adapter,
                status=status,
                timeout_sec=self.timeout_sec,
                elapsed_sec=elapsed_sec,
                returncode=returncode,
                timed_out=timed_out,
                stdout=stdout,
                stderr=stderr,
                files=files,
                artifacts=artifacts,
                diagnostics=[diagnostic],
            )
            write_json(case_dir / "agent_audit.json", audit)
            evidence.update(_behavior_evidence(case_dir, self.adapter.name, status, returncode, timed_out, elapsed_sec, stdout, stderr, files, artifacts))
            evidence["warning"] = diagnostic
            return _judge_case(self.judge, skill_text, case, evidence)

        timed_out = False
        start = time.perf_counter()
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
        elapsed_sec = time.perf_counter() - start
        status = _status(returncode, timed_out)

        (case_dir / "stdout.txt").write_text(stdout, encoding="utf-8")
        (case_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
        (case_dir / "exit_code.txt").write_text(exit_code_text, encoding="utf-8")
        files = _list_files(case_dir)
        write_json(case_dir / "files.json", files)
        audit = build_agent_audit(
            case=case,
            adapter=self.adapter,
            status=status,
            timeout_sec=self.timeout_sec,
            elapsed_sec=elapsed_sec,
            returncode=returncode,
            timed_out=timed_out,
            stdout=stdout,
            stderr=stderr,
            files=files,
            artifacts=artifacts,
        )
        write_json(case_dir / "agent_audit.json", audit)
        evidence.update(_behavior_evidence(case_dir, self.adapter.name, status, returncode, timed_out, elapsed_sec, stdout, stderr, files, artifacts))
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


def _status(returncode: int | None, timed_out: bool) -> str:
    if timed_out:
        return "timeout"
    if returncode == 0:
        return "success"
    return "failed"


def _behavior_evidence(
    case_dir: Path,
    runner_name: str,
    status: str,
    returncode: int | None,
    timed_out: bool,
    elapsed_sec: float,
    stdout: str,
    stderr: str,
    files: list[dict[str, object]],
    artifacts: dict[str, str],
) -> dict[str, object]:
    commands = []
    command_value = artifacts.get("command")
    command_path = case_dir.parent.parent / command_value if command_value else None
    if command_path and command_path.exists():
        data = json.loads(command_path.read_text(encoding="utf-8"))
        if data.get("command"):
            commands.append(data["command"])
    return {
        "workdir": str(case_dir),
        "runner_name": runner_name,
        "status": status,
        "returncode": returncode,
        "timed_out": timed_out,
        "elapsed_sec": round(max(0.0, elapsed_sec), 3),
        "stdout": stdout[-8000:],
        "stderr": stderr[-4000:],
        "commands": commands,
        "files": files,
        "agent_run_dir": str(Path("agent_runs") / case_dir.name),
        "agent_artifacts": artifacts,
    }


def _judge_case(judge, skill_text: str, case: EvalCase, evidence: dict[str, object]) -> CaseResult:
    if hasattr(judge, "judge"):
        return judge.judge(skill_text, case, evidence)
    return judge.judge_case(skill_text, case, evidence)
