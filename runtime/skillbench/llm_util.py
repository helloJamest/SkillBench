from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    text: str
    data: dict[str, Any] | None = None


class LLMClient:
    """Small backend facade used by future judge implementations.

    The MVP keeps runtime dependency-free. External API implementations can be
    added behind this interface without changing reports or runners.
    """

    def __init__(self, backend: str = "local-heuristic", command: str | None = None) -> None:
        self.backend = backend
        self.command = command

    def complete(self, prompt: str, schema: dict[str, Any] | None = None) -> LLMResponse:
        if self.backend == "custom-command" and self.command:
            proc = subprocess.run(
                self.command,
                input=prompt,
                text=True,
                capture_output=True,
                shell=True,
                timeout=120,
                check=False,
            )
            text = proc.stdout.strip() or proc.stderr.strip()
            return LLMResponse(text=text, data=_try_json(text))
        return LLMResponse(text="", data=None)


def _try_json(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None

