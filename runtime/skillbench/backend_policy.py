from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class BackendChoice:
    name: str
    reason: str


def choose_backend(requested: str | None = None) -> BackendChoice:
    requested = requested or os.environ.get("SKILLBENCH_JUDGE_BACKEND")
    if requested and requested != "auto":
        return BackendChoice(requested, "explicit backend requested")
    return BackendChoice("local-heuristic", "auto selects the supported local backend in this release")
