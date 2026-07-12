from __future__ import annotations

import shutil
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


def bootstrap_eval_pack(
    pack_id: str,
    *,
    target_dir: str | Path,
    packs_dir: str | Path | None = None,
    output: str | Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    catalog = catalog_eval_packs(packs_dir)
    pack = next((item for item in catalog["packs"] if item["id"] == pack_id), None)
    if not pack:
        known = ", ".join(item["id"] for item in catalog["packs"]) or "none"
        raise ValueError(f"Unknown eval pack {pack_id!r}. Known packs: {known}")

    target_root = Path(target_dir)
    output_path = Path(output) if output else target_root / ".skillbench" / "eval_packs" / f"{pack_id}.json"
    if output and not output_path.is_absolute():
        output_path = target_root / output_path

    overwritten = output_path.exists()
    if overwritten and not force:
        raise FileExistsError(f"Eval pack output already exists: {output_path}")

    target_root.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(pack["path"]), output_path)

    return {
        "pack_id": pack["id"],
        "profile": pack["profile"],
        "case_count": pack["case_count"],
        "tags": pack["tags"],
        "source": str(Path(pack["path"])).replace("\\", "/"),
        "output": str(output_path).replace("\\", "/"),
        "overwritten": overwritten,
    }
