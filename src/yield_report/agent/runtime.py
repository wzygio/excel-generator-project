"""Lightweight Skill runtime used by Codex and tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from yield_report.agent.spec_model import RunContext, SkillCall, SkillResult, TaskSpec
from yield_report.agent.trace import TraceEvent, TraceWriter

SkillRunFunc = Callable[[BaseModel, RunContext], SkillResult]


class SkillRegistration(BaseModel):
    """Runtime metadata for a registered skill."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    request_model: type[BaseModel]
    run: SkillRunFunc


class AgentRuntimeError(Exception):
    """Raised when a spec cannot be executed by the runtime."""


class AgentRuntime:
    """Execute TaskSpec workflow steps through registered skill tools."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillRegistration] = {}

    def register(
        self,
        name: str,
        request_model: type[BaseModel],
        run: SkillRunFunc,
    ) -> None:
        self._skills[name] = SkillRegistration(name=name, request_model=request_model, run=run)

    def run_spec(
        self,
        spec: TaskSpec,
        context: RunContext | None = None,
    ) -> list[SkillResult]:
        run_id = spec.run_id or "manual-run"
        context = context or RunContext(run_id=run_id, workspace=Path.cwd())
        self._seed_spec_inputs(spec, context)
        if context.trace is None and spec.trace.get("path"):
            trace_path = Path(spec.trace["path"])
            if not trace_path.is_absolute():
                trace_path = context.workspace / trace_path
            context.trace = TraceWriter(trace_path)

        results: list[SkillResult] = []
        completed: set[str] = set()

        for call in spec.workflow:
            missing = [dependency for dependency in call.depends_on if dependency not in completed]
            if missing:
                raise AgentRuntimeError(f"Step {call.id} has unmet dependencies: {missing}")
            result = self.run_call(call, context)
            results.append(result)
            completed.add(call.id)
            if call.save_as:
                context.remember(call.save_as, result)
            context.remember(call.id, result)
            if not result.success:
                break

        return results

    def run_call(self, call: SkillCall, context: RunContext) -> SkillResult:
        registration = self._skills.get(call.skill)
        if registration is None:
            raise AgentRuntimeError(f"Skill is not registered: {call.skill}")

        request_data = self._resolve_references(call.input, context)
        request = registration.request_model(**request_data)
        self._write_trace(
            context=context,
            call=call,
            status="started",
            input_summary=str(request_data)[:500],
        )
        result = registration.run(request, context)
        self._write_trace(
            context=context,
            call=call,
            status="succeeded" if result.success else "failed",
            output_summary=result.summary,
            artifacts=[str(artifact.path) for artifact in result.artifacts],
            error=result.error.model_dump(mode="json") if result.error else None,
        )
        return result

    def _resolve_references(self, value: Any, context: RunContext) -> Any:
        if isinstance(value, str) and value in context.state:
            return context.state[value]
        if isinstance(value, list):
            return [self._resolve_references(item, context) for item in value]
        if isinstance(value, dict):
            return {key: self._resolve_references(item, context) for key, item in value.items()}
        return value

    @staticmethod
    def _seed_spec_inputs(spec: TaskSpec, context: RunContext) -> None:
        context.remember("inputs", spec.inputs)
        reports = spec.inputs.get("reports", [])
        if isinstance(reports, list):
            for report in reports:
                if isinstance(report, dict) and report.get("alias"):
                    context.remember(str(report["alias"]), report)

    @staticmethod
    def _write_trace(
        *,
        context: RunContext,
        call: SkillCall,
        status: str,
        input_summary: str = "",
        output_summary: str = "",
        artifacts: list[str] | None = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        if context.trace is None:
            return
        context.trace.write(
            TraceEvent(
                run_id=context.run_id,
                step_id=call.id,
                skill=call.skill,
                status=status,
                input_summary=input_summary,
                output_summary=output_summary,
                artifacts=artifacts or [],
                error=error,
            )
        )
