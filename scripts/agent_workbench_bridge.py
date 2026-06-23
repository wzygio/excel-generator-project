"""JSON bridge for the CopilotKit Agent Workbench."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import traceback
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

WORKSPACE = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE / "src"
for path in (WORKSPACE, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
if hasattr(sys.stdout, "reconfigure"):
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")
for stream in (sys.stderr, sys.stdin):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")
load_dotenv(WORKSPACE / ".env")

from yield_report.agent.run_store import RunStore  # noqa: E402
from yield_report.agent.runtime_adapter import RuntimeRouter  # noqa: E402
from yield_report.agent.spec_builder import SpecBuilder, SpecBuildRequest  # noqa: E402
from yield_report.skills.data_analysis import tool as data_analysis_tool  # noqa: E402


def main() -> None:
    payload = _read_payload()
    captured_stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured_stdout):
            response = dispatch(payload)
        extra_stdout = captured_stdout.getvalue().strip()
        if extra_stdout:
            response.setdefault("diagnostics", {})["stdout"] = extra_stdout
    except Exception as exc:
        response = {
            "success": False,
            "summary": f"Agent Workbench bridge failed: {exc}",
            "error": {
                "code": "agent_workbench_bridge.failed",
                "message": str(exc),
                "recoverable": True,
                "details": {"traceback": traceback.format_exc()},
            },
        }
    json.dump(response, sys.stdout, ensure_ascii=False, default=str)


def dispatch(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "create_and_run").strip()
    workspace = Path(payload.get("workspace") or WORKSPACE).resolve()
    store = RunStore(workspace=workspace)

    if action == "create_spec":
        result = _create_spec(payload, store)
        return _build_response(result=result)

    if action == "run_spec":
        spec_path = Path(str(payload["spec_path"]))
        runtime = str(payload.get("runtime") or "auto")
        run_result = _run_spec(store=store, spec_path=spec_path, runtime=runtime)
        return _run_response(store=store, spec_path=spec_path, run_result=run_result)

    if action == "create_and_run":
        result = _create_spec(payload, store)
        run_result = _run_spec(
            store=store,
            spec_path=result.spec_path,
            runtime=str(payload.get("runtime") or "auto"),
        )
        return _run_response(store=store, spec_path=result.spec_path, run_result=run_result)

    if action == "get_run":
        run_id = str(payload.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("run_id is required")
        paths = store.create_run(run_id)
        return _snapshot_response(paths.spec_path)

    if action in {"confirm_memory", "reject_memory", "correct_memory"}:
        record_id = str(payload.get("record_id") or "").strip()
        if not record_id:
            raise ValueError("record_id is required")
        if action == "confirm_memory":
            record = data_analysis_tool.confirm_memory(record_id)
            summary = f"已确认记忆: {record_id}"
        elif action == "correct_memory":
            correction = str(payload.get("correction") or payload.get("correction_text") or "").strip()
            if not correction:
                raise ValueError("correction is required")
            record = data_analysis_tool.correct_memory(record_id, correction)
            summary = f"已记录修正: {record_id}"
        else:
            record = data_analysis_tool.reject_memory(record_id)
            summary = f"已拒绝记忆: {record_id}"
        return {
            "success": True,
            "summary": summary,
            "data": {"record_id": record_id, "record": _jsonable(record)},
        }

    raise ValueError(f"Unsupported action: {action}")


def _create_spec(payload: dict[str, Any], store: RunStore):
    goal = str(payload.get("goal") or payload.get("query") or "").strip()
    if not goal:
        raise ValueError("goal is required")
    raw_options = payload.get("options")
    options: dict[str, Any] = raw_options if isinstance(raw_options, dict) else {}
    builder = SpecBuilder(store=store)
    return builder.build(
        SpecBuildRequest(
            user_goal=goal,
            run_id=_optional_string(payload.get("run_id") or options.get("run_id")),
            source=_optional_string(payload.get("source") or options.get("source")) or "agent",
            capability=_optional_string(payload.get("capability") or options.get("capability")),
            fixed_flow=_bool_option(payload.get("fixed_flow") or options.get("fixed_flow")),
            report_date=_optional_string(options.get("report_date")),
            product_models=_string_list(options.get("product_models")),
            sections=_string_list(options.get("sections")) or [],
            builder_mode=str(options.get("builder_mode") or payload.get("builder_mode") or "auto"),
        )
    )


def _run_spec(store: RunStore, spec_path: Path, runtime: str):
    spec = store.load_spec(spec_path)
    context = store.make_context(spec_path, spec)
    return RuntimeRouter().run_spec(spec, context, requested_runtime=runtime)


def _build_response(*, result) -> dict[str, Any]:
    return {
        "success": not any(issue.severity == "error" for issue in result.validation_issues),
        "run_id": result.paths.run_id,
        "spec_path": str(result.spec_path),
        "status": result.spec.status,
        "summary": "TaskSpec created.",
        "warnings": result.warnings,
        "validation_issues": [issue.model_dump(mode="json") for issue in result.validation_issues],
        "spec": result.spec.model_dump(mode="json"),
        "paths": _paths_payload(result.paths),
    }


def _run_response(*, store: RunStore, spec_path: Path, run_result) -> dict[str, Any]:
    paths = store.paths_for_spec(spec_path)
    snapshot = _snapshot(paths.spec_path)
    results = [result.model_dump(mode="json") for result in run_result.results]
    artifacts = [
        artifact
        for result in results
        for artifact in result.get("artifacts", [])
    ]
    memory_updates = [
        update
        for result in results
        for update in result.get("memory_updates", [])
    ]
    return {
        "success": run_result.success,
        "run_id": paths.run_id,
        "runtime": run_result.runtime,
        "status": run_result.status,
        "summary": run_result.summary,
        "spec_path": str(paths.spec_path),
        "spec": snapshot.get("spec"),
        "results": results,
        "artifacts": artifacts,
        "memory_updates": memory_updates,
        "warnings": [warning for result in results for warning in result.get("warnings", [])],
        "data": {
            "run_id": paths.run_id,
            "runtime": run_result.runtime,
            "summary": snapshot.get("summary"),
            "trace": snapshot.get("trace", []),
            "memory_candidates": snapshot.get("memory_candidates", []),
            "results": results,
            "workflow_steps": _workflow_steps(snapshot, results),
        },
        "paths": _paths_payload(paths),
    }


def _snapshot_response(spec_path: Path) -> dict[str, Any]:
    snapshot = _snapshot(spec_path)
    return {
        "success": True,
        "run_id": Path(spec_path).resolve().parent.name,
        "summary": "Run snapshot loaded.",
        **snapshot,
    }


def _snapshot(spec_path: Path) -> dict[str, Any]:
    spec_path = spec_path if spec_path.is_absolute() else WORKSPACE / spec_path
    run_dir = spec_path.resolve().parent
    summary_path = run_dir / "run_summary.json"
    memory_path = run_dir / "memory_candidates.json"
    trace_path = run_dir / "trace.jsonl"
    spec = _read_yaml_or_none(spec_path)
    return {
        "spec": spec,
        "summary": _read_json_or_none(summary_path),
        "memory_candidates": _read_json_or_empty_list(memory_path),
        "trace": _read_jsonl_tail(trace_path, limit=200),
    }


def _workflow_steps(snapshot: dict[str, Any], results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary = snapshot.get("summary") or {}
    steps = summary.get("steps")
    if isinstance(steps, list) and steps:
        return steps
    return [
        {
            "name": result.get("skill_name"),
            "status": "succeeded" if result.get("success") else "failed",
            "detail": result.get("summary", ""),
        }
        for result in results
    ]


def _paths_payload(paths) -> dict[str, str]:
    return {
        "run_dir": str(paths.run_dir),
        "spec_path": str(paths.spec_path),
        "trace_path": str(paths.trace_path),
        "output_dir": str(paths.output_dir),
        "memory_candidates_path": str(paths.memory_candidates_path),
        "summary_path": str(paths.summary_path),
    }


def _read_payload() -> dict[str, Any]:
    raw = sys.stdin.read().lstrip("\ufeff").strip()
    first_object = raw.find("{")
    first_array = raw.find("[")
    candidates = [index for index in (first_object, first_array) if index >= 0]
    if candidates:
        raw = raw[min(candidates):]
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Bridge payload must be a JSON object")
    return data


def _read_yaml_or_none(path: Path) -> Any | None:
    if not path.exists():
        return None
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _read_json_or_none(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_or_empty_list(path: Path) -> list[Any]:
    data = _read_json_or_none(path)
    return data if isinstance(data, list) else []


def _read_jsonl_tail(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False, default=str)
        return value
    except TypeError:
        return str(value)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        items = [item.strip() for item in value.replace("，", ",").split(",")]
    elif isinstance(value, list):
        items = [str(item).strip() for item in value]
    else:
        items = [str(value).strip()]
    cleaned = [item for item in items if item]
    return cleaned or None


def _bool_option(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "固定", "rule"}


if __name__ == "__main__":
    main()
