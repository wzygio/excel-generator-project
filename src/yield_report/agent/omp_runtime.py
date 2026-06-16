"""Oh-My-Pi / Pi runtime adapter for TaskSpec runs."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from yield_report.agent.spec_model import (
    ArtifactRef,
    RunContext,
    SkillError,
    SkillResult,
    TaskSpec,
)
from yield_report.agent.trace import TraceEvent


class OmpRuntimeConfig(BaseModel):
    """Configuration for invoking the local OMP/Pi CLI."""

    command: str = "omp"
    mode: str = "json"
    timeout_seconds: int = 900
    tools: list[str] = Field(default_factory=lambda: ["read", "grep", "find", "bash"])
    no_session: bool = True
    no_lsp: bool = True
    no_extensions: bool = True
    no_title: bool = True
    auto_approve: bool = True
    model: str | None = None


class OmpRuntimeUnavailableError(Exception):
    """Raised when OMP/Pi cannot be started."""


class OmpJsonRuntime:
    """Run a TaskSpec through OMP one-shot JSON event mode.

    The adapter asks OMP to operate as the Agent Runtime for the run directory
    and records OMP's event stream as an artifact. Existing Python Skills are
    exposed as project tools that OMP may call; they are not the default runtime.
    """

    runtime_name = "omp"

    def __init__(self, config: OmpRuntimeConfig | None = None) -> None:
        self.config = config or OmpRuntimeConfig()

    def is_available(self) -> bool:
        return self._resolve_command() is not None

    def run_spec(self, spec: TaskSpec, context: RunContext) -> list[SkillResult]:
        resolved_command = self._resolve_command()
        if resolved_command is None:
            raise OmpRuntimeUnavailableError(f"OMP command not found: {self.config.command}")

        run_dir = _run_dir(context)
        run_dir.mkdir(parents=True, exist_ok=True)
        context.output_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = run_dir / "pi_prompt.md"
        events_path = run_dir / "pi_events.jsonl"
        prompt = self._build_prompt(spec, context)
        prompt_path.write_text(prompt, encoding="utf-8")

        _write_trace(context, "pi_runtime", "started", input_summary=str(prompt_path))
        command = self._build_command(context, prompt_path, resolved_command)
        try:
            completed = subprocess.run(
                command,
                cwd=context.workspace,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=self.config.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raw_events = _timeout_output(exc)
            result = _runtime_failure_result(
                code="omp.timeout",
                message=f"OMP timed out after {self.config.timeout_seconds} seconds.",
                diagnostics={
                    "timeout_seconds": self.config.timeout_seconds,
                    "command": command,
                    "events_path": str(events_path),
                    "stderr": _timeout_stderr(exc),
                },
                context=context,
                run_dir=run_dir,
                events_path=events_path,
                raw_events=raw_events,
            )
            _write_trace(
                context,
                "pi_runtime",
                "failed",
                output_summary=result.summary,
                artifacts=[str(artifact.path) for artifact in result.artifacts],
            )
            return [result]
        except OSError as exc:
            result = _failed_result(
                "omp.start_failed",
                str(exc),
                {"command": command, "exception_type": type(exc).__name__},
            )
            _write_trace(context, "pi_runtime", "failed", output_summary=result.summary)
            return [result]

        raw_events = completed.stdout.strip()
        events_path.write_text(raw_events + ("\n" if raw_events else ""), encoding="utf-8")
        diagnostics = {
            "returncode": completed.returncode,
            "stderr": completed.stderr.strip(),
            "command": command,
            "events_path": str(events_path),
        }
        if completed.returncode != 0:
            result = _failed_result(
                "omp.nonzero_exit",
                completed.stderr.strip() or f"OMP exited with {completed.returncode}",
                diagnostics,
            )
            _write_trace(context, "pi_runtime", "failed", output_summary=result.summary)
            return [result]

        generated_markdowns = _collect_generated_markdowns(context.output_dir)
        text = (
            _read_preferred_markdown(generated_markdowns)
            or _extract_text_from_json_events(raw_events)
            or "OMP run completed."
        )
        summary_path = context.output_dir / "pi_summary.md"
        summary_path.write_text(text, encoding="utf-8")
        artifacts = _build_result_artifacts(
            summary_path=summary_path,
            events_path=events_path,
            generated_markdowns=generated_markdowns,
        )
        blocker = _read_blocker_from_trace(run_dir)
        if blocker:
            diagnostics["blocker"] = blocker
            result = SkillResult(
                skill_name="pi_agent",
                success=False,
                summary=f"Pi/OMP runtime blocked: {blocker}",
                artifacts=artifacts,
                error=SkillError(
                    code="omp.blocked",
                    message=blocker,
                    recoverable=True,
                    details=diagnostics,
                ),
                data={
                    "result_text": text,
                    "runtime": self.runtime_name,
                    "diagnostics": diagnostics,
                },
            )
            _write_trace(
                context,
                "pi_runtime",
                "blocked",
                output_summary=result.summary,
                artifacts=[str(artifact.path) for artifact in artifacts],
            )
            return [result]

        result = SkillResult(
            skill_name="pi_agent",
            success=True,
            summary="Pi/OMP runtime completed.",
            artifacts=artifacts,
            data={"result_text": text, "runtime": self.runtime_name, "diagnostics": diagnostics},
        )
        _write_trace(
            context,
            "pi_runtime",
            "succeeded",
            output_summary=result.summary,
            artifacts=[str(artifact.path) for artifact in artifacts],
        )
        return [result]

    def _resolve_command(self) -> str | None:
        command = (
            os.environ.get("YIELD_REPORT_OMP_COMMAND")
            or os.environ.get("OMP_COMMAND")
            or self.config.command
        )
        direct = Path(command).expanduser()
        if direct.exists():
            return str(direct)

        found = shutil.which(command)
        if found:
            return found

        if Path(command).name.lower() not in {"omp", "omp.exe"}:
            return None

        for candidate in _windows_omp_candidates():
            if candidate.exists():
                return str(candidate)
        return None

    def _build_command(
        self,
        context: RunContext,
        prompt_path: Path,
        resolved_command: str,
    ) -> list[str]:
        command = [
            resolved_command,
            "--cwd",
            str(context.workspace),
            "--mode",
            self.config.mode,
            "--session-dir",
            str(_run_dir(context) / "pi-session"),
            "--tools",
            ",".join(self.config.tools),
        ]
        if self.config.no_session:
            command.append("--no-session")
        if self.config.no_lsp:
            command.append("--no-lsp")
        if self.config.no_extensions:
            command.append("--no-extensions")
        if self.config.no_title:
            command.append("--no-title")
        if self.config.auto_approve:
            command.append("--auto-approve")
        if self.config.model:
            command.extend(["--model", self.config.model])
        command.extend(["-p", f"@{prompt_path}"])
        return command

    @staticmethod
    def _build_prompt(spec: TaskSpec, context: RunContext) -> str:
        run_dir = _run_dir(context)
        spec_path = context.spec_path or run_dir / "spec.yaml"
        return (
            "# Yield Report Agent Runtime Task\n\n"
            "You are running as the OMP Agent Runtime for excel-generator-project.\n"
            "OMP 是本次运行的唯一 Agent Runtime。Do not delegate the whole task to "
            "`RuntimeRouter`, `scripts/run_task_spec.py --runtime python`, or the legacy "
            "PythonSkillRuntime. You may call existing project Skills and scripts as tools.\n"
            "Follow AGENTS.md and the Skill contracts. Treat the TaskSpec and user corrections "
            "as the source of truth.\n\n"
            "Safety boundary:\n"
            f"- Read the TaskSpec at `{spec_path}`.\n"
            f"- Write all generated artifacts under `{context.output_dir}`.\n"
            f"- Keep traceable notes under `{run_dir}`.\n"
            "- Prefer existing Python Skills and scripts over ad-hoc broad changes.\n"
            "- Do not print secrets or modify files outside the run directory unless a Skill/script requires it.\n\n"
            "Available project tool commands:\n"
            "- Run a report download Skill by sending JSON to `uv run python scripts/copilotkit_skill_bridge.py` "
            "with `module=report_download`, `action=run`, and `options` such as "
            "`report_type=daily_yield`, `end_date`, `product_models`, and `filters.month_count`.\n"
            "- Run a data analysis Skill through the same bridge with `module=data_analysis` and explicit "
            "`options.file_path`, `options.product_models`, `options.metrics`, `options.time_grain`, and "
            "`options.requested_periods` when available.\n"
            "- Run Table Schema Detect with `uv run python scripts/detect_table_schema.py --file <xlsx> "
            "--output-dir docs/references/table_schema`; pass the generated schema markdown into any LLM "
            "reasoning or final analysis.\n\n"
            "Task16 workflow rules:\n"
            "- For monthly yield analysis, compare the requested report date/current date with any local source "
            "file name containing `结束日期YYYY-MM-DD`. If the local source file end date is older than the "
            "requested date by 超过 1 天, treat it as stale and download a fresh source file.\n"
            "- If the user asks for 3 months but the source only provides 2 monthly periods, download again and "
            "set the FineReport 月数/month_count filter to 3. Do not present a 2-month answer as complete.\n"
            "- When FineReport/RPA cannot locate the month_count control or a download command times out, "
            "不要无限等待. Stop after a small number of attempts, write a `blocked` trace entry and a readable "
            "`analysis_summary.md` that explains the missing control/data, then return the blocker to the UI.\n"
            "- After downloading or selecting the correct source file, call Table Schema Detect and save schema "
            "under `docs/references/table_schema` before analysis. Use that schema in the final reasoning.\n"
            "- 用户修正 is authoritative: if the user explains a correction, incorporate it into the next plan, "
            "record why the previous memory/workflow was wrong, and rerun the task accordingly.\n"
            "- Final answer must state data source, requested vs actual period count, whether a stale file was "
            "redownloaded, and any blocker if FineReport/RPA prevents completion.\n\n"
            "TaskSpec snapshot:\n"
            "```json\n"
            f"{json.dumps(spec.model_dump(mode='json'), ensure_ascii=False, indent=2)}\n"
            "```\n\n"
            "Return a concise Chinese summary of what you did and any blockers.\n"
        )


def _extract_text_from_json_events(raw_events: str) -> str:
    fragments: list[str] = []
    for line in raw_events.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        for key in ("message", "text", "content", "delta"):
            value = event.get(key)
            if isinstance(value, str) and value.strip():
                fragments.append(value.strip())
    return "\n".join(fragments)


def _runtime_failure_result(
    *,
    code: str,
    message: str,
    diagnostics: dict[str, Any],
    context: RunContext,
    run_dir: Path,
    events_path: Path,
    raw_events: str,
) -> SkillResult:
    events_path.write_text(raw_events + ("\n" if raw_events else ""), encoding="utf-8")
    generated_markdowns = _collect_generated_markdowns(context.output_dir)
    text = _read_preferred_markdown(generated_markdowns) or _extract_text_from_json_events(raw_events)
    summary_path = context.output_dir / "pi_summary.md"
    if text:
        summary_path.write_text(text, encoding="utf-8")
    else:
        summary_path.write_text(f"# OMP runtime failed\n\n{message}", encoding="utf-8")
    artifacts = _build_result_artifacts(
        summary_path=summary_path,
        events_path=events_path,
        generated_markdowns=generated_markdowns,
    )
    blocker = _read_blocker_from_trace(run_dir)
    if blocker:
        diagnostics["blocker"] = blocker
        message = f"{message} Blocker: {blocker}"
    return SkillResult(
        skill_name="pi_agent",
        success=False,
        summary=f"Pi/OMP runtime failed: {message}",
        artifacts=artifacts,
        error=SkillError(code=code, message=message, recoverable=True, details=diagnostics),
        data={"result_text": text, "runtime": "omp", "diagnostics": diagnostics},
    )


def _timeout_output(exc: subprocess.TimeoutExpired) -> str:
    output = exc.output
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return str(output)


def _timeout_stderr(exc: subprocess.TimeoutExpired) -> str:
    stderr = exc.stderr
    if stderr is None:
        return ""
    if isinstance(stderr, bytes):
        return stderr.decode("utf-8", errors="replace")
    return str(stderr)


def _collect_generated_markdowns(output_dir: Path) -> list[Path]:
    if not output_dir.exists():
        return []

    def sort_key(path: Path) -> tuple[int, str]:
        if path.name == "analysis_summary.md":
            return (0, path.name.lower())
        if "analysis" in path.stem.lower():
            return (1, path.name.lower())
        return (2, path.name.lower())

    return sorted(
        [
            path
            for path in output_dir.glob("*.md")
            if path.is_file() and path.name != "pi_summary.md"
        ],
        key=sort_key,
    )


def _read_preferred_markdown(markdown_paths: list[Path]) -> str:
    if not markdown_paths:
        return ""
    try:
        text = markdown_paths[0].read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""
    max_chars = 120_000
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n[truncated]"


def _build_result_artifacts(
    *,
    summary_path: Path,
    events_path: Path,
    generated_markdowns: list[Path],
) -> list[ArtifactRef]:
    artifacts = [
        ArtifactRef(kind="markdown", path=summary_path, description="Pi runtime summary"),
    ]
    artifacts.extend(
        ArtifactRef(kind="markdown", path=path, description="OMP generated markdown")
        for path in generated_markdowns
    )
    artifacts.append(ArtifactRef(kind="jsonl", path=events_path, description="Pi runtime event stream"))
    return artifacts


def _read_blocker_from_trace(run_dir: Path) -> str | None:
    trace_path = run_dir / "trace.jsonl"
    if not trace_path.exists():
        return None
    try:
        lines = trace_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        status = str(event.get("status") or "").lower()
        step = str(event.get("step") or event.get("step_id") or "").lower()
        if status != "blocked" and step != "blocker":
            continue
        message = _blocker_message(event)
        return message or "OMP reported a blocked workflow."
    return None


def _blocker_message(event: dict[str, Any]) -> str:
    for key in ("detail", "message", "output_summary", "summary", "reason"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    error = event.get("error")
    if isinstance(error, dict):
        for key in ("message", "detail", "reason"):
            value = error.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return json.dumps(error, ensure_ascii=False)
    if isinstance(error, str) and error.strip():
        return error.strip()
    return ""


def _failed_result(code: str, message: str, details: dict[str, Any]) -> SkillResult:
    return SkillResult(
        skill_name="pi_agent",
        success=False,
        summary=f"Pi/OMP runtime failed: {message}",
        error=SkillError(code=code, message=message, recoverable=True, details=details),
        data={"runtime": "omp", "diagnostics": details},
    )


def _run_dir(context: RunContext) -> Path:
    configured = context.config.get("run_dir")
    if configured:
        return Path(configured)
    if context.spec_path is not None:
        return Path(context.spec_path).resolve().parent
    return context.workspace / "specs" / "runs" / context.run_id


def _windows_omp_candidates() -> list[Path]:
    candidates: list[Path] = []
    for env_name in ("LOCALAPPDATA", "APPDATA"):
        value = os.environ.get(env_name)
        if value:
            candidates.extend(
                [
                    Path(value) / "omp" / "omp.exe",
                    Path(value) / "npm" / "omp.cmd",
                ]
            )
    home = Path.home()
    candidates.extend(
        [
            home / "AppData" / "Local" / "omp" / "omp.exe",
            home / "AppData" / "Roaming" / "npm" / "omp.cmd",
        ]
    )
    return list(dict.fromkeys(candidates))


def _write_trace(
    context: RunContext,
    step_id: str,
    status: str,
    input_summary: str = "",
    output_summary: str = "",
    artifacts: list[str] | None = None,
) -> None:
    if context.trace is None:
        return
    context.trace.write(
        TraceEvent(
            run_id=context.run_id,
            step_id=step_id,
            skill="pi_agent",
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
            artifacts=artifacts or [],
        )
    )
