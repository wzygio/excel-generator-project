"""Lightweight Skill runtime used by Codex and tests."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from yield_report.agent.spec_model import RunContext, SkillCall, SkillError, SkillResult, TaskSpec
from yield_report.agent.trace import TraceEvent, TraceWriter
from yield_report.infrastructure.logging_config import configure_yield_report_logging_for_context

SkillRunFunc = Callable[[BaseModel, RunContext], SkillResult]
logger = logging.getLogger(__name__)


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
        run_id = spec.run_id or (context.run_id if context is not None else "manual-run")
        context = context or RunContext(run_id=run_id, workspace=Path.cwd())
        context.run_id = run_id
        self._prepare_run_context(spec, context)
        configure_yield_report_logging_for_context(context)
        self._seed_spec_inputs(spec, context)

        results: list[SkillResult] = []
        step_summaries: list[dict[str, Any]] = []
        completed: set[str] = set()

        for call in spec.workflow:
            missing = [dependency for dependency in call.depends_on if dependency not in completed]
            if missing:
                raise AgentRuntimeError(f"Step {call.id} has unmet dependencies: {missing}")
            result = self.run_call(call, context)
            results.append(result)
            step_summaries.append(self._step_summary(call, result))
            completed.add(call.id)
            if call.save_as:
                context.remember(call.save_as, result)
            context.remember(call.id, result)
            if not result.success:
                break

        self._write_run_outputs(context, results, step_summaries)
        return results

    def run_call(self, call: SkillCall, context: RunContext) -> SkillResult:
        registration = self._skills.get(call.skill)
        if registration is None:
            logger.error(
                "Skill is not registered: %s",
                call.skill,
                extra={
                    "event": "failure",
                    "purpose": "operation",
                    "run_id": context.run_id,
                    "task_id": call.id,
                },
            )
            self._write_trace(
                context=context,
                call=call,
                status="failed",
                error={
                    "code": "runtime.skill.unregistered",
                    "message": f"Skill is not registered: {call.skill}",
                    "recoverable": True,
                    "details": {"skill": call.skill},
                    "repair_hint": (
                        "Register the skill in yield_report.agent.registry or update "
                        "spec.workflow[*].skill."
                    ),
                },
            )
            raise AgentRuntimeError(f"Skill is not registered: {call.skill}")

        request_data = self._resolve_references(call.input, context)
        request = registration.request_model(**request_data)
        logger.info(
            "Skill call started: %s",
            call.skill,
            extra={
                "event": "start",
                "purpose": "operation",
                "run_id": context.run_id,
                "task_id": call.id,
            },
        )
        self._write_trace(
            context=context,
            call=call,
            status="started",
            input_summary=str(request_data)[:500],
        )
        try:
            result = registration.run(request, context)
        except Exception as exc:
            logger.exception(
                "Skill call raised an exception: %s",
                call.skill,
                extra={
                    "event": "failure",
                    "purpose": "operation",
                    "run_id": context.run_id,
                    "task_id": call.id,
                },
            )
            result = SkillResult(
                skill_name=call.skill,
                success=False,
                summary=f"Skill raised exception: {exc}",
                error=SkillError(
                    code=f"{call.skill}.execution.exception",
                    message=str(exc),
                    recoverable=True,
                    details={"exception_type": type(exc).__name__},
                ),
            )
        logger.log(
            logging.INFO if result.success else logging.ERROR,
            "Skill call completed: %s success=%s",
            call.skill,
            result.success,
            extra={
                "event": "success" if result.success else "failure",
                "purpose": "operation",
                "run_id": context.run_id,
                "task_id": call.id,
            },
        )
        self._write_trace(
            context=context,
            call=call,
            status="succeeded" if result.success else "failed",
            output_summary=result.summary,
            artifacts=[str(artifact.path) for artifact in result.artifacts],
            error=self._error_payload(result.error) if result.error else None,
        )
        return result

    def _prepare_run_context(self, spec: TaskSpec, context: RunContext) -> None:
        run_dir = self._resolve_run_dir(context)
        output_dir = Path(context.output_dir)
        if output_dir == Path("output") or not output_dir.is_absolute():
            context.output_dir = run_dir / "outputs"
        context.output_dir.mkdir(parents=True, exist_ok=True)

        context.config.setdefault("run_dir", str(run_dir))
        context.config.setdefault("memory_candidates_path", str(run_dir / "memory_candidates.json"))
        context.config.setdefault("summary_path", str(run_dir / "run_summary.json"))

        if context.trace is None:
            trace_path = Path(spec.trace.get("path") or "trace.jsonl")
            if not trace_path.is_absolute():
                trace_path = run_dir / trace_path
            context.trace = TraceWriter(trace_path)

    @staticmethod
    def _resolve_run_dir(context: RunContext) -> Path:
        configured = context.config.get("run_dir")
        if configured:
            return Path(configured)
        if context.spec_path is not None:
            return Path(context.spec_path).resolve().parent
        output_dir = Path(context.output_dir)
        if output_dir.name == "outputs":
            return output_dir.resolve().parent
        return context.workspace.resolve() / "specs" / "runs" / context.run_id

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
    def _step_summary(call: SkillCall, result: SkillResult) -> dict[str, Any]:
        return {
            "step_id": call.id,
            "skill": call.skill,
            "status": "succeeded" if result.success else "failed",
            "success": result.success,
            "summary": result.summary,
            "artifacts": [artifact.model_dump(mode="json") for artifact in result.artifacts],
            "warnings": result.warnings,
            "error": AgentRuntime._error_payload(result.error) if result.error else None,
        }

    @staticmethod
    def _write_run_outputs(
        context: RunContext,
        results: list[SkillResult],
        step_summaries: list[dict[str, Any]],
    ) -> None:
        run_dir = AgentRuntime._resolve_run_dir(context)
        summary_path = Path(context.config.get("summary_path") or run_dir / "run_summary.json")
        memory_path = Path(
            context.config.get("memory_candidates_path") or run_dir / "memory_candidates.json"
        )
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        memory_path.parent.mkdir(parents=True, exist_ok=True)

        status = "completed" if results and all(result.success for result in results) else "failed"
        artifacts = [
            artifact.model_dump(mode="json")
            for result in results
            for artifact in result.artifacts
        ]
        memory_candidates = [
            candidate.model_dump(mode="json")
            for result in results
            for candidate in result.memory_updates
        ]
        summary = {
            "run_id": context.run_id,
            "status": status,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "result_count": len(results),
            "steps": step_summaries,
            "artifacts": artifacts,
            "memory_candidates_path": str(memory_path),
        }
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        memory_path.write_text(
            json.dumps(memory_candidates, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _error_payload(error: SkillError) -> dict[str, Any]:
        payload = error.model_dump(mode="json")
        payload.setdefault(
            "repair_hint",
            "Inspect this step input and the target skill implementation, then rerun focused tests.",
        )
        return payload

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
