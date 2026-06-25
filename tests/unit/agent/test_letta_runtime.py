from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import yield_report.agent.runtime_adapter as runtime_adapter_module
from scripts import run_task_spec as run_task_spec_module
from yield_report.agent.letta_runtime import LettaRuntime, LettaRuntimeConfig
from yield_report.agent.runtime_adapter import RuntimeRouter
from yield_report.agent.spec_model import (
    ArtifactRef,
    MemoryCandidate,
    RunContext,
    SkillCall,
    SkillResult,
    TaskSpec,
)


def test_runtime_router_explicit_letta_uses_letta_runtime(tmp_path: Path) -> None:
    class FakePython:
        def run_spec(self, spec: TaskSpec, context: RunContext):
            raise AssertionError("explicit letta runtime must not call PythonSkillRuntime")

    class FakeOmp:
        def run_spec(self, spec: TaskSpec, context: RunContext):
            raise AssertionError("explicit letta runtime must not call OMP")

    class FakeLetta:
        def run_spec(self, spec: TaskSpec, context: RunContext):
            return [SkillResult(skill_name="letta_agent", success=True, summary="letta ok")]

    result = RuntimeRouter(
        python_runtime=FakePython(),
        omp_runtime=FakeOmp(),
        letta_runtime=FakeLetta(),
    ).run_spec(
        TaskSpec(run_id="run-letta-router"),
        RunContext(run_id="run-letta-router", workspace=tmp_path),
        requested_runtime="letta",
    )

    assert result.runtime == "letta"
    assert result.fallback_attempted is False
    assert result.success is True


def test_runtime_router_auto_can_use_configured_letta_default(tmp_path: Path) -> None:
    class FakePython:
        def run_spec(self, spec: TaskSpec, context: RunContext):
            raise AssertionError("auto runtime must not call PythonSkillRuntime")

    class FakeOmp:
        def run_spec(self, spec: TaskSpec, context: RunContext):
            raise AssertionError("auto runtime must not call OMP")

    class FakeLetta:
        def run_spec(self, spec: TaskSpec, context: RunContext):
            return [SkillResult(skill_name="letta_agent", success=True, summary="letta ok")]

    result = RuntimeRouter(
        python_runtime=FakePython(),
        omp_runtime=FakeOmp(),
        letta_runtime=FakeLetta(),
        default_runtime="letta",
    ).run_spec(
        TaskSpec(run_id="run-letta-default"),
        RunContext(run_id="run-letta-default", workspace=tmp_path),
        requested_runtime="auto",
    )

    assert result.runtime == "letta"
    assert result.success is True


def test_runtime_router_builds_letta_runtime_from_app_config(monkeypatch) -> None:
    letta_settings = SimpleNamespace(
        base_url="http://localhost:8283",
        api_key_env="LETTA_SERVER_PASSWORD",
        server_password_env="LETTA_SERVER_PASSWORD",
        agent_id="agent-from-config",
        agent_name="visionox-yield-monitoring-agent",
        agent_id_cache_path=".agent_workbench/letta_agent_id",
        model="openai/gpt-4.1",
        embedding="openai/text-embedding-3-small",
        sync_memory_blocks=True,
        archive_memory_candidates=True,
        use_conversations=True,
        compaction_mode="sliding_window",
        compaction_clip_chars=12345,
        streaming=True,
        stream_tokens=False,
        background_runs=False,
        timeout_seconds=321,
        max_tool_rounds=7,
    )
    fake_config = SimpleNamespace(
        get=lambda: SimpleNamespace(
            agent=SimpleNamespace(default_runtime="python", letta=letta_settings)
        )
    )
    monkeypatch.setattr(runtime_adapter_module, "app_config", fake_config)

    class FakePython:
        def run_spec(self, spec: TaskSpec, context: RunContext):
            raise AssertionError("not used")

    class FakeOmp:
        def run_spec(self, spec: TaskSpec, context: RunContext):
            raise AssertionError("not used")

    router = RuntimeRouter(python_runtime=FakePython(), omp_runtime=FakeOmp())

    assert isinstance(router.letta_runtime, LettaRuntime)
    assert router.letta_runtime.config.base_url == "http://localhost:8283"
    assert router.letta_runtime.config.api_key_env == "LETTA_SERVER_PASSWORD"
    assert router.letta_runtime.config.server_password_env == "LETTA_SERVER_PASSWORD"
    assert router.letta_runtime.config.agent_id == "agent-from-config"
    assert router.letta_runtime.config.agent_name == "visionox-yield-monitoring-agent"
    assert router.letta_runtime.config.agent_id_cache_path == ".agent_workbench/letta_agent_id"
    assert router.letta_runtime.config.embedding == "openai/text-embedding-3-small"
    assert router.letta_runtime.config.sync_memory_blocks is True
    assert router.letta_runtime.config.archive_memory_candidates is True
    assert router.letta_runtime.config.use_conversations is True
    assert router.letta_runtime.config.compaction_clip_chars == 12345
    assert router.letta_runtime.config.streaming is True
    assert router.letta_runtime.config.stream_tokens is False
    assert router.letta_runtime.config.background_runs is False
    assert router.letta_runtime.config.timeout_seconds == 321
    assert router.letta_runtime.config.max_tool_rounds == 7


def test_letta_runtime_sends_task_spec_with_client_tools_and_writes_summary(
    tmp_path: Path,
) -> None:
    calls: list[dict] = []

    class FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                messages=[
                    SimpleNamespace(
                        message_type="assistant_message",
                        content="M678 最近三个月月度良率趋势分析完成。",
                    )
                ]
            )

    fake_client = SimpleNamespace(agents=SimpleNamespace(messages=FakeMessages()))
    run_dir = tmp_path / "specs" / "runs" / "run-letta"
    context = RunContext(
        run_id="run-letta",
        workspace=tmp_path,
        spec_path=run_dir / "spec.yaml",
        output_dir=run_dir / "outputs",
        config={"run_dir": str(run_dir)},
    )
    spec = TaskSpec(
        run_id="run-letta",
        user_goal="请分析M678最近三个月的月度良率变化趋势；如果有恶化，请给出恶化原因",
    )

    results = LettaRuntime(client=fake_client, agent_id="agent-test").run_spec(spec, context)

    assert results[0].success is True
    assert "M678" in results[0].summary
    assert results[0].data["letta_agent_id"] == "agent-test"
    assert (run_dir / "outputs" / "letta_summary.md").read_text(encoding="utf-8")
    assert calls[0]["agent_id"] == "agent-test"
    assert "M678" in calls[0]["messages"][0]["content"]
    assert calls[0]["streaming"] is True
    assert calls[0]["max_steps"] == 20
    assert {tool["name"] for tool in calls[0]["client_tools"]} >= {
        "yield_report_download",
        "yield_data_analysis",
        "yield_daily_report",
    }


def test_letta_runtime_uses_local_server_env_when_cloud_api_key_is_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    init_kwargs: dict[str, object] = {}

    class FakeMessages:
        def create(self, **kwargs):
            return SimpleNamespace(
                messages=[
                    SimpleNamespace(
                        message_type="assistant_message",
                        content="M678 本地 Letta server 分析完成。",
                    )
                ]
            )

    class FakeLetta:
        def __init__(self, **kwargs) -> None:
            init_kwargs.update(kwargs)
            self.agents = SimpleNamespace(messages=FakeMessages())

    monkeypatch.delenv("LETTA_API_KEY", raising=False)
    monkeypatch.setenv("LETTA_BASE_URL", "http://localhost:8283")
    monkeypatch.setenv("LETTA_SERVER_PASSWORD", "local-password")
    monkeypatch.setitem(sys.modules, "letta_client", SimpleNamespace(Letta=FakeLetta))

    context = RunContext(run_id="run-local-letta", workspace=tmp_path)
    spec = TaskSpec(run_id="run-local-letta", user_goal="分析M678良率趋势")

    results = LettaRuntime(agent_id="agent-test").run_spec(spec, context)

    assert results[0].success is True
    assert init_kwargs["base_url"] == "http://localhost:8283"
    assert init_kwargs["api_key"] == "local-password"


def test_letta_runtime_allows_unsecured_local_server_env(
    monkeypatch,
    tmp_path: Path,
) -> None:
    init_kwargs: dict[str, object] = {}

    class FakeMessages:
        def create(self, **kwargs):
            return SimpleNamespace(
                messages=[
                    SimpleNamespace(
                        message_type="assistant_message",
                        content="local unsecured letta ok",
                    )
                ]
            )

    class FakeLetta:
        def __init__(self, **kwargs) -> None:
            init_kwargs.update(kwargs)
            self.agents = SimpleNamespace(messages=FakeMessages())

    monkeypatch.delenv("LETTA_API_KEY", raising=False)
    monkeypatch.delenv("LETTA_SERVER_PASSWORD", raising=False)
    monkeypatch.setenv("LETTA_BASE_URL", "http://localhost:8283")
    monkeypatch.setitem(sys.modules, "letta_client", SimpleNamespace(Letta=FakeLetta))

    context = RunContext(run_id="run-local-letta-no-password", workspace=tmp_path)
    spec = TaskSpec(run_id="run-local-letta-no-password", user_goal="analyze M678 yield")

    results = LettaRuntime(agent_id="agent-test").run_spec(spec, context)

    assert results[0].success is True
    assert init_kwargs["base_url"] == "http://localhost:8283"
    assert "api_key" not in init_kwargs


def test_letta_runtime_extracts_assistant_text_from_content_blocks(tmp_path: Path) -> None:
    class FakeMessages:
        def create(self, **kwargs):
            return SimpleNamespace(
                messages=[
                    SimpleNamespace(
                        message_type="assistant_message",
                        content=[
                            SimpleNamespace(type="text", text="M678 月度良率趋势分析完成。"),
                            {"type": "text", "text": "未发现明显恶化。"},
                        ],
                    )
                ]
            )

    fake_client = SimpleNamespace(agents=SimpleNamespace(messages=FakeMessages()))
    context = RunContext(run_id="run-letta-content-blocks", workspace=tmp_path)
    spec = TaskSpec(
        run_id="run-letta-content-blocks",
        user_goal="请分析M678最近三个月的月度良率变化趋势",
    )

    results = LettaRuntime(client=fake_client, agent_id="agent-test").run_spec(spec, context)

    assert results[0].success is True
    assert "M678 月度良率趋势分析完成" in results[0].summary
    assert "未发现明显恶化" in results[0].summary


def test_letta_runtime_creates_and_caches_agent_id_when_missing(tmp_path: Path) -> None:
    class FakeMessages:
        def create(self, **kwargs):
            return SimpleNamespace(
                messages=[
                    SimpleNamespace(
                        message_type="assistant_message",
                        content="M678 趋势分析完成。",
                    )
                ]
            )

    class FakeAgents:
        def __init__(self) -> None:
            self.messages = FakeMessages()
            self.create_calls = []

        def create(self, **kwargs):
            self.create_calls.append(kwargs)
            return SimpleNamespace(id="agent-created")

    fake_agents = FakeAgents()
    fake_client = SimpleNamespace(agents=fake_agents)
    context = RunContext(run_id="run-letta-create-agent", workspace=tmp_path)
    spec = TaskSpec(run_id="run-letta-create-agent", user_goal="分析M678良率趋势")

    results = LettaRuntime(client=fake_client).run_spec(spec, context)

    cache_path = tmp_path / ".agent_workbench" / "letta_agent_id"
    assert results[0].success is True
    assert results[0].data["letta_agent_id"] == "agent-created"
    assert cache_path.read_text(encoding="utf-8") == "agent-created"
    assert fake_agents.create_calls[0]["name"] == "visionox-yield-monitoring-agent"
    assert {block["label"] for block in fake_agents.create_calls[0]["memory_blocks"]} >= {
        "persona",
        "runtime_policy",
        "domain_contract",
        "current_task",
        "memory_digest",
    }
    assert fake_agents.create_calls[0]["compaction_settings"]["mode"] == "sliding_window"


def test_letta_runtime_syncs_memory_blocks_for_cached_agent(tmp_path: Path) -> None:
    cache_path = tmp_path / ".agent_workbench" / "letta_agent_id"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text("agent-cached", encoding="utf-8")
    updates: list[dict] = []
    creates: list[dict] = []
    attaches: list[tuple[str, str]] = []

    class FakeMessages:
        def create(self, **kwargs):
            return SimpleNamespace(
                messages=[
                    SimpleNamespace(
                        message_type="assistant_message",
                        content="memory blocks synced",
                    )
                ]
            )

    class FakeAgentBlocks:
        def retrieve(self, block_label: str, *, agent_id: str):
            if block_label == "current_task":
                return SimpleNamespace(id="block-current-task", value="old task")
            raise RuntimeError("missing block")

        def update(self, block_label: str, **kwargs):
            updates.append({"block_label": block_label, **kwargs})
            return SimpleNamespace(id=f"block-{block_label}")

        def attach(self, block_id: str, *, agent_id: str):
            attaches.append((agent_id, block_id))
            return SimpleNamespace(id=agent_id)

    class FakeBlocks:
        def create(self, **kwargs):
            creates.append(kwargs)
            return SimpleNamespace(id=f"block-{kwargs['label']}")

    fake_client = SimpleNamespace(
        agents=SimpleNamespace(messages=FakeMessages(), blocks=FakeAgentBlocks()),
        blocks=FakeBlocks(),
    )
    context = RunContext(run_id="run-letta-memory-blocks", workspace=tmp_path)
    spec = TaskSpec(run_id="run-letta-memory-blocks", user_goal="分析M678良率趋势")

    results = LettaRuntime(client=fake_client).run_spec(spec, context)

    assert results[0].success is True
    assert {create["label"] for create in creates} >= {
        "persona",
        "runtime_policy",
        "domain_contract",
        "memory_digest",
    }
    assert attaches
    assert any(update["block_label"] == "current_task" for update in updates)
    current_task_update = next(update for update in updates if update["block_label"] == "current_task")
    assert "run-letta-memory-blocks" in current_task_update["value"]


def test_letta_runtime_creates_agent_with_explicit_model_and_embedding(tmp_path: Path) -> None:
    class FakeMessages:
        def create(self, **kwargs):
            return SimpleNamespace(
                messages=[
                    SimpleNamespace(
                        message_type="assistant_message",
                        content="agent created with embedding",
                    )
                ]
            )

    class FakeAgents:
        def __init__(self) -> None:
            self.messages = FakeMessages()
            self.create_calls = []

        def create(self, **kwargs):
            self.create_calls.append(kwargs)
            return SimpleNamespace(id="agent-created")

    fake_agents = FakeAgents()
    fake_client = SimpleNamespace(agents=fake_agents)
    context = RunContext(run_id="run-letta-create-agent-embedding", workspace=tmp_path)
    spec = TaskSpec(run_id="run-letta-create-agent-embedding", user_goal="analyze M678 yield")

    results = LettaRuntime(
        config=LettaRuntimeConfig(
            model="deepseek/deepseek-chat",
            embedding="openai/text-embedding-3-small",
        ),
        client=fake_client,
    ).run_spec(spec, context)

    assert results[0].success is True
    assert fake_agents.create_calls[0]["model"] == "deepseek/deepseek-chat"
    assert fake_agents.create_calls[0]["embedding"] == "openai/text-embedding-3-small"


def test_letta_runtime_cloud_base_url_does_not_require_embedding(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class FakeMessages:
        def create(self, **kwargs):
            return SimpleNamespace(
                messages=[
                    SimpleNamespace(
                        message_type="assistant_message",
                        content="cloud base url agent created",
                    )
                ]
            )

    class FakeAgents:
        def __init__(self) -> None:
            self.messages = FakeMessages()
            self.create_calls = []

        def create(self, **kwargs):
            self.create_calls.append(kwargs)
            return SimpleNamespace(id="agent-created")

    monkeypatch.setenv("LETTA_BASE_URL", "https://api.letta.com")
    fake_agents = FakeAgents()
    fake_client = SimpleNamespace(agents=fake_agents)
    context = RunContext(run_id="run-letta-cloud-create-agent", workspace=tmp_path)
    spec = TaskSpec(run_id="run-letta-cloud-create-agent", user_goal="analyze M678 yield")

    results = LettaRuntime(
        config=LettaRuntimeConfig(embedding=""),
        client=fake_client,
    ).run_spec(spec, context)

    assert results[0].success is True
    assert fake_agents.create_calls[0]["model"] == "my-glm-key/glm-5.1"
    assert "embedding" not in fake_agents.create_calls[0]


def test_letta_runtime_uses_conversation_mapping_when_available(tmp_path: Path) -> None:
    conversation_calls: list[dict] = []

    class FakeConversationMessages:
        def create(self, conversation_id: str, **kwargs):
            conversation_calls.append({"conversation_id": conversation_id, **kwargs})
            return iter(
                [
                    SimpleNamespace(
                        message_type="assistant_message",
                        content="conversation-backed run completed",
                        run_id="letta-run-123",
                    )
                ]
            )

    class FakeConversations:
        def __init__(self) -> None:
            self.messages = FakeConversationMessages()
            self.create_calls = []

        def create(self, **kwargs):
            self.create_calls.append(kwargs)
            return SimpleNamespace(id="conversation-created")

    fake_conversations = FakeConversations()
    fake_client = SimpleNamespace(
        agents=SimpleNamespace(),
        conversations=fake_conversations,
    )
    run_dir = tmp_path / "specs" / "runs" / "run-letta-conversation"
    context = RunContext(
        run_id="run-letta-conversation",
        workspace=tmp_path,
        spec_path=run_dir / "spec.yaml",
        output_dir=run_dir / "outputs",
        config={"run_dir": str(run_dir)},
    )
    spec = TaskSpec(run_id="run-letta-conversation", user_goal="analyze M678 yield")

    results = LettaRuntime(client=fake_client, agent_id="agent-test").run_spec(spec, context)

    cache_path = tmp_path / ".agent_workbench" / "letta_conversations" / "run-letta-conversation"
    run_summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert results[0].success is True
    assert cache_path.read_text(encoding="utf-8") == "conversation-created"
    assert fake_conversations.create_calls[0]["agent_id"] == "agent-test"
    assert conversation_calls[0]["conversation_id"] == "conversation-created"
    assert conversation_calls[0]["streaming"] is True
    assert conversation_calls[0]["max_steps"] == 20
    assert results[0].data["letta_conversation_id"] == "conversation-created"
    assert results[0].data["letta_run_id"] == "letta-run-123"
    assert run_summary["letta_conversation_id"] == "conversation-created"
    assert run_summary["letta_run_id"] == "letta-run-123"


def test_letta_runtime_requires_embedding_when_auto_creating_local_agent(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class FakeAgents:
        def __init__(self) -> None:
            self.messages = SimpleNamespace()

        def create(self, **kwargs):
            raise AssertionError("local auto-create should fail before calling Letta")

    monkeypatch.setenv("LETTA_BASE_URL", "http://localhost:8283")
    fake_client = SimpleNamespace(agents=FakeAgents())
    context = RunContext(run_id="run-letta-local-missing-embedding", workspace=tmp_path)
    spec = TaskSpec(run_id="run-letta-local-missing-embedding", user_goal="analyze M678 yield")

    results = LettaRuntime(
        config=LettaRuntimeConfig(embedding=""),
        client=fake_client,
    ).run_spec(spec, context)

    assert results[0].success is False
    assert results[0].error is not None
    assert results[0].error.code == "letta.unavailable"
    assert "embedding" in results[0].summary


def test_letta_runtime_reuses_cached_agent_id(tmp_path: Path) -> None:
    cache_path = tmp_path / ".agent_workbench" / "letta_agent_id"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text("agent-cached", encoding="utf-8")

    class FakeMessages:
        def __init__(self) -> None:
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                messages=[
                    SimpleNamespace(
                        message_type="assistant_message",
                        content="M678 趋势分析完成。",
                    )
                ]
            )

    class FakeAgents:
        def __init__(self) -> None:
            self.messages = FakeMessages()

        def create(self, **kwargs):
            raise AssertionError("cached Letta agent id should avoid creating a new agent")

    fake_agents = FakeAgents()
    fake_client = SimpleNamespace(agents=fake_agents)
    context = RunContext(run_id="run-letta-cached-agent", workspace=tmp_path)
    spec = TaskSpec(run_id="run-letta-cached-agent", user_goal="分析M678良率趋势")

    results = LettaRuntime(client=fake_client).run_spec(spec, context)

    assert results[0].success is True
    assert results[0].data["letta_agent_id"] == "agent-cached"
    assert fake_agents.messages.calls[0]["agent_id"] == "agent-cached"


def test_letta_runtime_dispatches_client_tool_to_project_skill(tmp_path: Path) -> None:
    calls: list[dict] = []

    class FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return SimpleNamespace(
                    messages=[
                        SimpleNamespace(
                            message_type="approval_request_message",
                            tool_call=SimpleNamespace(
                                name="yield_data_analysis",
                                arguments=json.dumps(
                                    {
                                        "analysis_goal": "分析M678最近三个月月度良率趋势",
                                        "product_models": ["M678"],
                                        "time_grain": "month",
                                        "requested_periods": 3,
                                    },
                                    ensure_ascii=False,
                                ),
                                tool_call_id="call-analysis",
                            ),
                        )
                    ]
                )
            return SimpleNamespace(
                messages=[
                    SimpleNamespace(
                        message_type="assistant_message",
                        content="已根据 data_analysis 工具结果完成 M678 趋势分析。",
                    )
                ]
            )

    class FakeProjectRuntime:
        def __init__(self) -> None:
            self.calls = []

        def run_call(self, call, context):
            self.calls.append(call)
            assert call.skill == "data_analysis"
            assert call.input["product_models"] == ["M678"]
            assert call.input["question"] == "分析M678最近三个月月度良率趋势"
            assert call.input["analysis_intent"] == "trend"
            return SkillResult(
                skill_name="data_analysis",
                success=True,
                summary="M678 月度良率无明显恶化",
                data={"trend": "stable"},
                memory_updates=[
                    MemoryCandidate(
                        record_id="mem-m678-monthly-trend",
                        summary="M678 月度良率趋势分析可复用 data_analysis Skill",
                    )
                ],
            )

    class FakePassages:
        def __init__(self) -> None:
            self.create_calls = []

        def create(self, agent_id: str, **kwargs):
            self.create_calls.append({"agent_id": agent_id, **kwargs})
            return SimpleNamespace(id="passage-created")

    fake_passages = FakePassages()
    fake_client = SimpleNamespace(
        agents=SimpleNamespace(messages=FakeMessages(), passages=fake_passages)
    )
    fake_project_runtime = FakeProjectRuntime()
    run_dir = tmp_path / "specs" / "runs" / "run-letta-tools"
    context = RunContext(
        run_id="run-letta-tools",
        workspace=tmp_path,
        spec_path=run_dir / "spec.yaml",
        output_dir=run_dir / "outputs",
        config={
            "run_dir": str(run_dir),
            "summary_path": str(run_dir / "run_summary.json"),
            "memory_candidates_path": str(run_dir / "memory_candidates.json"),
        },
    )
    spec = TaskSpec(
        run_id="run-letta-tools",
        user_goal="请分析M678最近三个月的月度良率变化趋势；如果有恶化，请给出恶化原因",
    )

    results = LettaRuntime(
        client=fake_client,
        agent_id="agent-test",
        project_runtime=fake_project_runtime,
    ).run_spec(spec, context)

    assert results[0].success is True
    assert fake_project_runtime.calls[0].id == "letta_yield_data_analysis"
    approval = calls[1]["messages"][0]["approvals"][0]
    assert approval["tool_call_id"] == "call-analysis"
    assert approval["status"] == "success"
    assert "M678 月度良率无明显恶化" in approval["tool_return"]
    run_summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    memory_candidates = json.loads(
        (run_dir / "memory_candidates.json").read_text(encoding="utf-8")
    )
    assert run_summary["runtime"] == "letta"
    assert run_summary["letta_archival_memory_count"] == 1
    assert [step["step_id"] for step in run_summary["steps"]] == [
        "letta_yield_data_analysis",
        "letta_runtime",
    ]
    assert memory_candidates[0]["record_id"] == "mem-m678-monthly-trend"
    assert fake_passages.create_calls[0]["agent_id"] == "agent-test"
    assert fake_passages.create_calls[0]["tags"] == [
        "runtime",
        "memory_candidate",
        "pending",
    ]
    assert "mem-m678-monthly-trend" in fake_passages.create_calls[0]["text"]


def test_letta_runtime_returns_all_pending_approval_tool_calls(tmp_path: Path) -> None:
    calls: list[dict] = []
    tool_call_analysis = SimpleNamespace(
        name="yield_data_analysis",
        arguments=json.dumps(
            {
                "analysis_goal": "生成日报前分析M678良率",
                "product_models": ["M678"],
            },
            ensure_ascii=False,
        ),
        tool_call_id="call-analysis",
    )
    tool_call_report = SimpleNamespace(
        name="yield_daily_report",
        arguments=json.dumps(
            {
                "report_date": "2026-06-22",
                "product_models": ["M678"],
                "output_name": "daily_report_output.xlsx",
            },
            ensure_ascii=False,
        ),
        tool_call_id="call-report",
    )

    class FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return SimpleNamespace(
                    messages=[
                        SimpleNamespace(
                            message_type="approval_request_message",
                            tool_call=tool_call_analysis,
                            tool_calls=[tool_call_analysis, tool_call_report],
                        )
                    ]
                )
            return SimpleNamespace(
                messages=[
                    SimpleNamespace(
                        message_type="assistant_message",
                        content="日报生成完成，已列出 Excel 和 Markdown 产物路径。",
                    )
                ]
            )

    class FakeProjectRuntime:
        def __init__(self) -> None:
            self.skill_names = []

        def run_call(self, call, context):
            self.skill_names.append(call.skill)
            return SkillResult(
                skill_name=call.skill,
                success=True,
                summary=f"{call.skill} completed",
            )

    fake_project_runtime = FakeProjectRuntime()
    fake_client = SimpleNamespace(agents=SimpleNamespace(messages=FakeMessages()))
    context = RunContext(run_id="run-letta-parallel-tools", workspace=tmp_path)
    spec = TaskSpec(run_id=context.run_id, user_goal="请生成今天的良率日报")

    results = LettaRuntime(
        client=fake_client,
        agent_id="agent-test",
        project_runtime=fake_project_runtime,
    ).run_spec(spec, context)

    assert results[0].success is True
    assert fake_project_runtime.skill_names == ["data_analysis", "daily_report"]
    approvals = calls[1]["messages"][0]["approvals"]
    assert [approval["tool_call_id"] for approval in approvals] == [
        "call-analysis",
        "call-report",
    ]
    assert all(approval["status"] == "success" for approval in approvals)


def test_letta_runtime_fails_closed_for_unknown_workflow_tools(tmp_path: Path) -> None:
    spec = TaskSpec(
        run_id="run-unknown-workflow",
        workflow=[
            SkillCall(id="custom_step", skill="custom_unknown_skill", input={})
        ],
    )

    tools = LettaRuntime(agent_id="agent-test")._client_tools_for_spec(spec)

    assert tools == []


def test_letta_runtime_scopes_daily_report_workflow_to_native_tool() -> None:
    spec = TaskSpec(
        run_id="run-daily-tools",
        workflow=[
            SkillCall(
                id="generate_daily_report",
                skill="daily_report",
                input={"report_date": "2026-06-23"},
            )
        ],
    )

    tools = LettaRuntime(agent_id="agent-test")._client_tools_for_spec(spec)

    assert {tool["name"] for tool in tools} == {"yield_daily_report"}


def test_letta_runtime_scopes_report_download_workflow_to_finereport_wrapper() -> None:
    spec = TaskSpec(
        run_id="run-report-download-tools",
        workflow=[
            SkillCall(
                id="download_daily_yield",
                skill="report_download",
                input={"report_type": "daily_yield", "end_date": "2026-06-23"},
            )
        ],
    )

    tools = LettaRuntime(agent_id="agent-test")._client_tools_for_spec(spec)

    assert {tool["name"] for tool in tools} == {"yield_report_download"}
    assert "FineReport RPA" in tools[0]["description"]
    assert tools[0]["parameters"]["properties"]["report_type"]


def test_letta_report_download_tool_dispatches_to_report_download_skill(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "batch_yield.xlsx"

    class FakeProjectRuntime:
        def __init__(self) -> None:
            self.calls = []

        def run_call(self, call, context):
            self.calls.append(call)
            assert call.skill == "report_download"
            assert call.input["report_type"] == "batch_yield"
            assert call.input["product_models"] == ["M626"]
            return SkillResult(
                skill_name="report_download",
                success=True,
                summary="FineReport RPA downloaded batch yield report.",
                artifacts=[
                    ArtifactRef(
                        kind="excel",
                        path=output_path,
                        description="批次良率源表",
                    )
                ],
                data={"files": [{"file_path": str(output_path)}]},
            )

    fake_runtime = FakeProjectRuntime()
    context = RunContext(run_id="run-letta-report-download", workspace=tmp_path)
    tool_results = []
    tool_return, status = LettaRuntime(
        agent_id="agent-test",
        project_runtime=fake_runtime,
    )._execute_client_tool(
        SimpleNamespace(
            name="yield_report_download",
            arguments=json.dumps(
                {
                    "report_type": "batch_yield",
                    "end_date": "2026-06-23",
                    "product_models": ["M626"],
                },
                ensure_ascii=False,
            ),
            tool_call_id="call-download",
        ),
        TaskSpec(run_id="run-letta-report-download"),
        context,
        tool_results,
    )

    payload = json.loads(tool_return)
    assert status == "success"
    assert payload["summary"] == "FineReport RPA downloaded batch yield report."
    assert payload["artifacts"][0]["path"] == str(output_path)
    assert fake_runtime.calls[0].id == "letta_yield_report_download"
    assert tool_results[0][0].skill == "report_download"


def test_letta_runtime_returns_compact_client_tool_payload(tmp_path: Path) -> None:
    output_path = tmp_path / "daily.xlsx"

    class FakeProjectRuntime:
        def run_call(self, call, context):
            return SkillResult(
                skill_name="daily_report",
                success=True,
                summary="日报生成完成。",
                artifacts=[
                    ArtifactRef(kind="excel", path=output_path, description="日报文件")
                ],
                data={"row_count": 12, "large_internal_payload": ["ignored"]},
                warnings=["source reused"],
            )

    context = RunContext(run_id="run-compact-tool", workspace=tmp_path)
    tool_results = []
    tool_return, status = LettaRuntime(
        agent_id="agent-test",
        project_runtime=FakeProjectRuntime(),
    )._execute_client_tool(
        SimpleNamespace(
            name="yield_daily_report",
            arguments=json.dumps({"report_date": "2026-06-23"}, ensure_ascii=False),
            tool_call_id="call-daily",
        ),
        TaskSpec(run_id="run-compact-tool"),
        context,
        tool_results,
    )

    payload = json.loads(tool_return)
    assert status == "success"
    assert payload == {
        "status": "success",
        "summary": "日报生成完成。",
        "artifacts": [
            {
                "kind": "excel",
                "path": str(output_path),
                "description": "日报文件",
            }
        ],
        "metrics": {"row_count": 12},
        "warnings": ["source reused"],
        "error": None,
    }
    assert tool_results[0][0].skill == "daily_report"


def test_letta_runtime_keeps_run_successful_when_archival_memory_write_fails(
    tmp_path: Path,
) -> None:
    calls: list[dict] = []

    class FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return SimpleNamespace(
                    messages=[
                        SimpleNamespace(
                            message_type="approval_request_message",
                            tool_call=SimpleNamespace(
                                name="yield_data_analysis",
                                arguments=json.dumps(
                                    {
                                        "analysis_goal": "分析M678最近三个月月度良率趋势",
                                        "product_models": ["M678"],
                                        "time_grain": "monthly",
                                        "requested_periods": 3,
                                    },
                                    ensure_ascii=False,
                                ),
                                tool_call_id="call-analysis",
                            ),
                        )
                    ]
                )
            return SimpleNamespace(
                messages=[
                    SimpleNamespace(
                        message_type="assistant_message",
                        content="M678 趋势分析完成。",
                    )
                ]
            )

    class FailingPassages:
        def create(self, agent_id: str, **kwargs):
            raise RuntimeError("archival unavailable")

    class FakeProjectRuntime:
        def run_call(self, call, context):
            return SkillResult(
                skill_name="data_analysis",
                success=True,
                summary="M678 月度良率存在恶化",
                memory_updates=[
                    MemoryCandidate(
                        record_id="mem-m678-monthly-trend",
                        summary="M678 月度良率趋势分析记录",
                    )
                ],
            )

    fake_client = SimpleNamespace(
        agents=SimpleNamespace(messages=FakeMessages(), passages=FailingPassages())
    )
    run_dir = tmp_path / "specs" / "runs" / "run-letta-archive-failure"
    context = RunContext(
        run_id="run-letta-archive-failure",
        workspace=tmp_path,
        spec_path=run_dir / "spec.yaml",
        output_dir=run_dir / "outputs",
        config={"run_dir": str(run_dir)},
    )
    spec = TaskSpec(run_id=context.run_id, user_goal="分析M678月度良率趋势")

    results = LettaRuntime(
        client=fake_client,
        agent_id="agent-test",
        project_runtime=FakeProjectRuntime(),
    ).run_spec(spec, context)

    run_summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert results[0].success is True
    assert results[0].data["letta_archival_memory_count"] == 0
    assert run_summary["letta_archival_memory_count"] == 0
    assert run_summary["steps"][0]["success"] is True


def test_letta_runtime_returns_structured_failure_when_api_key_is_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("LETTA_API_KEY", raising=False)
    run_dir = tmp_path / "specs" / "runs" / "run-letta-missing-key"
    context = RunContext(
        run_id="run-letta-missing-key",
        workspace=tmp_path,
        spec_path=run_dir / "spec.yaml",
        output_dir=run_dir / "outputs",
        config={"run_dir": str(run_dir)},
    )
    spec = TaskSpec(run_id="run-letta-missing-key", user_goal="分析M678良率趋势")

    results = LettaRuntime(
        config=LettaRuntimeConfig(api_key_env="MISSING_LETTA_API_KEY"),
        agent_id="agent-test",
    ).run_spec(spec, context)

    assert results[0].success is False
    assert results[0].error is not None
    assert results[0].error.code == "letta.unavailable"
    assert "Missing Letta API key" in results[0].summary
    run_summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert run_summary["runtime"] == "letta"
    assert run_summary["status"] == "failed"


def test_letta_runtime_returns_failure_when_tool_rounds_are_exceeded(tmp_path: Path) -> None:
    class FakeMessages:
        def create(self, **kwargs):
            return SimpleNamespace(
                messages=[
                    SimpleNamespace(
                        message_type="approval_request_message",
                        tool_call=SimpleNamespace(
                            name="yield_data_analysis",
                            arguments=json.dumps(
                                {"analysis_goal": "持续请求工具"},
                                ensure_ascii=False,
                            ),
                            tool_call_id="call-loop",
                        ),
                    )
                ]
            )

    class FakeProjectRuntime:
        def run_call(self, call, context):
            return SkillResult(
                skill_name="data_analysis",
                success=True,
                summary="工具调用成功但 Letta 仍继续请求工具",
            )

    fake_client = SimpleNamespace(agents=SimpleNamespace(messages=FakeMessages()))
    context = RunContext(run_id="run-letta-max-rounds", workspace=tmp_path)
    spec = TaskSpec(run_id="run-letta-max-rounds", user_goal="分析M678良率趋势")

    results = LettaRuntime(
        config=LettaRuntimeConfig(max_tool_rounds=1),
        client=fake_client,
        agent_id="agent-test",
        project_runtime=FakeProjectRuntime(),
    ).run_spec(spec, context)

    assert results[0].success is False
    assert results[0].error is not None
    assert results[0].error.code == "letta.runtime_error"
    assert "max_tool_rounds=1" in results[0].summary


def test_run_task_spec_cli_accepts_letta_runtime(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, str] = {}

    class FakeRunStore:
        def __init__(self, workspace: Path) -> None:
            self.workspace = workspace

        def load_spec(self, spec_path: Path) -> TaskSpec:
            return TaskSpec(run_id="run-cli-letta", user_goal="分析M678良率趋势")

        def make_context(self, spec_path: Path, spec: TaskSpec) -> RunContext:
            return RunContext(run_id=spec.run_id or "run-cli-letta", workspace=tmp_path)

    class FakeRouter:
        def run_spec(
            self,
            spec: TaskSpec,
            context: RunContext,
            requested_runtime: str = "auto",
        ):
            captured["requested_runtime"] = requested_runtime
            return SimpleNamespace(
                success=True,
                runtime="letta",
                status="completed",
                summary="ok",
                results=[SkillResult(skill_name="letta_agent", success=True, summary="ok")],
            )

    monkeypatch.setattr(run_task_spec_module, "RunStore", FakeRunStore)
    monkeypatch.setattr(run_task_spec_module, "RuntimeRouter", FakeRouter)

    exit_code = run_task_spec_module.main(
        [
            "--spec",
            str(tmp_path / "spec.yaml"),
            "--workspace",
            str(tmp_path),
            "--runtime",
            "letta",
            "--json",
        ]
    )

    assert exit_code == 0
    assert captured["requested_runtime"] == "letta"
