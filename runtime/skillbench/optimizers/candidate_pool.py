from __future__ import annotations

from pathlib import Path

from ..observability.logging_io import ensure_dir, write_json
from ..schemas import Candidate


class CandidatePool:
    def __init__(self, run_dir: str | Path) -> None:
        self.run_dir = Path(run_dir)
        self.candidates_dir = ensure_dir(self.run_dir / "candidates")
        self.candidates: list[Candidate] = []

    def add_initial(self, skill_text: str) -> Candidate:
        return self.add_candidate(skill_text, parent_id=None, round_index=0, accepted=True, score=None)

    def add_candidate(
        self,
        skill_text: str,
        parent_id: str | None,
        round_index: int,
        accepted: bool = False,
        score: float | None = None,
    ) -> Candidate:
        candidate_id = f"candidate_{len(self.candidates):03d}"
        candidate_dir = ensure_dir(self.candidates_dir / candidate_id)
        path = candidate_dir / "SKILL.md"
        path.write_text(skill_text, encoding="utf-8")
        candidate = Candidate(
            id=candidate_id,
            path=str(path),
            parent_id=parent_id,
            round_index=round_index,
            accepted=accepted,
            score=score,
        )
        self.candidates.append(candidate)
        self.persist()
        return candidate

    def update(self, candidate_id: str, *, accepted: bool | None = None, score: float | None = None) -> Candidate:
        candidate = self.get(candidate_id)
        if accepted is not None:
            candidate.accepted = accepted
        if score is not None:
            candidate.score = score
        self.persist()
        return candidate

    def get(self, candidate_id: str) -> Candidate:
        for candidate in self.candidates:
            if candidate.id == candidate_id:
                return candidate
        raise KeyError(candidate_id)

    def select(self) -> Candidate:
        accepted = [candidate for candidate in self.candidates if candidate.accepted]
        if not accepted:
            return self.candidates[-1]
        return max(accepted, key=lambda item: item.score if item.score is not None else -1.0)

    def persist(self) -> None:
        write_json(self.run_dir / "candidates.json", self.candidates)

