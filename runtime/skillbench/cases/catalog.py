from __future__ import annotations

from pathlib import Path
from typing import Any

from .loader import load_eval_set_data


def default_eval_packs_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "examples" / "eval_packs"


def catalog_eval_packs(packs_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(packs_dir) if packs_dir else default_eval_packs_dir()
    packs = []
    for path in sorted(root.glob("*.json")):
        eval_set = load_eval_set_data(path)
        packs.append(
            {
                "id": eval_set.id,
                "profile": eval_set.profile,
                "path": str(path).replace("\\", "/"),
                "case_count": len(eval_set.cases),
                "tags": sorted({tag for case in eval_set.cases for tag in case.tags}),
                "categories": sorted({case.category for case in eval_set.cases if case.category}),
                "types": sorted({case.type for case in eval_set.cases}),
                "modes": sorted({case.mode for case in eval_set.cases}),
                "dimensions": sorted({dimension for case in eval_set.cases for dimension in case.dimensions}),
                "purpose": str(eval_set.metadata.get("purpose", "")),
                "copy_guidance": str(eval_set.metadata.get("copy_guidance", "")),
            }
        )
    return {
        "packs_dir": str(root),
        "pack_count": len(packs),
        "packs": packs,
    }
