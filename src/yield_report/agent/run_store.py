"""Run directory management for Spec-driven Agent runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from yield_report.agent.memory import AgentMemory
from yield_report.agent.router import load_task_spec
from yield_report.agent.spec_model import RunContext, TaskSpec
from yield_report.agent.trace import TraceWriter


@dataclass(frozen=True)
class RunPaths:
    """Filesystem paths owned by one TaskSpec run."""

    run_id: str
    run_dir: Path
    spec_path: Path
    trace_path: Path
    output_dir: Path
    memory_candidates_path: Path
    summary_path: Path


class RunStore:
    """Create and load run-scoped files under ``specs/runs/<run_id>/``."""

    def __init__(self, workspace: Path | None = None, runs_root: Path | None = None) -> None:
        self.workspace = (workspace or Path.cwd()).resolve()
        root = runs_root or Path("specs/runs")
        self.runs_root = root if root.is_absolute() else self.workspace / root

    def create_run(self, run_id: str | None = None) -> RunPaths:
        """Create a run directory and return all standard paths."""
        normalized_run_id = run_id or datetime.now().strftime("run-%Y%m%d-%H%M%S")
        run_dir = self.runs_root / normalized_run_id
        output_dir = run_dir / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        return RunPaths(
            run_id=normalized_run_id,
            run_dir=run_dir,
            spec_path=run_dir / "spec.yaml",
            trace_path=run_dir / "trace.jsonl",
            output_dir=output_dir,
            memory_candidates_path=run_dir / "memory_candidates.json",
            summary_path=run_dir / "run_summary.json",
        )

    def paths_for_spec(self, spec_path: Path) -> RunPaths:
        """Resolve standard run paths for an existing spec file."""
        resolved_spec = spec_path if spec_path.is_absolute() else self.workspace / spec_path
        run_dir = resolved_spec.resolve().parent
        return RunPaths(
            run_id=run_dir.name,
            run_dir=run_dir,
            spec_path=run_dir / "spec.yaml",
            trace_path=run_dir / "trace.jsonl",
            output_dir=run_dir / "outputs",
            memory_candidates_path=run_dir / "memory_candidates.json",
            summary_path=run_dir / "run_summary.json",
        )

    def load_spec(self, spec_path: Path) -> TaskSpec:
        """Load and validate a TaskSpec YAML file."""
        path = spec_path if spec_path.is_absolute() else self.workspace / spec_path
        return load_task_spec(path)

    def save_spec(self, spec: TaskSpec, spec_path: Path) -> None:
        """Write a TaskSpec YAML file with stable field ordering."""
        path = spec_path if spec_path.is_absolute() else self.workspace / spec_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(spec.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def make_context(self, spec_path: Path, spec: TaskSpec) -> RunContext:
        """Build the RunContext used by AgentRuntime for a stored spec."""
        paths = self.paths_for_spec(spec_path)
        paths.output_dir.mkdir(parents=True, exist_ok=True)
        return RunContext(
            run_id=spec.run_id or paths.run_id,
            workspace=self.workspace,
            spec_path=paths.spec_path,
            output_dir=paths.output_dir,
            memory=AgentMemory(),
            trace=TraceWriter(paths.trace_path),
            config={
                "run_dir": str(paths.run_dir),
                "memory_candidates_path": str(paths.memory_candidates_path),
                "summary_path": str(paths.summary_path),
            },
        )

    def standard_paths(self, context: RunContext) -> RunPaths:
        """Resolve run paths from a Runtime context."""
        if context.spec_path is not None:
            return self.paths_for_spec(context.spec_path)
        run_dir = self.runs_root / context.run_id
        return RunPaths(
            run_id=context.run_id,
            run_dir=run_dir,
            spec_path=run_dir / "spec.yaml",
            trace_path=run_dir / "trace.jsonl",
            output_dir=context.output_dir,
            memory_candidates_path=run_dir / "memory_candidates.json",
            summary_path=run_dir / "run_summary.json",
        )

    @staticmethod
    def dump_yaml(data: dict[str, Any], path: Path) -> None:
        """Write YAML data for small support files."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
