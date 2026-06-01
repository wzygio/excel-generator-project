"""Spec loading helpers for Codex-driven Agent runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from yield_report.agent.spec_model import TaskSpec


class SpecLoadError(Exception):
    """Raised when a task spec cannot be loaded or validated."""


def load_task_spec(path: Path) -> TaskSpec:
    """Load a YAML task spec from disk."""
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise SpecLoadError(f"Failed to read spec: {path}") from exc

    return parse_task_spec(raw)


def parse_task_spec(raw: dict[str, Any] | None) -> TaskSpec:
    """Validate a raw YAML mapping as a TaskSpec."""
    if not isinstance(raw, dict):
        raise SpecLoadError("Task spec must be a YAML mapping")
    try:
        spec = TaskSpec(**raw)
    except Exception as exc:
        raise SpecLoadError(f"Task spec validation failed: {exc}") from exc
    validate_task_spec(spec)
    return spec


def validate_task_spec(spec: TaskSpec) -> None:
    """Validate workflow references that Pydantic cannot check alone."""
    if spec.schema_version != 1:
        raise SpecLoadError(f"Unsupported spec schema_version: {spec.schema_version}")

    seen: set[str] = set()
    for call in spec.workflow:
        if call.id in seen:
            raise SpecLoadError(f"Duplicate workflow step id: {call.id}")
        seen.add(call.id)

    for call in spec.workflow:
        missing = [dependency for dependency in call.depends_on if dependency not in seen]
        if missing:
            raise SpecLoadError(f"Step {call.id} depends on unknown steps: {missing}")
