from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from shared_kernel.infrastructure.codex_cli_client import CodexCLIClient, CodexCLIError
from shared_kernel.infrastructure.llm_handler import LLMManager, LLMProviderError


def test_codex_cli_client_reads_output_last_message(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["input"] = kwargs["input"]
        output_file = Path(args[args.index("-o") + 1])
        output_file.write_text("codex ok", encoding="utf-8")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "shared_kernel.infrastructure.codex_cli_client.subprocess.run",
        fake_run,
    )

    client = CodexCLIClient(codex_bin="codex", workspace=tmp_path)
    result = client.chat(
        messages=[{"role": "user", "content": "hello"}],
        system_prompt="system",
        response_format={"type": "json_object"},
    )

    assert result == "codex ok"
    assert captured["args"][:2] == ["codex", "exec"]
    assert "--ephemeral" in captured["args"]
    assert "--sandbox" in captured["args"]
    assert captured["args"][-1] == "-"
    assert "Output contract: return exactly one valid JSON object" in captured["input"]
    assert "USER message:\nhello" in captured["input"]


def test_codex_cli_client_raises_on_nonzero_exit(tmp_path: Path, monkeypatch) -> None:
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=7, stdout="", stderr="bad")

    monkeypatch.setattr(
        "shared_kernel.infrastructure.codex_cli_client.subprocess.run",
        fake_run,
    )

    client = CodexCLIClient(codex_bin="codex", workspace=tmp_path)

    with pytest.raises(CodexCLIError, match="exited with code 7"):
        client.run("prompt")


def test_llm_manager_routes_legacy_provider_to_codex_client() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def chat(self, **kwargs):
            self.calls.append(kwargs)
            return "ok"

    fake = FakeClient()
    manager = LLMManager(codex_client=fake)

    try:
        result = manager.chat(
            provider="deepseek",
            messages=[{"role": "user", "content": "hello"}],
            response_format={"type": "json_object"},
        )
    finally:
        manager.clear_clients()

    assert result == "ok"
    assert fake.calls
    assert fake.calls[0]["messages"][0]["content"] == "hello"


def test_llm_manager_wraps_codex_errors() -> None:
    class FakeClient:
        def chat(self, **kwargs):
            raise CodexCLIError("missing")

    manager = LLMManager(codex_client=FakeClient())

    try:
        with pytest.raises(LLMProviderError, match="Codex CLI call failed"):
            manager.chat(messages=[{"role": "user", "content": "hello"}])
    finally:
        manager.clear_clients()
