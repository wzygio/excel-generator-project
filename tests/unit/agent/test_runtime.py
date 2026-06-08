from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from yield_report.agent.runtime import AgentRuntime, AgentRuntimeError
from yield_report.agent.spec_model import (
    ArtifactRef,
    MemoryCandidate,
    RunContext,
    SkillCall,
    SkillError,
    SkillResult,
    TaskSpec,
)


class EchoRequest(BaseModel):
    value: str


class ReportRefRequest(BaseModel):
    report_ref: dict


def test_agent_runtime_executes_skill_and_saves_result(tmp_path: Path) -> None:
    runtime = AgentRuntime()

    def run_echo(request: EchoRequest, context: RunContext) -> SkillResult:
        return SkillResult(
            skill_name="echo",
            success=True,
            summary=f"echo {request.value}",
            data={"value": request.value, "run_id": context.run_id},
        )

    runtime.register("echo", EchoRequest, run_echo)
    context = RunContext(run_id="run-1", workspace=tmp_path)
    spec = TaskSpec(
        run_id="run-1",
        workflow=[
            SkillCall(
                id="step_echo",
                skill="echo",
                input={"value": "ok"},
                save_as="echo_result",
            )
        ],
    )

    results = runtime.run_spec(spec, context=context)

    assert len(results) == 1
    assert results[0].success is True
    assert context.recall("echo_result").data["value"] == "ok"


def test_agent_runtime_writes_trace(tmp_path: Path) -> None:
    runtime = AgentRuntime()

    def run_echo(request: EchoRequest, context: RunContext) -> SkillResult:
        return SkillResult(skill_name="echo", success=True, summary=request.value)

    runtime.register("echo", EchoRequest, run_echo)
    trace_path = tmp_path / "trace.jsonl"
    spec = TaskSpec(
        run_id="run-2",
        workflow=[SkillCall(id="step_echo", skill="echo", input={"value": "ok"})],
        trace={"path": str(trace_path)},
    )

    runtime.run_spec(spec, context=RunContext(run_id="run-2", workspace=tmp_path))

    events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert [event["status"] for event in events] == ["started", "succeeded"]
    assert events[0]["step_id"] == "step_echo"


def test_agent_runtime_resolves_report_alias_from_spec_inputs(tmp_path: Path) -> None:
    runtime = AgentRuntime()
    seen: dict[str, object] = {}

    def run_report_ref(request: ReportRefRequest, context: RunContext) -> SkillResult:
        seen["report_ref"] = request.report_ref
        return SkillResult(skill_name="report_ref", success=True, summary="ok")

    runtime.register("report_ref", ReportRefRequest, run_report_ref)
    spec = TaskSpec(
        run_id="run-3",
        inputs={
            "reports": [
                {
                    "alias": "daily_yield",
                    "report_type": "daily_yield",
                    "filters": {"product_models": ["M678"]},
                }
            ]
        },
        workflow=[
            SkillCall(
                id="download",
                skill="report_ref",
                input={"report_ref": "daily_yield"},
            )
        ],
    )

    runtime.run_spec(spec, context=RunContext(run_id="run-3", workspace=tmp_path))

    assert seen["report_ref"] == {
        "alias": "daily_yield",
        "report_type": "daily_yield",
        "filters": {"product_models": ["M678"]},
    }


def test_agent_runtime_resolves_relative_trace_to_run_dir(tmp_path: Path) -> None:
    runtime = AgentRuntime()

    def run_echo(request: EchoRequest, context: RunContext) -> SkillResult:
        return SkillResult(skill_name="echo", success=True, summary=request.value)

    runtime.register("echo", EchoRequest, run_echo)
    run_dir = tmp_path / "specs" / "runs" / "run-trace"
    spec = TaskSpec(
        run_id="run-trace",
        workflow=[SkillCall(id="step_echo", skill="echo", input={"value": "ok"})],
        trace={"path": "trace.jsonl"},
    )

    runtime.run_spec(
        spec,
        context=RunContext(
            run_id="run-trace",
            workspace=tmp_path,
            spec_path=run_dir / "spec.yaml",
            output_dir=run_dir / "outputs",
        ),
    )

    assert (run_dir / "trace.jsonl").exists()
    assert (run_dir / "run_summary.json").exists()
    assert (run_dir / "memory_candidates.json").exists()


def test_agent_runtime_writes_summary_artifacts_and_memory_candidates(tmp_path: Path) -> None:
    runtime = AgentRuntime()

    def run_echo(request: EchoRequest, context: RunContext) -> SkillResult:
        artifact = context.output_dir / "analysis.md"
        artifact.write_text("ok", encoding="utf-8")
        return SkillResult(
            skill_name="echo",
            success=True,
            summary="done",
            artifacts=[ArtifactRef(kind="markdown", path=artifact, description="analysis")],
            memory_updates=[
                MemoryCandidate(record_id="mem-1", summary="字段映射候选")
            ],
        )

    runtime.register("echo", EchoRequest, run_echo)
    run_dir = tmp_path / "specs" / "runs" / "run-summary"
    spec = TaskSpec(
        run_id="run-summary",
        workflow=[SkillCall(id="step_echo", skill="echo", input={"value": "ok"})],
    )

    runtime.run_spec(
        spec,
        context=RunContext(
            run_id="run-summary",
            workspace=tmp_path,
            spec_path=run_dir / "spec.yaml",
            output_dir=run_dir / "outputs",
        ),
    )

    summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    memory = json.loads((run_dir / "memory_candidates.json").read_text(encoding="utf-8"))
    assert summary["status"] == "completed"
    assert summary["steps"][0]["step_id"] == "step_echo"
    assert summary["artifacts"][0]["kind"] == "markdown"
    assert memory[0]["record_id"] == "mem-1"


def test_agent_runtime_stops_after_failed_step(tmp_path: Path) -> None:
    runtime = AgentRuntime()
    calls: list[str] = []

    def run_fail(request: EchoRequest, context: RunContext) -> SkillResult:
        calls.append("fail")
        return SkillResult(
            skill_name="fail",
            success=False,
            summary="blocked",
            error=SkillError(
                code="fail.blocked",
                message="blocked",
                recoverable=True,
                details={"reason": "test"},
            ),
        )

    def run_never(request: EchoRequest, context: RunContext) -> SkillResult:
        calls.append("never")
        return SkillResult(skill_name="never", success=True)

    runtime.register("fail", EchoRequest, run_fail)
    runtime.register("never", EchoRequest, run_never)
    run_dir = tmp_path / "specs" / "runs" / "run-failed"
    spec = TaskSpec(
        run_id="run-failed",
        workflow=[
            SkillCall(id="first", skill="fail", input={"value": "x"}),
            SkillCall(id="second", skill="never", input={"value": "y"}, depends_on=["first"]),
        ],
    )

    results = runtime.run_spec(
        spec,
        context=RunContext(
            run_id="run-failed",
            workspace=tmp_path,
            spec_path=run_dir / "spec.yaml",
            output_dir=run_dir / "outputs",
        ),
    )

    summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [result.skill_name for result in results] == ["fail"]
    assert calls == ["fail"]
    assert summary["status"] == "failed"
    assert events[-1]["error"]["recoverable"] is True
    assert "repair_hint" in events[-1]["error"]


def test_agent_runtime_unregistered_skill_writes_failed_trace(tmp_path: Path) -> None:
    runtime = AgentRuntime()
    run_dir = tmp_path / "specs" / "runs" / "run-unregistered"
    spec = TaskSpec(
        run_id="run-unregistered",
        workflow=[SkillCall(id="missing", skill="missing_skill")],
    )

    try:
        runtime.run_spec(
            spec,
            context=RunContext(
                run_id="run-unregistered",
                workspace=tmp_path,
                spec_path=run_dir / "spec.yaml",
                output_dir=run_dir / "outputs",
            ),
        )
    except AgentRuntimeError:
        pass
    else:
        raise AssertionError("AgentRuntimeError was not raised")

    events = [json.loads(line) for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events[0]["status"] == "failed"
    assert events[0]["error"]["code"] == "runtime.skill.unregistered"
