"""TaskSpec validation for Agent Workbench runs."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, Field

from yield_report.agent.run_id import RunIdFactory, normalize_capability, normalize_source
from yield_report.agent.spec_model import TaskSpec


class SpecValidationIssue(BaseModel):
    """One code-owned validation issue for a TaskSpec."""

    severity: Literal["error", "warning"] = "error"
    code: str
    message: str
    location: str = ""


class SpecValidationResult(BaseModel):
    """Validation result with both blocking errors and soft warnings."""

    issues: list[SpecValidationIssue] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def errors(self) -> list[SpecValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[SpecValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]


class SpecValidationError(Exception):
    """Raised when a TaskSpec fails code-owned validation."""

    def __init__(self, result: SpecValidationResult) -> None:
        self.result = result
        super().__init__(_format_issues(result.errors))


class SpecValidator:
    """Validate cross-field TaskSpec rules before execution."""

    def __init__(self, registered_skills: Iterable[str] | None = None) -> None:
        self._registered_skills = set(registered_skills or [])

    def validate(self, spec: TaskSpec) -> SpecValidationResult:
        issues: list[SpecValidationIssue] = []
        self._validate_schema_version(spec, issues)
        self._validate_status(spec, issues)
        self._validate_run_identity(spec, issues)
        self._validate_workflow(spec, issues)
        self._validate_outputs(spec, issues)
        self._validate_memory(spec, issues)
        return SpecValidationResult(issues=issues)

    def assert_valid(self, spec: TaskSpec) -> None:
        result = self.validate(spec)
        if not result.ok:
            raise SpecValidationError(result)

    @staticmethod
    def _validate_schema_version(
        spec: TaskSpec,
        issues: list[SpecValidationIssue],
    ) -> None:
        if spec.schema_version != 1:
            issues.append(
                SpecValidationIssue(
                    code="spec.schema.unsupported_version",
                    message=f"Unsupported spec schema_version: {spec.schema_version}",
                    location="schema_version",
                )
            )

    @staticmethod
    def _validate_status(spec: TaskSpec, issues: list[SpecValidationIssue]) -> None:
        allowed = {"draft", "ready", "running", "needs_confirmation", "completed", "failed"}
        if spec.status not in allowed:
            issues.append(
                SpecValidationIssue(
                    code="spec.status.invalid",
                    message=f"Unsupported spec status: {spec.status}",
                    location="status",
                )
            )

    @staticmethod
    def _validate_run_identity(
        spec: TaskSpec,
        issues: list[SpecValidationIssue],
    ) -> None:
        if not spec.run_id:
            issues.append(
                SpecValidationIssue(
                    code="spec.run_id.missing",
                    message="run_id is required for executable TaskSpecs.",
                    location="run_id",
                )
            )
        else:
            try:
                RunIdFactory.validate(spec.run_id)
            except ValueError as exc:
                issues.append(
                    SpecValidationIssue(
                        code="spec.run_id.invalid",
                        message=str(exc),
                        location="run_id",
                    )
                )

        source = spec.constraints.get("spec_source")
        if not source:
            issues.append(
                SpecValidationIssue(
                    code="spec.constraints.spec_source_missing",
                    message="constraints.spec_source is required.",
                    location="constraints.spec_source",
                )
            )
        else:
            try:
                normalize_source(str(source))
            except ValueError as exc:
                issues.append(
                    SpecValidationIssue(
                        code="spec.constraints.spec_source_invalid",
                        message=str(exc),
                        location="constraints.spec_source",
                    )
                )

        capability = spec.constraints.get("capability")
        if not capability:
            issues.append(
                SpecValidationIssue(
                    code="spec.constraints.capability_missing",
                    message="constraints.capability is required.",
                    location="constraints.capability",
                )
            )
        else:
            try:
                normalize_capability(str(capability))
            except ValueError as exc:
                issues.append(
                    SpecValidationIssue(
                        code="spec.constraints.capability_invalid",
                        message=str(exc),
                        location="constraints.capability",
                    )
                )

    def _validate_workflow(self, spec: TaskSpec, issues: list[SpecValidationIssue]) -> None:
        if not spec.workflow:
            issues.append(
                SpecValidationIssue(
                    code="spec.workflow.empty",
                    message="TaskSpec workflow must contain at least one step.",
                    location="workflow",
                )
            )
            return

        seen: set[str] = set()
        all_ids = [call.id for call in spec.workflow]
        all_id_set = set(all_ids)
        for index, call in enumerate(spec.workflow):
            location = f"workflow[{index}]"
            if not call.id:
                issues.append(
                    SpecValidationIssue(
                        code="spec.workflow.missing_id",
                        message="Workflow step id is required.",
                        location=f"{location}.id",
                    )
                )
            elif call.id in seen:
                issues.append(
                    SpecValidationIssue(
                        code="spec.workflow.duplicate_id",
                        message=f"Duplicate workflow step id: {call.id}",
                        location=f"{location}.id",
                    )
                )
            seen.add(call.id)

            if not call.skill:
                issues.append(
                    SpecValidationIssue(
                        code="spec.workflow.missing_skill",
                        message=f"Workflow step {call.id or index} must declare a skill.",
                        location=f"{location}.skill",
                    )
                )
            elif self._registered_skills and call.skill not in self._registered_skills:
                issues.append(
                    SpecValidationIssue(
                        code="spec.workflow.unregistered_skill",
                        message=f"Skill is not registered: {call.skill}",
                        location=f"{location}.skill",
                    )
                )

            for dependency in call.depends_on:
                if dependency not in all_id_set:
                    issues.append(
                        SpecValidationIssue(
                            code="spec.workflow.unknown_dependency",
                            message=f"Step {call.id} depends on unknown step: {dependency}",
                            location=f"{location}.depends_on",
                        )
                    )
                elif dependency not in seen:
                    issues.append(
                        SpecValidationIssue(
                            severity="warning",
                            code="spec.workflow.forward_dependency",
                            message=(
                                f"Step {call.id} depends on later step {dependency}; "
                                "the current sequential runtime expects dependencies to run first."
                            ),
                            location=f"{location}.depends_on",
                        )
                    )

    @staticmethod
    def _validate_outputs(spec: TaskSpec, issues: list[SpecValidationIssue]) -> None:
        if not spec.outputs:
            issues.append(
                SpecValidationIssue(
                    code="spec.outputs.empty",
                    message="TaskSpec outputs must declare at least one expected artifact.",
                    location="outputs",
                )
            )

    @staticmethod
    def _validate_memory(spec: TaskSpec, issues: list[SpecValidationIssue]) -> None:
        reuse_policy = spec.memory.get("reuse_policy")
        if reuse_policy and reuse_policy != "confirmed_only":
            issues.append(
                SpecValidationIssue(
                    code="spec.memory.reuse_policy_not_confirmed_only",
                    message="Memory reuse_policy must be confirmed_only.",
                    location="memory.reuse_policy",
                )
            )
        candidate_policy = spec.memory.get("candidate_policy")
        if candidate_policy and candidate_policy not in {"record_pending", "disabled"}:
            issues.append(
                SpecValidationIssue(
                    severity="warning",
                    code="spec.memory.unknown_candidate_policy",
                    message=f"Unknown memory candidate_policy: {candidate_policy}",
                    location="memory.candidate_policy",
                )
            )


def validate_task_spec(
    spec: TaskSpec,
    registered_skills: Iterable[str] | None = None,
) -> SpecValidationResult:
    """Validate a TaskSpec and return structured issues."""
    return SpecValidator(registered_skills=registered_skills).validate(spec)


def assert_valid_task_spec(
    spec: TaskSpec,
    registered_skills: Iterable[str] | None = None,
) -> None:
    """Raise if a TaskSpec contains blocking validation errors."""
    SpecValidator(registered_skills=registered_skills).assert_valid(spec)


def _format_issues(issues: list[SpecValidationIssue]) -> str:
    if not issues:
        return "TaskSpec validation failed"
    return "; ".join(
        f"{issue.code} at {issue.location or '<root>'}: {issue.message}"
        for issue in issues
    )
