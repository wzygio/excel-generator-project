"""Letta-backed Agent runtime adapter."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from pydantic import BaseModel

from yield_report.agent.client_tools import (
    build_project_client_tool_registry,
    execute_runtime_tool,
    select_runtime_tools_for_skills,
    to_letta_client_tools,
)
from yield_report.agent.registry import build_default_runtime
from yield_report.agent.spec_model import (
    ArtifactRef,
    RunContext,
    SkillCall,
    SkillError,
    SkillResult,
    TaskSpec,
)
from yield_report.agent.trace import TraceEvent

PROJECT_CLIENT_TOOLS: list[dict[str, Any]] = to_letta_client_tools(
    build_project_client_tool_registry()
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class LettaRuntimeConfig(BaseModel):
    """Configuration for invoking Letta."""

    base_url: str = ""
    api_key_env: str = "LETTA_API_KEY"
    server_password_env: str = "LETTA_SERVER_PASSWORD"
    agent_id: str = ""
    agent_name: str = "visionox-yield-monitoring-agent"
    agent_id_cache_path: str = ".agent_workbench/letta_agent_id"
    model: str = "my-glm-key/glm-5.1"
    embedding: str = "my-glm-key/text-embedding-3-large"
    sync_memory_blocks: bool = True
    archive_memory_candidates: bool = True
    use_conversations: bool = True
    compaction_mode: str = "sliding_window"
    compaction_clip_chars: int = 50000
    compaction_prompt: str = "Summarize operational context without inventing facts."
    streaming: bool = True
    stream_tokens: bool = False
    background_runs: bool = False
    timeout_seconds: int = 900
    max_tool_rounds: int = 20


class LettaRuntimeUnavailableError(Exception):
    """Raised when Letta cannot be started or configured."""


class LettaRuntime:
    """Run a TaskSpec through a Letta stateful agent."""

    runtime_name = "letta"

    def __init__(
        self,
        config: LettaRuntimeConfig | None = None,
        client: Any | None = None,
        agent_id: str = "",
        project_runtime: Any | None = None,
    ) -> None:
        self.config = config or LettaRuntimeConfig()
        self.client = client
        self.agent_id = agent_id
        self.project_runtime = project_runtime or build_default_runtime()
        self.client_tool_registry = build_project_client_tool_registry()

    def run_spec(self, spec: TaskSpec, context: RunContext) -> list[SkillResult]:
        tool_results: list[tuple[SkillCall, SkillResult]] = []
        try:
            client = self.client or self._client()
            agent_id = self._resolve_agent_id(client, context, spec)
            self._sync_agent_config(client, agent_id)
            self._sync_memory_blocks(client, agent_id, spec, context)
            conversation_id = self._resolve_conversation_id(client, agent_id, spec, context)
            self._write_trace(context, "letta_runtime", "started", "Sending TaskSpec to Letta")
            prompt = self._build_prompt(spec, context)
            client_tools = self._client_tools_for_spec(spec)
            response = self._send_messages(
                client=client,
                agent_id=agent_id,
                messages=[{"role": "user", "content": prompt}],
                conversation_id=conversation_id,
                client_tools=client_tools,
            )
            response = self._tool_loop(
                client,
                agent_id,
                response,
                spec,
                context,
                tool_results,
                conversation_id,
                client_tools,
            )
        except LettaRuntimeUnavailableError as exc:
            result = self._failed_result(
                code="letta.unavailable",
                message=str(exc),
                details={"exception_type": type(exc).__name__},
            )
            self._write_trace(context, "letta_runtime", "failed", result.summary)
            self._write_run_outputs(context, result, tool_results)
            return [result]
        except Exception as exc:
            result = self._failed_result(
                code="letta.runtime_error",
                message=str(exc),
                details={"exception_type": type(exc).__name__},
            )
            self._write_trace(context, "letta_runtime", "failed", result.summary)
            self._write_run_outputs(context, result, tool_results)
            return [result]

        summary = self._assistant_text(response) or "Letta runtime completed."
        letta_run_id = self._response_run_id(response)
        summary_path = context.output_dir / "letta_summary.md"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(summary, encoding="utf-8")
        result_data = {
            "runtime": self.runtime_name,
            "letta_agent_id": agent_id,
            "letta_conversation_id": conversation_id,
            "letta_run_id": letta_run_id,
        }
        result = SkillResult(
            skill_name="letta_agent",
            success=True,
            summary=summary,
            artifacts=[
                ArtifactRef(
                    kind="markdown",
                    path=summary_path,
                    description="Letta runtime summary",
                )
            ],
            data=result_data,
        )
        result.data["letta_archival_memory_count"] = self._archive_memory_candidates(
            client=client,
            agent_id=agent_id,
            context=context,
            results=[tool_result for _, tool_result in tool_results] + [result],
        )
        self._write_trace(context, "letta_runtime", "succeeded", summary[:500])
        self._write_run_outputs(context, result, tool_results)
        return [result]

    def _client(self) -> Any:
        self._load_runtime_env()
        base_url = self._configured_base_url()
        if base_url and self._is_local_base_url(base_url):
            api_key = os.getenv(self.config.server_password_env)
        else:
            api_key = os.getenv(self.config.api_key_env)
            if not api_key and base_url:
                api_key = os.getenv(self.config.server_password_env)
        if not api_key and (
            not base_url or not self._is_local_base_url(base_url)
        ):
            raise LettaRuntimeUnavailableError(
                "Missing Letta API key env var: "
                f"{self.config.api_key_env}"
            )
        try:
            from letta_client import Letta
        except ImportError as exc:
            raise LettaRuntimeUnavailableError(
                "Missing dependency letta-client. Install it with `uv add letta-client`."
            ) from exc
        if base_url:
            if not api_key:
                return Letta(
                    base_url=base_url,
                    timeout=self.config.timeout_seconds,
                )
            return Letta(
                base_url=base_url,
                api_key=api_key,
                timeout=self.config.timeout_seconds,
            )
        return Letta(api_key=api_key, timeout=self.config.timeout_seconds)

    @staticmethod
    def _load_runtime_env() -> None:
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        load_dotenv(override=False)

    def _resolve_agent_id(
        self,
        client: Any,
        context: RunContext,
        spec: TaskSpec | None = None,
    ) -> str:
        configured = self.agent_id or self.config.agent_id or os.getenv("LETTA_AGENT_ID")
        if configured:
            return configured

        cached = self._read_cached_agent_id(context)
        if cached:
            return cached

        embedding = self.config.embedding.strip()
        if self._is_local_base_url(self._configured_base_url()) and not embedding:
            raise LettaRuntimeUnavailableError(
                "Local Letta server requires agent.letta.embedding when auto-creating "
                "an agent. Set LETTA_AGENT_ID, keep a cached agent id, or configure "
                "agent.letta.embedding."
            )
        create_kwargs: dict[str, Any] = {
            "name": self.config.agent_name,
            "model": self.config.model,
            "description": "Stateful Agent Runtime for Visionox OLED yield monitoring.",
            "tags": ["visionox-yield", "agent-runtime"],
        }
        if embedding:
            create_kwargs["embedding"] = embedding
        compaction_settings = self._compaction_settings()
        if compaction_settings:
            create_kwargs["compaction_settings"] = compaction_settings
        if self.config.sync_memory_blocks:
            create_kwargs["memory_blocks"] = self._memory_blocks(spec, context)
        agent = client.agents.create(**create_kwargs)
        agent_id = str(getattr(agent, "id", "") or "").strip()
        if not agent_id:
            raise LettaRuntimeUnavailableError("Letta agent creation did not return an id.")
        self._write_cached_agent_id(context, agent_id)
        return agent_id

    def _sync_agent_config(self, client: Any, agent_id: str) -> None:
        update = getattr(getattr(client, "agents", None), "update", None)
        if update is None:
            return
        update_kwargs: dict[str, Any] = {"model": self.config.model}
        if self.config.embedding.strip():
            update_kwargs["embedding"] = self.config.embedding.strip()
        compaction_settings = self._compaction_settings()
        if compaction_settings:
            update_kwargs["compaction_settings"] = compaction_settings
        update(agent_id=agent_id, **update_kwargs)

    def _sync_memory_blocks(
        self,
        client: Any,
        agent_id: str,
        spec: TaskSpec,
        context: RunContext,
    ) -> None:
        if not self.config.sync_memory_blocks:
            return
        agent_blocks = getattr(getattr(client, "agents", None), "blocks", None)
        if agent_blocks is None:
            return
        global_blocks = getattr(client, "blocks", None)
        for block in self._memory_blocks(spec, context):
            label = str(block["label"])
            try:
                existing = agent_blocks.retrieve(label, agent_id=agent_id)
            except Exception:
                if global_blocks is None or not hasattr(global_blocks, "create"):
                    continue
                created = global_blocks.create(**block)
                block_id = str(getattr(created, "id", "") or "").strip()
                if block_id and hasattr(agent_blocks, "attach"):
                    agent_blocks.attach(block_id, agent_id=agent_id)
                continue

            if label == "memory_digest" and str(getattr(existing, "value", "") or "").strip():
                continue
            update = getattr(agent_blocks, "update", None)
            if update is None:
                continue
            update(label, agent_id=agent_id, **block)

    def _resolve_conversation_id(
        self,
        client: Any,
        agent_id: str,
        spec: TaskSpec,
        context: RunContext,
    ) -> str:
        if not self.config.use_conversations:
            return ""
        conversations = getattr(client, "conversations", None)
        if conversations is None or not hasattr(conversations, "create"):
            return ""

        cache_path = self._conversation_cache_path(context)
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8").strip()

        conversation = conversations.create(
            agent_id=agent_id,
            description=f"TaskSpec run {context.run_id}",
            summary=(spec.user_goal or context.run_id)[:500],
        )
        conversation_id = str(getattr(conversation, "id", "") or "").strip()
        if not conversation_id:
            return ""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(conversation_id, encoding="utf-8")
        return conversation_id

    def _conversation_cache_path(self, context: RunContext) -> Path:
        safe_run_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", context.run_id or "manual-run")
        return context.workspace / ".agent_workbench" / "letta_conversations" / safe_run_id

    def _configured_base_url(self) -> str:
        return (os.getenv("LETTA_BASE_URL") or self.config.base_url).strip()

    @staticmethod
    def _is_local_base_url(base_url: str) -> bool:
        if not base_url:
            return False
        hostname = urlparse(base_url).hostname or ""
        return hostname.lower() in {"localhost", "127.0.0.1", "::1"}

    def _read_cached_agent_id(self, context: RunContext) -> str:
        cache_path = self._agent_id_cache_path(context)
        if not cache_path.exists():
            return ""
        return cache_path.read_text(encoding="utf-8").strip()

    def _write_cached_agent_id(self, context: RunContext, agent_id: str) -> None:
        cache_path = self._agent_id_cache_path(context)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(agent_id, encoding="utf-8")

    def _agent_id_cache_path(self, context: RunContext) -> Path:
        cache_path = Path(self.config.agent_id_cache_path)
        if cache_path.is_absolute():
            return cache_path
        return context.workspace / cache_path

    def _tool_loop(
        self,
        client: Any,
        agent_id: str,
        response: Any,
        spec: TaskSpec,
        context: RunContext,
        tool_results: list[tuple[SkillCall, SkillResult]],
        conversation_id: str = "",
        client_tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        for round_index in range(self.config.max_tool_rounds):
            approvals: list[dict[str, Any]] = []
            seen_tool_call_ids: set[str] = set()
            for message in getattr(response, "messages", []) or []:
                if getattr(message, "message_type", "") != "approval_request_message":
                    continue
                tool_calls = self._approval_tool_calls(message)
                if not tool_calls:
                    continue
                for tool_call in tool_calls:
                    tool_call_id = str(getattr(tool_call, "tool_call_id", "") or "")
                    if not tool_call_id or tool_call_id in seen_tool_call_ids:
                        continue
                    seen_tool_call_ids.add(tool_call_id)
                    tool_return, status = self._execute_client_tool(
                        tool_call,
                        spec,
                        context,
                        tool_results,
                    )
                    approvals.append(
                        {
                            "type": "tool",
                            "tool_call_id": tool_call_id,
                            "tool_return": tool_return,
                            "status": status,
                        }
                    )

            if not approvals:
                return response

            self._write_trace(
                context,
                "letta_tool_round",
                "succeeded",
                f"round={round_index + 1}, approvals={len(approvals)}",
            )
            response = self._send_messages(
                client=client,
                agent_id=agent_id,
                messages=[{"type": "approval", "approvals": approvals}],
                conversation_id=conversation_id,
                client_tools=client_tools,
            )

        raise RuntimeError(f"Letta exceeded max_tool_rounds={self.config.max_tool_rounds}")

    @staticmethod
    def _approval_tool_calls(message: Any) -> list[Any]:
        tool_calls = getattr(message, "tool_calls", None)
        if isinstance(tool_calls, list):
            return [tool_call for tool_call in tool_calls if tool_call is not None]
        if tool_calls is not None:
            return [tool_calls]

        tool_call = getattr(message, "tool_call", None)
        if tool_call is None:
            return []
        return [tool_call]

    def _send_messages(
        self,
        client: Any,
        agent_id: str,
        messages: list[dict[str, Any]],
        conversation_id: str = "",
        client_tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        client_tools = client_tools or to_letta_client_tools(self.client_tool_registry)
        request_kwargs: dict[str, Any] = {
            "agent_id": agent_id,
            "messages": messages,
            "client_tools": client_tools,
            "max_steps": self.config.max_tool_rounds,
        }
        if self.config.streaming:
            request_kwargs["streaming"] = True
        if self.config.stream_tokens:
            request_kwargs["stream_tokens"] = True
        if self.config.background_runs:
            request_kwargs["background"] = True
        if conversation_id:
            conversation_messages = getattr(
                getattr(getattr(client, "conversations", None), "messages", None),
                "create",
                None,
            )
            if conversation_messages is not None:
                response = conversation_messages(conversation_id, **request_kwargs)
                return self._coerce_response(response)
        response = client.agents.messages.create(**request_kwargs)
        return self._coerce_response(response)

    def _client_tools_for_spec(self, spec: TaskSpec) -> list[dict[str, Any]]:
        workflow_skills = {call.skill for call in spec.workflow}
        return to_letta_client_tools(
            select_runtime_tools_for_skills(workflow_skills, self.client_tool_registry)
        )

    @staticmethod
    def _coerce_response(response: Any) -> Any:
        if hasattr(response, "messages"):
            return response
        if isinstance(response, Iterable) and not isinstance(response, (str, bytes, dict)):
            messages: list[Any] = []
            run_id = ""
            for chunk in response:
                chunk_messages = getattr(chunk, "messages", None)
                if chunk_messages:
                    messages.extend(chunk_messages)
                elif getattr(chunk, "message_type", ""):
                    messages.append(chunk)
                run_id = str(getattr(chunk, "run_id", "") or run_id)
            return SimpleNamespace(messages=messages, run_id=run_id)
        return response

    def _execute_client_tool(
        self,
        tool_call: Any,
        spec: TaskSpec,
        context: RunContext,
        tool_results: list[tuple[SkillCall, SkillResult]],
    ) -> tuple[str, str]:
        del spec
        name = str(getattr(tool_call, "name", ""))
        try:
            args = json.loads(getattr(tool_call, "arguments", "") or "{}")
        except json.JSONDecodeError as exc:
            payload = {"error": f"Invalid tool arguments JSON: {exc}"}
            return json.dumps(payload, ensure_ascii=False), "error"

        try:
            call, result, payload = execute_runtime_tool(
                tool_name=name,
                arguments=args,
                registry=self.client_tool_registry,
                project_runtime=self.project_runtime,
                context=context,
                call_id_prefix="letta",
            )
        except KeyError:
            payload = {"error": f"Unknown Letta client tool: {name}"}
            return json.dumps(payload, ensure_ascii=False), "error"
        tool_results.append((call, result))
        return json.dumps(payload, ensure_ascii=False), "success" if result.success else "error"

    @staticmethod
    def _normalize_client_tool_input(name: str, args: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(args)
        if name == "yield_data_analysis":
            analysis_goal = str(normalized.get("analysis_goal") or "").strip()
            if analysis_goal and not str(normalized.get("question") or "").strip():
                normalized["question"] = analysis_goal
            intent = str(normalized.get("analysis_intent") or "").strip()
            if not intent and any(keyword in analysis_goal for keyword in ["趋势", "变化", "波动", "恶化"]):
                normalized["analysis_intent"] = "trend"
        return normalized

    def _archive_memory_candidates(
        self,
        client: Any,
        agent_id: str,
        context: RunContext,
        results: list[SkillResult],
    ) -> int:
        if not self.config.archive_memory_candidates:
            return 0
        passages = getattr(getattr(client, "agents", None), "passages", None)
        create = getattr(passages, "create", None)
        if create is None:
            return 0

        archived = 0
        seen: set[str] = set()
        for result in results:
            for candidate in result.memory_updates:
                if candidate.record_id in seen:
                    continue
                seen.add(candidate.record_id)
                payload = {
                    "run_id": context.run_id,
                    "record_id": candidate.record_id,
                    "status": candidate.status,
                    "summary": candidate.summary,
                    "metadata": candidate.metadata,
                    "source_skill": result.skill_name,
                }
                try:
                    create(
                        agent_id,
                        text=json.dumps(payload, ensure_ascii=False, sort_keys=True),
                        tags=["runtime", "memory_candidate", candidate.status or "pending"],
                    )
                except Exception as exc:
                    self._write_trace(
                        context,
                        "letta_archival_memory",
                        "failed",
                        f"record_id={candidate.record_id}; error={exc}",
                    )
                    continue
                archived += 1
        return archived

    def _compaction_settings(self) -> dict[str, Any]:
        mode = self.config.compaction_mode.strip()
        if not mode:
            return {}
        settings: dict[str, Any] = {"mode": mode}
        if self.config.compaction_clip_chars > 0:
            settings["clip_chars"] = self.config.compaction_clip_chars
        if self.config.compaction_prompt.strip():
            settings["prompt"] = self.config.compaction_prompt.strip()
        return settings

    def _memory_blocks(
        self,
        spec: TaskSpec | None,
        context: RunContext,
    ) -> list[dict[str, Any]]:
        return [
            {
                "label": "persona",
                "description": "Agent identity and responsibility.",
                "value": (
                    "You are the Visionox OLED yield monitoring runtime agent. "
                    "Understand TaskSpecs, choose registered client tools, and summarize "
                    "results in Chinese."
                ),
                "limit": 4000,
            },
            {
                "label": "runtime_policy",
                "description": "Read-only runtime and tool-use boundaries.",
                "value": (
                    "Use only registered Letta client tools. Treat local SkillResult outputs "
                    "as the source of truth. Never invent file paths, credentials, portal "
                    "sessions, or Excel contents. Return concise summaries and artifact refs."
                ),
                "limit": 8000,
                "read_only": True,
            },
            {
                "label": "domain_contract",
                "description": "Read-only OLED yield-report business contract summary.",
                "value": (
                    "This system analyzes OLED yield reports through typed TaskSpecs and "
                    "project Skills. Complete business truth remains in local specs, traces, "
                    "artifacts, Excel files, and typed Python modules."
                ),
                "limit": 8000,
                "read_only": True,
            },
            {
                "label": "current_task",
                "description": "Current TaskSpec run summary, refreshed by the runtime.",
                "value": self._current_task_block_value(spec, context),
                "limit": 6000,
            },
            {
                "label": "memory_digest",
                "description": "Agent-maintained digest of reusable runtime lessons.",
                "value": "No durable runtime lessons have been recorded yet.",
                "limit": 8000,
            },
        ]

    @staticmethod
    def _current_task_block_value(spec: TaskSpec | None, context: RunContext) -> str:
        if spec is None:
            return f"run_id={context.run_id}"
        product_models = spec.inputs.get("product_models") or spec.inputs.get("products")
        return json.dumps(
            {
                "run_id": context.run_id,
                "spec_run_id": spec.run_id,
                "user_goal": spec.user_goal,
                "workflow_steps": [call.id for call in spec.workflow],
                "product_models": product_models,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    @staticmethod
    def _build_prompt(spec: TaskSpec, context: RunContext) -> str:
        return (
            "# Yield Report TaskSpec\n\n"
            "你正在作为 Letta Agent Runtime 执行良率监控任务。\n"
            "请根据 TaskSpec 自主选择工具。工具执行结果才是事实来源。\n\n"
            f"run_id: {context.run_id}\n"
            f"workspace: {context.workspace}\n"
            f"output_dir: {context.output_dir}\n\n"
            "TaskSpec JSON:\n"
            "```json\n"
            f"{json.dumps(spec.model_dump(mode='json'), ensure_ascii=False, indent=2)}\n"
            "```\n\n"
            "最终请用中文总结：数据源、执行步骤、产物、阻塞项、是否写入 memory 候选。"
        )

    @staticmethod
    def _assistant_text(response: Any) -> str:
        fragments: list[str] = []
        for message in getattr(response, "messages", []) or []:
            if getattr(message, "message_type", "") != "assistant_message":
                continue
            content = getattr(message, "content", "")
            text = LettaRuntime._content_text(content)
            if text:
                fragments.append(text)
        return "\n\n".join(fragments)

    @staticmethod
    def _content_text(content: Any) -> str:
        if isinstance(content, str):
            return content.strip()
        if not isinstance(content, list):
            return ""
        fragments: list[str] = []
        for part in content:
            text = getattr(part, "text", None)
            if text is None and isinstance(part, dict):
                text = part.get("text") or part.get("content")
            if isinstance(text, str) and text.strip():
                fragments.append(text.strip())
        return "\n".join(fragments)

    @staticmethod
    def _failed_result(code: str, message: str, details: dict[str, Any]) -> SkillResult:
        return SkillResult(
            skill_name="letta_agent",
            success=False,
            summary=f"Letta runtime failed: {message}",
            error=SkillError(code=code, message=message, recoverable=True, details=details),
            data={"runtime": "letta"},
        )

    @staticmethod
    def _write_run_outputs(
        context: RunContext,
        final_result: SkillResult,
        tool_results: list[tuple[SkillCall, SkillResult]],
    ) -> None:
        run_dir = LettaRuntime._resolve_run_dir(context)
        summary_path = Path(context.config.get("summary_path") or run_dir / "run_summary.json")
        memory_path = Path(
            context.config.get("memory_candidates_path") or run_dir / "memory_candidates.json"
        )
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        memory_path.parent.mkdir(parents=True, exist_ok=True)

        results = [result for _, result in tool_results] + [final_result]
        artifacts = [
            artifact.model_dump(mode="json")
            for result in results
            for artifact in result.artifacts
        ]
        memory_candidates = [
            candidate.model_dump(mode="json")
            for result in results
            for candidate in result.memory_updates
        ]
        steps = [
            LettaRuntime._tool_step_summary(call, result)
            for call, result in tool_results
        ]
        steps.append(
            {
                "step_id": "letta_runtime",
                "skill": final_result.skill_name,
                "status": "succeeded" if final_result.success else "failed",
                "success": final_result.success,
                "summary": final_result.summary,
                "artifacts": [artifact.model_dump(mode="json") for artifact in final_result.artifacts],
                "warnings": final_result.warnings,
                "error": final_result.error.model_dump(mode="json") if final_result.error else None,
            }
        )

        summary = {
            "run_id": context.run_id,
            "runtime": "letta",
            "letta_agent_id": final_result.data.get("letta_agent_id"),
            "letta_conversation_id": final_result.data.get("letta_conversation_id"),
            "letta_run_id": final_result.data.get("letta_run_id"),
            "letta_archival_memory_count": final_result.data.get(
                "letta_archival_memory_count", 0
            ),
            "status": "completed" if final_result.success else "failed",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "result_count": len(results),
            "steps": steps,
            "artifacts": artifacts,
            "memory_candidates_path": str(memory_path),
        }
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        memory_path.write_text(
            json.dumps(memory_candidates, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _tool_step_summary(call: SkillCall, result: SkillResult) -> dict[str, Any]:
        return {
            "step_id": call.id,
            "skill": result.skill_name,
            "status": "succeeded" if result.success else "failed",
            "success": result.success,
            "summary": result.summary,
            "artifacts": [artifact.model_dump(mode="json") for artifact in result.artifacts],
            "warnings": result.warnings,
            "error": result.error.model_dump(mode="json") if result.error else None,
        }

    @staticmethod
    def _resolve_run_dir(context: RunContext) -> Path:
        configured = context.config.get("run_dir")
        if configured:
            return Path(configured)
        if context.spec_path is not None:
            return Path(context.spec_path).resolve().parent
        output_dir = Path(context.output_dir)
        if output_dir.name == "outputs":
            return output_dir.resolve().parent
        return context.workspace.resolve() / "specs" / "runs" / context.run_id

    @staticmethod
    def _response_run_id(response: Any) -> str:
        return str(getattr(response, "run_id", "") or "")

    @staticmethod
    def _write_trace(
        context: RunContext,
        step_id: str,
        status: str,
        output_summary: str = "",
    ) -> None:
        if context.trace is None:
            return
        context.trace.write(
            TraceEvent(
                run_id=context.run_id,
                step_id=step_id,
                skill="letta_agent",
                status=status,
                output_summary=output_summary,
            )
        )
