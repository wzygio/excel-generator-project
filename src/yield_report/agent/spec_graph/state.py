"""State and dependency types for the LangGraph Spec sub-agent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from yield_report.agent.run_id import RunIdFactory
from yield_report.agent.spec_model import TaskSpec
from yield_report.agent.spec_validation import SpecValidationIssue

DraftGenerator = Callable[[Any, list[SpecValidationIssue], str], dict[str, Any] | str]


class SpecAgentResult(TypedDict):
    """Final result returned by the Spec graph facade."""

    spec: TaskSpec
    warnings: list[str]
    validation_issues: list[SpecValidationIssue]


class SpecAgentState(TypedDict):
    """LangGraph state for Spec construction."""

    request: Any
    context: NotRequired[str]
    raw_spec: NotRequired[dict[str, Any] | str]
    spec: NotRequired[TaskSpec]
    warnings: NotRequired[list[str]]
    validation_issues: NotRequired[list[SpecValidationIssue]]
    repair_attempts: NotRequired[int]


@dataclass(frozen=True)
class SpecGraphDeps:
    """Runtime dependencies injected into graph nodes."""

    workspace: Path
    draft_generator: DraftGenerator
    registered_skills: set[str]
    run_id_factory: RunIdFactory
    max_repair_attempts: int = 2
