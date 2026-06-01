from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from yield_report.agent.runtime import AgentRuntime
from yield_report.agent.spec_model import RunContext, SkillCall, SkillResult, TaskSpec


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
