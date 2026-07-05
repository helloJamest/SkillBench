from __future__ import annotations

import os
from dataclasses import dataclass


AGENT_RUNNERS = ["custom-command", "codex-cli", "claude-cli"]


@dataclass(frozen=True)
class AgentRunnerAdapter:
    name: str
    command: str | None
    configured: bool
    reason: str


def build_agent_adapter(runner_name: str | None = None, command: str | None = None) -> AgentRunnerAdapter:
    name = runner_name or os.environ.get("SKILLBENCH_AGENT_RUNNER", "custom-command")
    if name not in AGENT_RUNNERS:
        raise ValueError(f"Unsupported agent runner: {name}")

    if command:
        return AgentRunnerAdapter(name=name, command=command, configured=True, reason="explicit command provided")

    if name == "codex-cli":
        env_command = os.environ.get("SKILLBENCH_CODEX_COMMAND")
        if env_command:
            return AgentRunnerAdapter(name=name, command=env_command, configured=True, reason="SKILLBENCH_CODEX_COMMAND configured")
        return AgentRunnerAdapter(
            name=name,
            command=None,
            configured=False,
            reason="Set SKILLBENCH_AGENT_COMMAND or SKILLBENCH_CODEX_COMMAND to run codex-cli.",
        )

    if name == "claude-cli":
        env_command = os.environ.get("SKILLBENCH_CLAUDE_COMMAND")
        if env_command:
            return AgentRunnerAdapter(name=name, command=env_command, configured=True, reason="SKILLBENCH_CLAUDE_COMMAND configured")
        return AgentRunnerAdapter(
            name=name,
            command=None,
            configured=False,
            reason="Set SKILLBENCH_AGENT_COMMAND or SKILLBENCH_CLAUDE_COMMAND to run claude-cli.",
        )

    env_command = os.environ.get("SKILLBENCH_AGENT_COMMAND")
    if env_command:
        return AgentRunnerAdapter(name=name, command=env_command, configured=True, reason="SKILLBENCH_AGENT_COMMAND configured")
    return AgentRunnerAdapter(
        name=name,
        command=None,
        configured=False,
        reason="Set SKILLBENCH_AGENT_COMMAND to run custom-command.",
    )
