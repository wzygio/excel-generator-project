from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from yield_report.agent.pydantic_ai_runtime import (
    PydanticAIRuntime,
    PydanticAIRuntimeOutput,
)
from yield_report.agent.runtime_adapter import RuntimeRouter
from yield_report.agent.spec_model import (
    ArtifactRef,
    MemoryCandidate,
    RunContext,
    SkillCall,
    SkillResult,
    TaskSpec,
)


def test_pydantic_ai_runtime_dispatches_project_tool_and_writes_outputs(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "analysis.md"

    class FakeProjectRuntime:
        def __init__(self) -> None:
            self.calls = []

        def run_call(self, call, context):
            self.calls.append(call)
            assert call.skill == "data_analysis"
            assert call.input["question"] == "分析 M678 月度良率趋势"
            return SkillResult(
                skill_name="data_analysis",
                success=True,
                summary="M678 月度良率趋势分析完成",
                artifacts=[
                    ArtifactRef(kind="markdown", path=output_path, description="analysis")
                ],
                data={"row_count": 12},
                memory_updates=[
                    MemoryCandidate(
                        record_id="mem-m678-trend",
                        summary="M678 月度良率趋势分析记忆候选",
                    )
                ],
            )

    class FakeAgent:
        def __init__(self) -> None:
            self.prompt = ""
            self.usage_limits = None

        def run_sync(self, prompt, *, deps, usage_limits):
            self.prompt = prompt
            self.usage_limits = usage_limits
            deps.runtime_payload = deps  # type: ignore[attr-defined]
            runtime._execute_project_tool(
                deps,
                "yield_data_analysis",
                {"question": "分析 M678 月度良率趋势"},
            )
            return SimpleNamespace(
                output=PydanticAIRuntimeOutput(
                    status="completed",
                    summary="Pydantic AI 已调用 data_analysis 并完成分析。",
                )
            )

    fake_agent = FakeAgent()
    fake_project_runtime = FakeProjectRuntime()
    runtime = PydanticAIRuntime(
        agent=fake_agent,
        project_runtime=fake_project_runtime,
    )
    run_dir = tmp_path / "specs" / "runs" / "run-pydantic-ai-tools"
    context = RunContext(
        run_id="run-pydantic-ai-tools",
        workspace=tmp_path,
        spec_path=run_dir / "spec.yaml",
        output_dir=run_dir / "outputs",
        config={
            "run_dir": str(run_dir),
            "summary_path": str(run_dir / "run_summary.json"),
            "memory_candidates_path": str(run_dir / "memory_candidates.json"),
        },
    )
    spec = TaskSpec(
        run_id=context.run_id,
        user_goal="分析 M678 月度良率趋势",
        workflow=[
            SkillCall(
                id="analyze",
                skill="data_analysis",
                input={"question": "分析 M678 月度良率趋势"},
            )
        ],
    )

    results = runtime.run_spec(spec, context)

    assert results[0].success is True
    assert results[0].data["runtime"] == "pydantic_ai"
    assert fake_project_runtime.calls[0].id == "pydantic_ai_yield_data_analysis"
    assert "yield_data_analysis" in fake_agent.prompt
    assert fake_agent.usage_limits.tool_calls_limit == 20
    run_summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    memory_candidates = json.loads(
        (run_dir / "memory_candidates.json").read_text(encoding="utf-8")
    )
    assert run_summary["runtime"] == "pydantic_ai"
    assert [step["step_id"] for step in run_summary["steps"]] == [
        "pydantic_ai_yield_data_analysis",
        "pydantic_ai_runtime",
    ]
    assert memory_candidates[0]["record_id"] == "mem-m678-trend"


def test_pydantic_ai_runtime_fails_when_workflow_gets_no_tool_call(
    tmp_path: Path,
) -> None:
    class FakeAgent:
        def run_sync(self, prompt, *, deps, usage_limits):
            return SimpleNamespace(
                output=PydanticAIRuntimeOutput(
                    status="completed",
                    summary="Agent returned without tool calls.",
                )
            )

    context = RunContext(run_id="run-no-tool", workspace=tmp_path)
    spec = TaskSpec(
        run_id=context.run_id,
        workflow=[SkillCall(id="analyze", skill="data_analysis", input={})],
    )

    results = PydanticAIRuntime(agent=FakeAgent()).run_spec(spec, context)

    assert results[0].success is False
    assert results[0].error is not None
    assert results[0].error.code == "pydantic_ai.workflow.no_tool_calls"


def test_pydantic_ai_runtime_fails_closed_for_unknown_workflow(
    tmp_path: Path,
) -> None:
    context = RunContext(run_id="run-unknown-pydantic-ai", workspace=tmp_path)
    spec = TaskSpec(
        run_id=context.run_id,
        workflow=[SkillCall(id="custom", skill="custom_unknown_skill", input={})],
    )

    results = PydanticAIRuntime(agent=object()).run_spec(spec, context)

    assert results[0].success is False
    assert results[0].error is not None
    assert results[0].error.code == "pydantic_ai.unavailable"


def test_runtime_router_auto_uses_pydantic_ai_default(tmp_path: Path) -> None:
    class FakePython:
        def run_spec(self, spec: TaskSpec, context: RunContext):
            raise AssertionError("auto non-exempt runtime must not call Python")

    class FakeLetta:
        def run_spec(self, spec: TaskSpec, context: RunContext):
            raise AssertionError("auto default should use Pydantic AI")

    class FakePydanticAI:
        def run_spec(self, spec: TaskSpec, context: RunContext):
            return [
                SkillResult(
                    skill_name="pydantic_ai_agent",
                    success=True,
                    summary="pydantic ok",
                )
            ]

    result = RuntimeRouter(
        python_runtime=FakePython(),
        letta_runtime=FakeLetta(),
        pydantic_ai_runtime=FakePydanticAI(),
        default_runtime="pydantic_ai",
    ).run_spec(
        TaskSpec(run_id="run-router-pydantic-ai"),
        RunContext(run_id="run-router-pydantic-ai", workspace=tmp_path),
        requested_runtime="auto",
    )

    assert result.runtime == "pydantic_ai"
    assert result.success is True


def test_runtime_router_keeps_explicit_letta_runtime(tmp_path: Path) -> None:
    class FakeLetta:
        def run_spec(self, spec: TaskSpec, context: RunContext):
            return [SkillResult(skill_name="letta_agent", success=True, summary="letta ok")]

    class FakePydanticAI:
        def run_spec(self, spec: TaskSpec, context: RunContext):
            raise AssertionError("explicit letta must not call Pydantic AI")

    result = RuntimeRouter(
        letta_runtime=FakeLetta(),
        pydantic_ai_runtime=FakePydanticAI(),
    ).run_spec(
        TaskSpec(run_id="run-router-letta"),
        RunContext(run_id="run-router-letta", workspace=tmp_path),
        requested_runtime="letta",
    )

    assert result.runtime == "letta"
    assert result.success is True
