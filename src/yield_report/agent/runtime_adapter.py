"""Runtime selection for TaskSpec execution."""

from __future__ import annotations

from pydantic import BaseModel, Field

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


class RuntimeRouter:
    """Choose a runtime according to user request and TaskSpec constraints.

    `auto` is OMP-first. The Python runtime remains available as an explicit
    deterministic tool/debug path, but it is no longer the Agent Runtime picked
    by the workbench.
    """

    def __init__(
        self,
        python_runtime: PythonSkillRuntime | None = None,
        omp_runtime: OmpJsonRuntime | None = None,
    ) -> None:
        self.python_runtime = python_runtime or PythonSkillRuntime()
        self.omp_runtime = omp_runtime or OmpJsonRuntime()

    def run_spec(
        self,
        spec: TaskSpec,
        context: RunContext,
        requested_runtime: str = "auto",
    ) -> RuntimeRunResult:
        requested = (requested_runtime or "auto").lower().strip()
        if requested in {"omp", "pi"}:
            return self._run_omp(spec, context)
        if requested == "python":
            results = self.python_runtime.run_spec(spec, context)
            return RuntimeRunResult(runtime="python", results=results)

        runtime_hint = str(spec.constraints.get("runtime") or "").lower()
        if runtime_hint in {"omp", "pi"}:
            return self._run_omp(spec, context)

        if requested == "auto":
            return self._run_omp(spec, context)

        results = self.python_runtime.run_spec(spec, context)
        return RuntimeRunResult(runtime="python", results=results)

    def _run_omp(self, spec: TaskSpec, context: RunContext) -> RuntimeRunResult:
        try:
            results = self.omp_runtime.run_spec(spec, context)
        except OmpRuntimeUnavailableError as exc:
            raise RuntimeError(str(exc)) from exc
        return RuntimeRunResult(runtime="omp", results=results)
