"""Shared Agent/Skill models.

Codex is the external agent core for this project. These models are the
stable Python-side contract that CopilotKit, Pi/OMP, Python Skills, and tests can all call.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class ArtifactRef(BaseModel):
    """A file or generated object produced by a skill."""

    kind: str
    path: Path
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillError(BaseModel):
    """Structured failure information returned by a skill."""

    code: str
    message: str
    recoverable: bool = True
    details: dict[str, Any] = Field(default_factory=dict)


class MemoryCandidate(BaseModel):
    """A memory update that should be confirmed before automatic reuse."""

    record_id: str
    summary: str
    status: str = "pending"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SkillResult(BaseModel):
    """Unified result returned by all skill tools."""

    skill_name: str
    success: bool
    summary: str = ""
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: SkillError | None = None
    memory_updates: list[MemoryCandidate] = Field(default_factory=list)


class RunContext(BaseModel):
    """Context shared across skill calls within one run."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str
    workspace: Path = Field(default_factory=Path.cwd)
    spec_path: Path | None = None
    output_dir: Path = Path("output")
    memory: Any | None = None
    trace: Any | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    state: dict[str, Any] = Field(default_factory=dict)

    def remember(self, key: str, value: Any) -> None:
        self.state[key] = value

    def recall(self, key: str, default: Any | None = None) -> Any:
        return self.state.get(key, default)


class SkillCall(BaseModel):
    """One workflow step in a task spec."""

    id: str
    skill: str
    input: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    save_as: str | None = None


class TaskSpec(BaseModel):
    """Spec-driven task contract consumed by the lightweight runtime."""

    schema_version: int = 1
    run_id: str | None = None
    status: str = "draft"
    user_goal: str = ""
    constraints: dict[str, Any] = Field(default_factory=dict)
    inputs: dict[str, Any] = Field(default_factory=dict)
    workflow: list[SkillCall] = Field(default_factory=list)
    outputs: dict[str, Any] = Field(default_factory=dict)
    memory: dict[str, Any] = Field(default_factory=dict)
    trace: dict[str, Any] = Field(default_factory=dict)


class SkillTool(Protocol):
    """Protocol implemented by callable project skills."""

    name: str
    description: str
    request_model: type[BaseModel]

    def run(self, request: BaseModel, context: RunContext) -> SkillResult:
        ...
