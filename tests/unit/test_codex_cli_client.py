from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from yield_report.shared_kernel.infrastructure.codex_cli_client import CodexCLIClient, CodexCLIError
from yield_report.shared_kernel.infrastructure.llm_handler import LLMManager, LLMProviderError


def test_codex_cli_client_reads_output_last_message(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["input"] = kwargs["input"]
        output_file = Path(args[args.index("-o") + 1])
        output_file.write_text("codex ok", encoding="utf-8")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "yield_report.shared_kernel.infrastructure.codex_cli_client.subprocess.run",
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
        "yield_report.shared_kernel.infrastructure.codex_cli_client.subprocess.run",
        fake_run,
    )

    client = CodexCLIClient(codex_bin="codex", workspace=tmp_path)

    with pytest.raises(CodexCLIError, match="exited with code 7"):
        client.run("prompt")


def test_llm_manager_routes_legacy_provider_to_deepseek_client() -> None:
    class FakeCompletions:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
            )

    class FakeClient:
        def __init__(self) -> None:
            self.chat = SimpleNamespace(completions=FakeCompletions())

    fake = FakeClient()
    manager = LLMManager(deepseek_client=fake)

    try:
        result = manager.chat(
            provider="deepseek",
            messages=[{"role": "user", "content": "hello"}],
            response_format={"type": "json_object"},
        )
    finally:
        manager.clear_clients()

    assert result == "ok"
    assert fake.chat.completions.calls
    assert fake.chat.completions.calls[0]["messages"][0]["content"] == "hello"
    assert fake.chat.completions.calls[0]["response_format"] == {"type": "json_object"}


def test_llm_manager_wraps_deepseek_errors() -> None:
    class FakeCompletions:
        def create(self, **kwargs):
            raise RuntimeError("missing")

    class FakeClient:
        def __init__(self) -> None:
            self.chat = SimpleNamespace(completions=FakeCompletions())

    manager = LLMManager(deepseek_client=FakeClient())

    try:
        with pytest.raises(LLMProviderError, match="DeepSeek API call failed"):
            manager.chat(messages=[{"role": "user", "content": "hello"}])
    finally:
        manager.clear_clients()
