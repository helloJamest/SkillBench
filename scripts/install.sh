#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT/runtime"
TARGET="${SKILLBENCH_HOME:-$HOME/.skillbench}"
VENV="$TARGET/venv"

mkdir -p "$TARGET"
printf '%s\n' "$RUNTIME_DIR" > "$TARGET/runtime.path"
python -m venv "$VENV"
"$VENV/bin/python" -m pip install --no-deps "$ROOT"
printf 'SkillBench runtime: %s\n' "$RUNTIME_DIR"
printf 'SkillBench venv: %s\n' "$VENV"
printf 'Run: %s\n' "$VENV/bin/skillbench"
