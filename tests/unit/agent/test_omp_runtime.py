from __future__ import annotations

import subprocess
from pathlib import Path

from yield_report.agent.omp_runtime import OmpJsonRuntime, OmpRuntimeConfig
from yield_report.agent.runtime_adapter import RuntimeRouter
from yield_report.agent.spec_model import RunContext, SkillCall, SkillResult, TaskSpec


def test_omp_runtime_builds_run_scoped_prompt_and_parses_events(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout='{"type":"message","message":"分析完成"}\n',
            stderr="",
        )

    monkeypatch.setattr("shutil.which", lambda command: command)
    monkeypatch.setattr("subprocess.run", fake_run)
    run_dir = tmp_path / "specs" / "runs" / "run-pi"
    context = RunContext(
        run_id="run-pi",
        workspace=tmp_path,
        spec_path=run_dir / "spec.yaml",
        output_dir=run_dir / "outputs",
        config={"run_dir": str(run_dir)},
    )
    runtime = OmpJsonRuntime(config=OmpRuntimeConfig(command="omp", timeout_seconds=5))

    results = runtime.run_spec(
        TaskSpec(
            run_id="run-pi",
            workflow=[SkillCall(id="analyze", skill="data_analysis")],
            outputs={"analysis_summary": {"required": True}},
        ),
        context,
    )

    assert results[0].success is True
    assert "分析完成" in results[0].data["result_text"]
    assert (run_dir / "pi_prompt.md").exists()
    assert (run_dir / "pi_events.jsonl").exists()
    assert "--mode" in calls[0]
    assert "--session-dir" in calls[0]


def test_omp_runtime_returns_structured_failure_on_nonzero_exit(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(args=command, returncode=7, stdout="", stderr="bad auth")

    monkeypatch.setattr("shutil.which", lambda command: command)
    monkeypatch.setattr("subprocess.run", fake_run)
    run_dir = tmp_path / "specs" / "runs" / "run-pi-fail"
    context = RunContext(
        run_id="run-pi-fail",
        workspace=tmp_path,
        spec_path=run_dir / "spec.yaml",
        output_dir=run_dir / "outputs",
        config={"run_dir": str(run_dir)},
    )

    results = OmpJsonRuntime().run_spec(TaskSpec(run_id="run-pi-fail"), context)

    assert results[0].success is False
    assert results[0].error is not None
    assert results[0].error.code == "omp.nonzero_exit"


def test_runtime_router_uses_python_then_pi_fallback(tmp_path: Path) -> None:
    class FakePython:
        def run_spec(self, spec: TaskSpec, context: RunContext):
            return [SkillResult(skill_name="data_analysis", success=False, summary="failed")]

    class FakeOmp:
        def run_spec(self, spec: TaskSpec, context: RunContext):
            return [SkillResult(skill_name="pi_agent", success=True, summary="pi ok")]

    spec = TaskSpec(
        run_id="run-router",
        constraints={"runtime": "python_with_pi_fallback"},
        workflow=[SkillCall(id="analyze", skill="data_analysis")],
        outputs={"analysis_summary": {"required": True}},
    )

    result = RuntimeRouter(python_runtime=FakePython(), omp_runtime=FakeOmp()).run_spec(
        spec,
        RunContext(run_id="run-router", workspace=tmp_path),
        requested_runtime="auto",
    )

    assert result.runtime == "omp"
    assert result.fallback_attempted is True
    assert result.success is True
