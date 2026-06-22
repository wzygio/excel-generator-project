"""Runtime selection for TaskSpec execution."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from shared_kernel.config import config as app_config
from yield_report.agent.letta_runtime import (
    LettaRuntime,
    LettaRuntimeConfig,
    LettaRuntimeUnavailableError,
)
from yield_report.agent.omp_runtime import OmpJsonRuntime, OmpRuntimeUnavailableError
from yield_report.agent.registry import build_default_runtime
from yield_report.agent.spec_model import RunContext, SkillResult, TaskSpec


class RuntimeRunResult(BaseModel):
    """Structured result for a TaskSpec runtime invocation."""

    runtime: str
    results: list[SkillResult] = Field(default_factory=list)
    fallback_attempted: bool = False

    @property
    def success(self) -> bool:
        return bool(self.results) and all(result.success for result in self.results)

    @property
    def status(self) -> str:
        return "completed" if self.success else "failed"

    @property
    def summary(self) -> str:
        if not self.results:
            return "No runtime results."
        return "\n".join(result.summary for result in self.results if result.summary)


class PythonSkillRuntime:
    """Adapter around the existing deterministic Python Skill runtime."""

    runtime_name = "python"

    def run_spec(self, spec: TaskSpec, context: RunContext) -> list[SkillResult]:
        return build_default_runtime().run_spec(spec, context)


class SpecRuntime(Protocol):
    """Runtime object that can execute a TaskSpec."""

    def run_spec(self, spec: TaskSpec, context: RunContext) -> list[SkillResult]:
        ...


class RuntimeRouter:
    """Choose a runtime according to user request and TaskSpec constraints.

    `auto` follows the configured default runtime. Letta is the Agent runtime;
    Python remains available as an explicit deterministic Skill execution path.
    """

    def __init__(
        self,
        python_runtime: SpecRuntime | None = None,
        omp_runtime: SpecRuntime | None = None,
        letta_runtime: SpecRuntime | None = None,
        default_runtime: str | None = None,
    ) -> None:
        self.python_runtime = python_runtime or PythonSkillRuntime()
        self.omp_runtime = omp_runtime or OmpJsonRuntime()
        self.letta_runtime = letta_runtime or LettaRuntime(config=_configured_letta_runtime_config())
        self.default_runtime = (default_runtime or _configured_default_runtime()).lower().strip()

    def run_spec(
        self,
        spec: TaskSpec,
        context: RunContext,
        requested_runtime: str = "auto",
    ) -> RuntimeRunResult:
        requested = (requested_runtime or "auto").lower().strip()
        if requested == "letta":
            return self._run_letta(spec, context)
        if requested in {"omp", "pi"}:
            return self._run_omp(spec, context)
        if requested == "python":
            results = self.python_runtime.run_spec(spec, context)
            return RuntimeRunResult(runtime="python", results=results)

        runtime_hint = str(spec.constraints.get("runtime") or "").lower()
        if runtime_hint in {"python", "python_skill", "python_skills"}:
            results = self.python_runtime.run_spec(spec, context)
            return RuntimeRunResult(runtime="python", results=results)
        if runtime_hint == "letta":
            return self._run_letta(spec, context)
        if runtime_hint in {"omp", "pi"}:
            return self._run_omp_with_python_fallback(spec, context)

        if requested == "auto":
            return self._run_default(spec, context)

        results = self.python_runtime.run_spec(spec, context)
        return RuntimeRunResult(runtime="python", results=results)

    def _run_default(self, spec: TaskSpec, context: RunContext) -> RuntimeRunResult:
        if self.default_runtime == "letta":
            return self._run_letta(spec, context)
        if self.default_runtime in {"omp", "pi"}:
            return self._run_omp_with_python_fallback(spec, context)
        results = self.python_runtime.run_spec(spec, context)
        return RuntimeRunResult(runtime="python", results=results)

    def _run_omp(self, spec: TaskSpec, context: RunContext) -> RuntimeRunResult:
        try:
            results = self.omp_runtime.run_spec(spec, context)
        except OmpRuntimeUnavailableError as exc:
            raise RuntimeError(str(exc)) from exc
        return RuntimeRunResult(runtime="omp", results=results)

    def _run_omp_with_python_fallback(
        self,
        spec: TaskSpec,
        context: RunContext,
    ) -> RuntimeRunResult:
        result = self._run_omp(spec, context)
        if result.success or not _should_fallback_from_omp(result):
            return result

        python_results = self.python_runtime.run_spec(spec, context)
        _add_fallback_warning(python_results, result.summary)
        return RuntimeRunResult(
            runtime="python",
            results=python_results,
            fallback_attempted=True,
        )

    def _run_letta(self, spec: TaskSpec, context: RunContext) -> RuntimeRunResult:
        try:
            results = self.letta_runtime.run_spec(spec, context)
        except LettaRuntimeUnavailableError as exc:
            raise RuntimeError(str(exc)) from exc
        return RuntimeRunResult(runtime="letta", results=results)


def _configured_default_runtime() -> str:
    try:
        return app_config.get().agent.default_runtime
    except Exception:
        return "python"


def _should_fallback_from_omp(result: RuntimeRunResult) -> bool:
    """Return true when OMP failed before producing a useful task result."""
    if result.success:
        return False
    fallback_error_codes = {"omp.start_failed", "omp.nonzero_exit"}
    for skill_result in result.results:
        error = skill_result.error
        if error and error.code in fallback_error_codes:
            return True
        message = " ".join(
            [
                skill_result.summary or "",
                error.message if error else "",
                str(error.details if error else ""),
            ]
        )
        if any(
            marker in message
            for marker in [
                "ReferenceError: window is not defined",
                "isMCPToolName",
                "swagger-ui-bundle",
            ]
        ):
            return True
    return False


def _add_fallback_warning(results: list[SkillResult], omp_summary: str) -> None:
    if not results:
        return
    warning = (
        "Pi/OMP runtime failed before completing the task; "
        "fell back to deterministic Python Skill runtime."
    )
    if omp_summary:
        warning = f"{warning} Original OMP summary: {omp_summary[:500]}"
    results[0].warnings.insert(0, warning)


def _configured_letta_runtime_config() -> LettaRuntimeConfig:
    try:
        settings = app_config.get().agent.letta
    except Exception:
        return LettaRuntimeConfig()
    defaults = LettaRuntimeConfig()
    return LettaRuntimeConfig(
        base_url=settings.base_url,
        api_key_env=settings.api_key_env,
        server_password_env=settings.server_password_env,
        agent_id=settings.agent_id,
        agent_name=settings.agent_name,
        agent_id_cache_path=settings.agent_id_cache_path,
        model=settings.model,
        embedding=settings.embedding,
        sync_memory_blocks=getattr(settings, "sync_memory_blocks", defaults.sync_memory_blocks),
        archive_memory_candidates=getattr(
            settings,
            "archive_memory_candidates",
            defaults.archive_memory_candidates,
        ),
        use_conversations=getattr(settings, "use_conversations", defaults.use_conversations),
        compaction_mode=getattr(settings, "compaction_mode", defaults.compaction_mode),
        compaction_clip_chars=getattr(
            settings,
            "compaction_clip_chars",
            defaults.compaction_clip_chars,
        ),
        compaction_prompt=getattr(settings, "compaction_prompt", defaults.compaction_prompt),
        streaming=getattr(settings, "streaming", defaults.streaming),
        stream_tokens=getattr(settings, "stream_tokens", defaults.stream_tokens),
        background_runs=getattr(settings, "background_runs", defaults.background_runs),
        timeout_seconds=settings.timeout_seconds,
        max_tool_rounds=settings.max_tool_rounds,
    )
