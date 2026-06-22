from __future__ import annotations

from pathlib import Path

from ..schemas import EvalReport, EvalSet
from .logging_io import ensure_dir, update_latest_pointer, write_json, write_jsonl
from ..reports.summary import write_summary


class ReportWriter:
    def __init__(self, run_dir: str | Path, output_root: str | Path | None = None) -> None:
        self.run_dir = ensure_dir(run_dir)
        self.output_root = Path(output_root) if output_root else self.run_dir.parent

    def write_eval_set(self, eval_set: EvalSet) -> Path:
        return write_json(self.run_dir / "eval_set.json", eval_set)

    def write_report(self, report: EvalReport) -> Path:
        report_path = write_json(self.run_dir / "report.json", report)
        write_jsonl(self.run_dir / "case_results.jsonl", report.case_results)
        write_summary(report, self.run_dir / "summary.md")
        update_latest_pointer(self.output_root, self.run_dir)
        return report_path

    def write_candidate(self, candidate_id: str, text: str) -> Path:
        target = self.run_dir / "candidates" / candidate_id / "SKILL.md"
        ensure_dir(target.parent)
        target.write_text(text, encoding="utf-8")
        return target
