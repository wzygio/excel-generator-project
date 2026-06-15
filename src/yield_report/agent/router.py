"""Spec loading helpers for Codex-driven Agent runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from yield_report.agent.spec_model import TaskSpec
from yield_report.agent.spec_validation import SpecValidationError, assert_valid_task_spec


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
    try:
        assert_valid_task_spec(spec)
    except SpecValidationError as exc:
        raise SpecLoadError(str(exc)) from exc
