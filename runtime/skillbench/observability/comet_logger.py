from __future__ import annotations

from pathlib import Path
from typing import Any

from .logging_io import append_jsonl


class CometLogger:
    """Optional Comet ML logger with local JSONL fallback."""

    def __init__(
        self,
        run_dir: str | Path,
        enabled: bool = False,
        project_name: str = "skillbench",
        workspace: str | None = None,
        experiment_name: str | None = None,
    ) -> None:
        self.run_dir = Path(run_dir)
        self.enabled = enabled
        self.project_name = project_name
        self.workspace = workspace
        self.experiment_name = experiment_name
        self._experiment = None
        self._offline_path = self.run_dir / "comet_offline.jsonl"

        if enabled:
            try:
                from comet_ml import Experiment  # type: ignore

                self._experiment = Experiment(project_name=project_name, workspace=workspace)
                if experiment_name:
                    self._experiment.set_name(experiment_name)
            except Exception as exc:  # pragma: no cover - depends on optional external package
                self._experiment = None
                append_jsonl(self._offline_path, {"event": "comet_unavailable", "error": str(exc)})

    def log_metric(self, name: str, value: float, step: int | None = None) -> None:
        if self._experiment is not None:
            self._experiment.log_metric(name, value, step=step)
            return
        append_jsonl(self._offline_path, {"event": "metric", "name": name, "value": value, "step": step})

    def log_parameters(self, params: dict[str, Any]) -> None:
        if self._experiment is not None:
            self._experiment.log_parameters(params)
            return
        append_jsonl(self._offline_path, {"event": "parameters", "parameters": params})

    def log_asset(self, path: str | Path) -> None:
        asset_path = Path(path)
        if self._experiment is not None:
            self._experiment.log_asset(str(asset_path))
            return
        append_jsonl(self._offline_path, {"event": "asset", "path": str(asset_path)})

    def end(self) -> None:
        if self._experiment is not None:
            self._experiment.end()
