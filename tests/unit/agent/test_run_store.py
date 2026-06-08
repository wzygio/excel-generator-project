from __future__ import annotations

from pathlib import Path

from yield_report.agent.run_store import RunStore
from yield_report.agent.spec_model import SkillCall, TaskSpec
from yield_report.agent.trace import TraceWriter


def test_run_store_creates_standard_run_paths(tmp_path: Path) -> None:
    store = RunStore(workspace=tmp_path)

    paths = store.create_run("run-fixed")

    assert paths.run_dir == tmp_path / "specs" / "runs" / "run-fixed"
    assert paths.spec_path == paths.run_dir / "spec.yaml"
    assert paths.trace_path == paths.run_dir / "trace.jsonl"
    assert paths.output_dir == paths.run_dir / "outputs"
    assert paths.memory_candidates_path == paths.run_dir / "memory_candidates.json"
    assert paths.summary_path == paths.run_dir / "run_summary.json"
    assert paths.output_dir.exists()


def test_run_store_saves_and_loads_task_spec(tmp_path: Path) -> None:
    store = RunStore(workspace=tmp_path)
    paths = store.create_run("run-save-load")
    spec = TaskSpec(
        run_id=paths.run_id,
        status="ready",
        user_goal="生成 M678 今天良率日报",
        workflow=[SkillCall(id="analyze", skill="data_analysis")],
        outputs={"analysis_summary": {"required": True, "format": "markdown"}},
    )

    store.save_spec(spec, paths.spec_path)
    loaded = store.load_spec(paths.spec_path)

    assert loaded.run_id == "run-save-load"
    assert loaded.status == "ready"
    assert loaded.workflow[0].skill == "data_analysis"


def test_run_store_make_context_points_to_run_directory(tmp_path: Path) -> None:
    store = RunStore(workspace=tmp_path)
    paths = store.create_run("run-context")
    spec = TaskSpec(run_id="run-context", workflow=[])

    context = store.make_context(paths.spec_path, spec)

    assert context.run_id == "run-context"
    assert context.workspace == tmp_path
    assert context.spec_path == paths.spec_path
    assert context.output_dir == paths.output_dir
    assert isinstance(context.trace, TraceWriter)
    assert context.trace.trace_path == paths.trace_path
    assert context.config["memory_candidates_path"] == str(paths.memory_candidates_path)
