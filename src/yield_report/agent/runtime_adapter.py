"""Runtime selection for TaskSpec execution."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from yield_report.shared_kernel.config import config as app_config
from yield_report.agent.letta_runtime import (
    LettaRuntime,
    LettaRuntimeConfig,
    LettaRuntimeUnavailableError,
)
from yield_report.agent.pydantic_ai_runtime import (
    PydanticAIRuntime,
    PydanticAIRuntimeConfig,
    PydanticAIRuntimeUnavailableError,
)
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


PYTHON_EXEMPT_CAPABILITIES = {"daily-report", "anomaly-monitor"}


class RuntimeRouter:
    """Choose the single Agent runtime, with narrow fixed-flow exemptions.

    Pydantic AI is the default Agent runtime. Letta remains available as an
    explicit optional stateful runtime. Deterministic Python Skill execution is
    allowed only for rule-built, fixed business workflows whose capability is
    explicitly exempted by project policy.
    """

    def __init__(
        self,
        python_runtime: SpecRuntime | None = None,
        omp_runtime: SpecRuntime | None = None,
        letta_runtime: SpecRuntime | None = None,
        pydantic_ai_runtime: SpecRuntime | None = None,
        default_runtime: str | None = None,
    ) -> None:
        del omp_runtime
        self.python_runtime = python_runtime or PythonSkillRuntime()
        self.letta_runtime = letta_runtime or LettaRuntime(config=_configured_letta_runtime_config())
        self.pydantic_ai_runtime = pydantic_ai_runtime or PydanticAIRuntime(
            config=_configured_pydantic_ai_runtime_config()
        )
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
        if requested in {"pydantic_ai", "pydantic-ai", "pydantic"}:
            return self._run_pydantic_ai(spec, context)
        if requested == "python":
            return self._run_python_exemption(spec, context)
        if requested in {"omp", "pi"}:
            raise RuntimeError("OMP/Pi runtime is disabled. Use Pydantic AI or Letta.")

        runtime_hint = str(spec.constraints.get("runtime") or "").lower()
        if runtime_hint in {"python", "python_skill", "python_skills"}:
            return self._run_python_exemption(spec, context)
        if runtime_hint == "letta":
            return self._run_letta(spec, context)
        if runtime_hint in {"pydantic_ai", "pydantic-ai", "pydantic"}:
            return self._run_pydantic_ai(spec, context)
        if runtime_hint in {"omp", "pi"}:
            raise RuntimeError("TaskSpec requests disabled OMP/Pi runtime. Use Pydantic AI or Letta.")

        if requested == "auto":
            return self._run_default(spec, context)

        raise RuntimeError(f"Unsupported runtime: {requested_runtime}")

    def _run_default(self, spec: TaskSpec, context: RunContext) -> RuntimeRunResult:
        if _is_python_exempt_spec(spec):
            return self._run_python_exemption(spec, context)
        if self.default_runtime in {"", "auto", "pydantic_ai", "pydantic-ai", "pydantic"}:
            return self._run_pydantic_ai(spec, context)
        if self.default_runtime == "letta":
            return self._run_letta(spec, context)
        if self.default_runtime == "python":
            raise RuntimeError(
                "Configured default runtime is disabled by policy: "
                f"{self.default_runtime}. Use pydantic_ai or letta."
            )
        raise RuntimeError(f"Unsupported default runtime: {self.default_runtime}")

    def _run_python_exemption(self, spec: TaskSpec, context: RunContext) -> RuntimeRunResult:
        if not _is_python_exempt_spec(spec):
            raise RuntimeError(
                "Python runtime is allowed only for rule-built fixed business "
                "exemptions: daily-report and anomaly-monitor."
            )
        results = self.python_runtime.run_spec(spec, context)
        return RuntimeRunResult(runtime="python", results=results)

    def _run_letta(self, spec: TaskSpec, context: RunContext) -> RuntimeRunResult:
        try:
            results = self.letta_runtime.run_spec(spec, context)
        except LettaRuntimeUnavailableError as exc:
            raise RuntimeError(str(exc)) from exc
        return RuntimeRunResult(runtime="letta", results=results)

    def _run_pydantic_ai(self, spec: TaskSpec, context: RunContext) -> RuntimeRunResult:
        try:
            results = self.pydantic_ai_runtime.run_spec(spec, context)
        except PydanticAIRuntimeUnavailableError as exc:
            raise RuntimeError(str(exc)) from exc
        return RuntimeRunResult(runtime="pydantic_ai", results=results)


def _configured_default_runtime() -> str:
    try:
        return app_config.get().agent.default_runtime
    except Exception:
        return "pydantic_ai"


def _is_python_exempt_spec(spec: TaskSpec) -> bool:
    constraints = spec.constraints
    capability = _normalize_capability(str(constraints.get("capability") or ""))
    if capability not in PYTHON_EXEMPT_CAPABILITIES:
        return False
    if constraints.get("fixed_flow") is not True:
        return False
    builder = str(
        constraints.get("builder_mode")
        or constraints.get("spec_builder")
        or ""
    ).lower()
    return builder == "rule"


def _normalize_capability(value: str) -> str:
    return value.strip().lower().replace("_", "-")


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


def _configured_pydantic_ai_runtime_config() -> PydanticAIRuntimeConfig:
    try:
        cfg = app_config.get()
        settings = cfg.agent.pydantic_ai
        llm_settings = cfg.llm.deepseek
    except Exception:
        return PydanticAIRuntimeConfig()

    defaults = PydanticAIRuntimeConfig()
    return PydanticAIRuntimeConfig(
        model=settings.model or llm_settings.model_name or defaults.model,
        base_url=settings.base_url or llm_settings.base_url or defaults.base_url,
        api_key_env=settings.api_key_env,
        api_key=llm_settings.api_key,
        request_limit=getattr(settings, "request_limit", defaults.request_limit),
        max_tool_calls=getattr(settings, "max_tool_calls", defaults.max_tool_calls),
        tool_timeout_seconds=getattr(
            settings,
            "tool_timeout_seconds",
            defaults.tool_timeout_seconds,
        ),
        require_tool_use_for_workflow=getattr(
            settings,
            "require_tool_use_for_workflow",
            defaults.require_tool_use_for_workflow,
        ),
    )
