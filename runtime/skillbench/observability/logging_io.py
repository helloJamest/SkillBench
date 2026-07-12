from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from ..schemas import to_dict


def ensure_dir(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def write_json(path: str | Path, value: Any) -> Path:
    target = Path(path)
    ensure_dir(target.parent)
    target.write_text(json.dumps(to_dict(value), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_jsonl(path: str | Path, values: Iterable[Any]) -> Path:
    target = Path(path)
    ensure_dir(target.parent)
    with target.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(to_dict(value), ensure_ascii=False) + "\n")
    return target


def append_jsonl(path: str | Path, value: Any) -> Path:
    target = Path(path)
    ensure_dir(target.parent)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(to_dict(value), ensure_ascii=False) + "\n")
    return target


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "item"


def update_latest_pointer(output_root: str | Path, run_dir: str | Path) -> None:
    root = ensure_dir(output_root)
    pointer = root / "latest.txt"
    pointer.write_text(str(Path(run_dir).resolve()), encoding="utf-8")


def resolve_run_dir(value: str | Path) -> Path:
    path = Path(value)
    if path.name == "latest" and not path.exists():
        pointer = path.parent / "latest.txt"
        if pointer.exists():
            return Path(pointer.read_text(encoding="utf-8").strip())
    if path.is_file() and path.name == "latest.txt":
        return Path(path.read_text(encoding="utf-8").strip())
    return path
