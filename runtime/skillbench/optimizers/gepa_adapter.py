from __future__ import annotations

from ..schemas import Reflection
from .mutation_policy import MutationPolicy


class GepaAdapter:
    """Adapter seam for external GEPA optimizers.

    The open-source MVP keeps GEPA optional. If a compatible `gepa` package is
    available, future code can delegate mutation here. Otherwise this adapter
    uses SkillBench's deterministic mutation policy while preserving the same
    select/execute/reflect/mutate/accept lifecycle.
    """

    def __init__(self) -> None:
        try:
            import gepa  # type: ignore

            self.gepa = gepa
        except Exception:  # pragma: no cover - optional external dependency
            self.gepa = None
        self.fallback = MutationPolicy()

    def mutate(self, skill_text: str, reflection: Reflection, parent_candidate_id: str, candidate_id: str):
        return self.fallback.mutate(skill_text, reflection, parent_candidate_id, candidate_id)
