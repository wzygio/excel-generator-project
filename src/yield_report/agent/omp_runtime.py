"""Oh-My-Pi / Pi runtime adapter for TaskSpec runs."""

from __future__ import annotations

import json
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
    model: str | None = None


class OmpRuntimeUnavailableError(Exception):
    """Raised when OMP/Pi cannot be started."""


class OmpJsonRuntime:
    """Run a TaskSpec through OMP one-shot JSON event mode.

    The adapter is intentionally small and conservative. It asks OMP to operate
    inside the run directory and then records OMP's event stream as an artifact.
    Stable Python Skills remain the deterministic fallback for known workflows.
    """

    runtime_name = "omp"

    def __init__(self, config: OmpRuntimeConfig | None = None) -> None:
        self.config = config or OmpRuntimeConfig()

    def is_available(self) -> bool:
        return shutil.which(self.config.command) is not None

    def run_spec(self, spec: TaskSpec, context: RunContext) -> list[SkillResult]:
        if not self.is_available():
            raise OmpRuntimeUnavailableError(f"OMP command not found: {self.config.command}")

        run_dir = _run_dir(context)
        run_dir.mkdir(parents=True, exist_ok=True)
        context.output_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = run_dir / "pi_prompt.md"
        events_path = run_dir / "pi_events.jsonl"
        prompt = self._build_prompt(spec, context)
        prompt_path.write_text(prompt, encoding="utf-8")

        _write_trace(context, "pi_runtime", "started", input_summary=str(prompt_path))
        command = self._build_command(context, prompt_path)
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
        except subprocess.TimeoutExpired:
            result = _failed_result(
                "omp.timeout",
                f"OMP timed out after {self.config.timeout_seconds} seconds.",
                {"timeout_seconds": self.config.timeout_seconds, "command": command},
            )
            _write_trace(context, "pi_runtime", "failed", output_summary=result.summary)
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

        text = _extract_text_from_json_events(raw_events) or "OMP run completed."
        summary_path = context.output_dir / "pi_summary.md"
        summary_path.write_text(text, encoding="utf-8")
        result = SkillResult(
            skill_name="pi_agent",
            success=True,
            summary="Pi/OMP runtime completed.",
            artifacts=[
                ArtifactRef(kind="markdown", path=summary_path, description="Pi runtime summary"),
                ArtifactRef(kind="jsonl", path=events_path, description="Pi runtime event stream"),
            ],
            data={"result_text": text, "runtime": self.runtime_name, "diagnostics": diagnostics},
        )
        _write_trace(
            context,
            "pi_runtime",
            "succeeded",
            output_summary=result.summary,
            artifacts=[str(summary_path), str(events_path)],
        )
        return [result]

    def _build_command(self, context: RunContext, prompt_path: Path) -> list[str]:
        command = [
            self.config.command,
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
            "You are running as the Pi/OMP runtime for excel-generator-project.\n"
            "Follow AGENTS.md and the Skill contracts. Treat the TaskSpec as the source of truth.\n\n"
            "Safety boundary:\n"
            f"- Read the TaskSpec at `{spec_path}`.\n"
            f"- Write all generated artifacts under `{context.output_dir}`.\n"
            f"- Keep traceable notes under `{run_dir}`.\n"
            "- Prefer existing Python Skills and scripts over ad-hoc broad changes.\n"
            "- Do not print secrets or modify files outside the run directory unless a Skill/script requires it.\n\n"
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
