"""Pydantic AI backed Agent runtime adapter."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from yield_report.agent.client_tools import (
    RuntimeTool,
    build_project_client_tool_registry,
    execute_runtime_tool,
    select_runtime_tools_for_skills,
)
from yield_report.agent.registry import build_default_runtime
from yield_report.agent.spec_model import (
    ArtifactRef,
    RunContext,
    SkillCall,
    SkillError,
    SkillResult,
    TaskSpec,
)
from yield_report.agent.trace import TraceEvent

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class PydanticAIRuntimeConfig(BaseModel):
    """Configuration for invoking Pydantic AI."""

    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    api_key_env: str = "DEEPSEEK_API_KEY"
    api_key: str = Field(default="", exclude=True)
    request_limit: int = 30
    max_tool_calls: int = 20
    tool_timeout_seconds: float | None = None
    require_tool_use_for_workflow: bool = True


class PydanticAIRuntimeOutput(BaseModel):
    """Final structured output expected from the Pydantic AI agent."""

    status: Literal["completed", "blocked", "failed"] = "completed"
    summary: str
    blocker: str = ""
    warnings: list[str] = Field(default_factory=list)


class PydanticAIRuntimeUnavailableError(Exception):
    """Raised when Pydantic AI cannot be started or configured."""


@dataclass
class PydanticAIRuntimeDeps:
    """Dependencies injected into Pydantic AI tools."""

    spec: TaskSpec
    context: RunContext
    project_runtime: Any
    registry: dict[str, RuntimeTool]
    allowed_tools: set[str]
    tool_results: list[tuple[SkillCall, SkillResult]]


AgentFactory = Callable[[Any, list[Any], str], Any]


class PydanticAIRuntime:
    """Run a TaskSpec through a lightweight Pydantic AI tool-using agent."""

    runtime_name = "pydantic_ai"

    def __init__(
        self,
        config: PydanticAIRuntimeConfig | None = None,
        agent: Any | None = None,
        agent_factory: AgentFactory | None = None,
        project_runtime: Any | None = None,
    ) -> None:
        self.config = config or PydanticAIRuntimeConfig()
        self.agent = agent
        self.agent_factory = agent_factory
        self.project_runtime = project_runtime or build_default_runtime()
        self.client_tool_registry = build_project_client_tool_registry()

    def run_spec(self, spec: TaskSpec, context: RunContext) -> list[SkillResult]:
        tool_results: list[tuple[SkillCall, SkillResult]] = []
        self._prepare_run_context(spec, context)
        selected_tools = self._runtime_tools_for_spec(spec)

        try:
            if spec.workflow and not selected_tools:
                raise PydanticAIRuntimeUnavailableError(
                    "No approved Pydantic AI runtime tools for this TaskSpec workflow."
                )

            deps = PydanticAIRuntimeDeps(
                spec=spec,
                context=context,
                project_runtime=self.project_runtime,
                registry=self.client_tool_registry,
                allowed_tools={tool.name for tool in selected_tools},
                tool_results=tool_results,
            )
            prompt = self._build_prompt(spec, context, selected_tools)
            self._write_trace(context, "pydantic_ai_runtime", "started", "Sending TaskSpec")
            agent = self.agent or self._build_agent(selected_tools)
            output = self._run_agent(agent, prompt, deps)
        except PydanticAIRuntimeUnavailableError as exc:
            result = self._failed_result(
                code="pydantic_ai.unavailable",
                message=str(exc),
                details={"exception_type": type(exc).__name__},
            )
            self._write_trace(context, "pydantic_ai_runtime", "failed", result.summary)
            self._write_run_outputs(context, result, tool_results)
            return [result]
        except Exception as exc:
            result = self._failed_result(
                code="pydantic_ai.runtime_error",
                message=str(exc),
                details={"exception_type": type(exc).__name__},
            )
            self._write_trace(context, "pydantic_ai_runtime", "failed", result.summary)
            self._write_run_outputs(context, result, tool_results)
            return [result]

        result = self._final_result(output, context, spec, tool_results)
        self._write_trace(
            context,
            "pydantic_ai_runtime",
            "succeeded" if result.success else "failed",
            result.summary[:500],
        )
        self._write_run_outputs(context, result, tool_results)
        return [result]

    def _build_agent(self, selected_tools: list[RuntimeTool]) -> Any:
        try:
            from pydantic_ai import Agent, Tool
        except ImportError as exc:
            raise PydanticAIRuntimeUnavailableError(
                "Missing dependency pydantic-ai-slim[openai]. Install it with "
                '`uv add "pydantic-ai-slim[openai]"`.'
            ) from exc

        def run_project_tool(
            ctx: Any,
            tool_name: str,
            arguments: dict[str, Any],
        ) -> dict[str, Any]:
            """Execute one approved project runtime tool."""
            return self._execute_project_tool(ctx.deps, tool_name, arguments)

        tools = [
            Tool(
                run_project_tool,
                takes_ctx=True,
                name="run_project_tool",
                description=(
                    "Execute one approved OLED yield-report runtime tool. "
                    "tool_name must be one of: "
                    f"{', '.join(tool.name for tool in selected_tools) or 'none'}."
                ),
                timeout=self.config.tool_timeout_seconds,
            )
        ]
        instructions = (
            "You are the Pydantic AI Agent Runtime for an OLED yield-report system. "
            "Treat TaskSpec JSON, local SkillResult outputs, and artifact paths as the "
            "source of truth. Use run_project_tool for required workflow steps. "
            "Never invent file paths, credentials, portal sessions, or Excel contents."
        )
        if self.agent_factory is not None:
            return self.agent_factory(self._model(), tools, instructions)
        return Agent(
            self._model(),
            deps_type=PydanticAIRuntimeDeps,
            output_type=PydanticAIRuntimeOutput,
            instructions=instructions,
            tools=tools,
            tool_timeout=self.config.tool_timeout_seconds,
        )

    def _model(self) -> Any:
        if not self.config.base_url:
            return self.config.model

        self._load_runtime_env()
        api_key = self.config.api_key or os.getenv(self.config.api_key_env)
        if not api_key:
            raise PydanticAIRuntimeUnavailableError(
                f"Missing Pydantic AI API key env var: {self.config.api_key_env}"
            )
        try:
            from pydantic_ai.models.openai import OpenAIChatModel
            from pydantic_ai.providers.openai import OpenAIProvider
        except ImportError as exc:
            raise PydanticAIRuntimeUnavailableError(
                "Missing OpenAI-compatible Pydantic AI dependencies."
            ) from exc
        return OpenAIChatModel(
            self.config.model,
            provider=OpenAIProvider(base_url=self.config.base_url, api_key=api_key),
        )

    @staticmethod
    def _load_runtime_env() -> None:
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        load_dotenv(override=False)

    def _runtime_tools_for_spec(self, spec: TaskSpec) -> list[RuntimeTool]:
        workflow_skills = {call.skill for call in spec.workflow}
        return select_runtime_tools_for_skills(workflow_skills, self.client_tool_registry)

    def _run_agent(
        self,
        agent: Any,
        prompt: str,
        deps: PydanticAIRuntimeDeps,
    ) -> PydanticAIRuntimeOutput:
        try:
            from pydantic_ai import UsageLimits
        except ImportError as exc:
            raise PydanticAIRuntimeUnavailableError(
                "Missing dependency pydantic-ai-slim[openai]."
            ) from exc

        run_result = agent.run_sync(
            prompt,
            deps=deps,
            usage_limits=UsageLimits(
                request_limit=self.config.request_limit,
                tool_calls_limit=self.config.max_tool_calls,
            ),
        )
        output = getattr(run_result, "output", run_result)
        if isinstance(output, PydanticAIRuntimeOutput):
            return output
        if isinstance(output, dict):
            return PydanticAIRuntimeOutput.model_validate(output)
        return PydanticAIRuntimeOutput(summary=str(output))

    def _execute_project_tool(
        self,
        deps: PydanticAIRuntimeDeps,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if tool_name not in deps.allowed_tools:
            payload = {
                "status": "error",
                "summary": f"Tool is not allowed for this TaskSpec: {tool_name}",
                "artifacts": [],
                "metrics": {},
                "warnings": [],
                "error": {
                    "code": "pydantic_ai.tool.not_allowed",
                    "message": f"Tool is not allowed for this TaskSpec: {tool_name}",
                    "recoverable": True,
                    "details": {"tool_name": tool_name},
                },
            }
            self._write_trace(
                deps.context,
                "pydantic_ai_tool",
                "failed",
                payload["summary"],
            )
            return payload

        try:
            call, result, payload = execute_runtime_tool(
                tool_name=tool_name,
                arguments=arguments,
                registry=deps.registry,
                project_runtime=deps.project_runtime,
                context=deps.context,
                call_id_prefix="pydantic_ai",
            )
        except Exception as exc:
            payload = {
                "status": "error",
                "summary": f"Runtime tool failed before Skill execution: {exc}",
                "artifacts": [],
                "metrics": {},
                "warnings": [],
                "error": {
                    "code": "pydantic_ai.tool.dispatch_failed",
                    "message": str(exc),
                    "recoverable": True,
                    "details": {"tool_name": tool_name, "exception_type": type(exc).__name__},
                },
            }
            self._write_trace(
                deps.context,
                "pydantic_ai_tool",
                "failed",
                payload["summary"],
            )
            return payload

        deps.tool_results.append((call, result))
        return payload

    @staticmethod
    def _build_prompt(
        spec: TaskSpec,
        context: RunContext,
        selected_tools: list[RuntimeTool],
    ) -> str:
        tools_payload = [
            {
                "name": tool.name,
                "description": tool.description,
                "skill_name": tool.skill_name,
                "risk_level": tool.risk_level,
                "parameters": tool.parameters,
            }
            for tool in selected_tools
        ]
        return (
            "# Yield Report TaskSpec\n\n"
            "You are executing a traceable OLED yield-report TaskSpec through "
            "Pydantic AI. For workflow steps, call `run_project_tool` with one "
            "approved tool name and JSON arguments that match that tool schema.\n\n"
            f"run_id: {context.run_id}\n"
            f"workspace: {context.workspace}\n"
            f"output_dir: {context.output_dir}\n\n"
            "Approved runtime tools:\n"
            "```json\n"
            f"{json.dumps(tools_payload, ensure_ascii=False, indent=2)}\n"
            "```\n\n"
            "TaskSpec JSON:\n"
            "```json\n"
            f"{json.dumps(spec.model_dump(mode='json'), ensure_ascii=False, indent=2)}\n"
            "```\n\n"
            "Return structured output with status, summary, blocker, and warnings. "
            "The final summary should be Chinese and mention data source, steps, "
            "artifacts, blockers, and memory candidates when present."
        )

    def _final_result(
        self,
        output: PydanticAIRuntimeOutput,
        context: RunContext,
        spec: TaskSpec,
        tool_results: list[tuple[SkillCall, SkillResult]],
    ) -> SkillResult:
        missing_tool_use = (
            self.config.require_tool_use_for_workflow
            and bool(spec.workflow)
            and not tool_results
        )
        failed_tool = next((result for _, result in tool_results if not result.success), None)
        success = output.status == "completed" and not missing_tool_use and failed_tool is None
        summary = output.summary
        error: SkillError | None = None
        if missing_tool_use:
            success = False
            summary = "Pydantic AI runtime did not call any project tool for the TaskSpec workflow."
            error = SkillError(
                code="pydantic_ai.workflow.no_tool_calls",
                message=summary,
                recoverable=True,
                details={"workflow_steps": [call.id for call in spec.workflow]},
            )
        elif failed_tool is not None:
            success = False
            error = failed_tool.error or SkillError(
                code="pydantic_ai.workflow.tool_failed",
                message=failed_tool.summary,
                recoverable=True,
                details={"skill_name": failed_tool.skill_name},
            )
        elif output.status in {"blocked", "failed"}:
            success = False
            error = SkillError(
                code=f"pydantic_ai.workflow.{output.status}",
                message=output.blocker or output.summary,
                recoverable=True,
                details={"status": output.status},
            )

        summary_path = context.output_dir / "pydantic_ai_summary.md"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(summary, encoding="utf-8")
        return SkillResult(
            skill_name="pydantic_ai_agent",
            success=success,
            summary=summary,
            artifacts=[
                ArtifactRef(
                    kind="markdown",
                    path=summary_path,
                    description="Pydantic AI runtime summary",
                )
            ],
            data={
                "runtime": self.runtime_name,
                "status": output.status,
                "tool_result_count": len(tool_results),
            },
            warnings=list(output.warnings),
            error=error,
        )

    @staticmethod
    def _failed_result(code: str, message: str, details: dict[str, Any]) -> SkillResult:
        return SkillResult(
            skill_name="pydantic_ai_agent",
            success=False,
            summary=f"Pydantic AI runtime failed: {message}",
            error=SkillError(code=code, message=message, recoverable=True, details=details),
            data={"runtime": "pydantic_ai"},
        )

    @staticmethod
    def _prepare_run_context(spec: TaskSpec, context: RunContext) -> None:
        run_dir = PydanticAIRuntime._resolve_run_dir(context)
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
            from yield_report.agent.trace import TraceWriter

            context.trace = TraceWriter(trace_path)

    @staticmethod
    def _write_run_outputs(
        context: RunContext,
        final_result: SkillResult,
        tool_results: list[tuple[SkillCall, SkillResult]],
    ) -> None:
        run_dir = PydanticAIRuntime._resolve_run_dir(context)
        summary_path = Path(context.config.get("summary_path") or run_dir / "run_summary.json")
        memory_path = Path(
            context.config.get("memory_candidates_path") or run_dir / "memory_candidates.json"
        )
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        memory_path.parent.mkdir(parents=True, exist_ok=True)

        results = [result for _, result in tool_results] + [final_result]
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
        steps = [
            PydanticAIRuntime._tool_step_summary(call, result)
            for call, result in tool_results
        ]
        steps.append(
            {
                "step_id": "pydantic_ai_runtime",
                "skill": final_result.skill_name,
                "status": "succeeded" if final_result.success else "failed",
                "success": final_result.success,
                "summary": final_result.summary,
                "artifacts": [artifact.model_dump(mode="json") for artifact in final_result.artifacts],
                "warnings": final_result.warnings,
                "error": final_result.error.model_dump(mode="json") if final_result.error else None,
            }
        )

        summary = {
            "run_id": context.run_id,
            "runtime": "pydantic_ai",
            "status": "completed" if final_result.success else "failed",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "result_count": len(results),
            "steps": steps,
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
    def _tool_step_summary(call: SkillCall, result: SkillResult) -> dict[str, Any]:
        return {
            "step_id": call.id,
            "skill": result.skill_name,
            "status": "succeeded" if result.success else "failed",
            "success": result.success,
            "summary": result.summary,
            "artifacts": [artifact.model_dump(mode="json") for artifact in result.artifacts],
            "warnings": result.warnings,
            "error": result.error.model_dump(mode="json") if result.error else None,
        }

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

    @staticmethod
    def _write_trace(
        context: RunContext,
        step_id: str,
        status: str,
        output_summary: str = "",
    ) -> None:
        if context.trace is None:
            return
        context.trace.write(
            TraceEvent(
                run_id=context.run_id,
                step_id=step_id,
                skill="pydantic_ai_agent",
                status=status,
                output_summary=output_summary,
            )
        )
