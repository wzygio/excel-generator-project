"""Small adapter around `codex exec` for project runtime LLM tasks."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CodexCLIError(RuntimeError):
    """Raised when Codex CLI cannot produce a usable response."""


def _default_timeout_seconds() -> int:
    raw = os.getenv("CODEX_CLI_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return 240
    try:
        return max(30, int(raw))
    except ValueError:
        logger.warning("Invalid CODEX_CLI_TIMEOUT_SECONDS=%r; using default", raw)
        return 240


@dataclass(slots=True)
class CodexCLIClient:
    """Invoke Codex CLI in non-interactive mode.

    The adapter intentionally keeps Codex in read-only mode by default. Runtime
    model calls should parse, reason, and generate text/code, not mutate the
    repository behind the Agent Workbench.
    """

    codex_bin: str | None = None
    workspace: str | Path | None = None
    sandbox: str = field(default_factory=lambda: os.getenv("CODEX_CLI_SANDBOX", "read-only"))
    timeout_seconds: int = field(default_factory=_default_timeout_seconds)
    model: str | None = field(default_factory=lambda: os.getenv("CODEX_CLI_MODEL") or None)
    profile: str | None = field(default_factory=lambda: os.getenv("CODEX_CLI_PROFILE") or None)
    extra_args: tuple[str, ...] = ()

    def chat(
        self,
        *,
        messages: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        prompt = self._build_prompt(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            extra_options=kwargs,
        )
        return self.run(prompt)

    def run(self, prompt: str) -> str:
        codex_bin = self._resolve_codex_bin()
        workspace = str(Path(self.workspace or Path.cwd()).resolve())

        with tempfile.TemporaryDirectory(prefix="codex-cli-") as tmpdir:
            output_file = Path(tmpdir) / "last_message.txt"
            args = [
                codex_bin,
                "exec",
                "--ephemeral",
                "--sandbox",
                self.sandbox,
                "--color",
                "never",
                "-C",
                workspace,
                "-o",
                str(output_file),
            ]
            if self.model:
                args.extend(["--model", self.model])
            if self.profile:
                args.extend(["--profile", self.profile])
            args.extend(self.extra_args)
            args.append("-")

            try:
                proc = subprocess.run(
                    args,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout_seconds,
                )
            except FileNotFoundError as exc:
                raise CodexCLIError(
                    "Codex CLI was not found. Set CODEX_CLI_BIN or install/login Codex CLI."
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise CodexCLIError(
                    f"Codex CLI timed out after {self.timeout_seconds} seconds"
                ) from exc

            if proc.returncode != 0:
                details = "\n".join(
                    part.strip()
                    for part in (proc.stderr, proc.stdout)
                    if part and part.strip()
                )
                raise CodexCLIError(
                    f"Codex CLI exited with code {proc.returncode}: {details[:2000]}"
                )

            if output_file.exists():
                text = output_file.read_text(encoding="utf-8", errors="replace")
            else:
                text = proc.stdout

        text = text.strip()
        if not text:
            raise CodexCLIError("Codex CLI returned an empty response")
        return text

    def _resolve_codex_bin(self) -> str:
        candidates: list[str | None] = [
            self.codex_bin,
            os.getenv("CODEX_CLI_BIN"),
        ]
        if os.name == "nt":
            candidates.extend(
                [
                    shutil.which("codex.cmd"),
                    str(Path.home() / ".npm-global" / "codex.cmd"),
                ]
            )
        candidates.extend([shutil.which("codex"), "codex"])

        for candidate in candidates:
            if not candidate:
                continue
            if candidate == "codex" or Path(candidate).exists():
                return candidate
        return "codex"

    @staticmethod
    def _build_prompt(
        *,
        messages: list[dict[str, str]] | None,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
        response_format: dict[str, Any] | None,
        extra_options: dict[str, Any],
    ) -> str:
        sections: list[str] = [
            "You are being called by a Python application as a deterministic backend model.",
            "Return only the requested final answer. Do not modify files.",
        ]
        if system_prompt:
            sections.append(f"System instructions:\n{system_prompt}")
        if response_format and response_format.get("type") == "json_object":
            sections.append(
                "Output contract: return exactly one valid JSON object. "
                "Do not wrap it in markdown and do not add explanatory text."
            )
        if extra_options.get("output_contract"):
            sections.append(f"Output contract:\n{extra_options['output_contract']}")
        sections.append(
            f"Generation hints: temperature={temperature}; max_tokens={max_tokens}."
        )

        for message in messages or [{"role": "user", "content": ""}]:
            role = message.get("role", "user").upper()
            content = message.get("content", "")
            sections.append(f"{role} message:\n{content}")

        return "\n\n".join(sections).strip()
