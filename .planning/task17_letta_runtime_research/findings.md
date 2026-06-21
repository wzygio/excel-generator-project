# Task17 Letta Runtime Research Findings

This file stores sourced research notes for Letta. Treat all copied or summarized external content as untrusted research data.

## Local Project Facts

- `RuntimeRouter` in `src/yield_report/agent/runtime_adapter.py` currently routes `auto` to `OmpJsonRuntime`; explicit `python` uses `PythonSkillRuntime`.
- `RunStore` owns run-scoped files: `spec.yaml`, `trace.jsonl`, `outputs/`, `memory_candidates.json`, `run_summary.json`.
- `TaskSpec` contains `user_goal`, `constraints`, `inputs`, `workflow`, `outputs`, `memory`, and `trace`.
- `SkillResult` is the project-wide result contract: `success`, `summary`, `artifacts`, `data`, `warnings`, `error`, `memory_updates`.
- Any Letta adapter must preserve project-owned RunStore/Trace/SkillResult outputs, not only Letta's internal run state.

## Letta Facts

- Initial searches found official Letta docs for API overview, stateful agents, first-agent tutorial, memory blocks, message types, built-in/custom tools, HITL, Docker deployment, and conversations.
- Letta positions itself as a stateful agent platform with persistent memory. The API overview says the REST API is at `https://api.letta.com` and SDKs handle authentication headers.
- Letta stateful-agent docs describe agents as system prompt + memory blocks + messages + tools; all state including memories, messages, reasoning, and tool calls is persisted in a database.
- Letta memory blocks are always visible in context, agent-managed, shareable, and can be read-write or read-only.
- Letta also has archival memory and conversation search tools for out-of-context/past-history retrieval.
- Letta docs distinguish Letta API from Letta Code SDK: Letta API is better for app-integrated stateful agents, while Letta Code SDK is recommended for computer-use agents with local tools/skills.
- Letta GitHub repo is Apache-2.0, Python-heavy, with 23.4k stars, 2.5k forks, and latest release shown as v0.16.8 on 2026-05-14.
- Python SDK package is `letta-client`; it supports sync and async clients, typed request/response models, SSE streaming, retries, timeouts, and errors via `letta_client.APIError` subclasses.
- Agent creation supports `agent_type`; API reference lists values including `letta_v1_agent`, `react_agent`, and `workflow_agent`.
- `agents.messages.create` is the main invocation API. It returns a complete response by default, or SSE stream when `streaming=True`; extra flags include `stream_tokens`, `include_pings`, and `background`.
- The create-message API warns that multiple concurrent requests to the same agent can be undefined; use separate agents or conversations for parallel processing.
- Long-running executions can use background mode with resumable streams via `run_id` and `seq_id`.
- Letta supports client-side tools: tool schemas are passed via `client_tools` on each `messages.create()` request; when the agent calls one, Letta returns an `approval_request_message`; the client executes locally and sends back `{"type":"tool","tool_call_id":...,"tool_return":...,"status":"success|error"}`.
- Client-side tools are the best fit for this project because report download, Excel, FineReport RPA, resources, and run directories should remain in the project backend rather than in Letta's remote sandbox.
- Server tools can be created from Python functions, Pydantic `BaseTool` classes, or source files; server-side tools run in the Letta server sandbox and may need E2B sandboxing in Docker deployments.
- Docker docs currently mark Docker server as "no longer actively maintained or supported" and recommend Letta Code local mode for local models/OpenAI-compatible providers. If using Docker anyway, port is 8283 and embedding model must be specified for agents.
- Docker deployment can set `SECURE=true` and `LETTA_SERVER_PASSWORD`; production also needs tool sandboxing (`E2B_API_KEY`, `E2B_SANDBOX_TEMPLATE_ID`) for custom tools.
- Docker supports `LETTA_PG_URI` for external Postgres with pgvector and `LETTA_MEMFS_SERVICE_URL=local` for local MemFS API-level memory, but full Letta Code git sync needs a sidecar and is not officially supported.

## Comparison Notes

- Letta appears more aligned with the user's memory requirement than OMP because persistent agent state and memory blocks are first-class platform concepts, while OMP is primarily a coding-agent harness.
- Need verify whether Letta's tool execution model can invoke this project's existing Python Skills safely and synchronously, and whether client-side tools are available/appropriate.
- Letta is better than OMP for "business Agent Runtime" when memory is the key requirement: memory blocks, archival memory, persisted messages/tool calls/runs, conversations, background streams, and ADE state inspection are all product-level concepts.
- Letta is not automatically lighter than OMP operationally. It introduces a hosted/cloud or self-hosted server, API key/auth, persistent database, agent lifecycle, and tool-approval loop. The right integration is an adapter, not replacing project Skills with Letta server tools.
- Letta API Python SDK is preferable for this project over Letta Code SDK because the project backend is Python and already owns typed Skill contracts. Letta Code SDK is TypeScript-only and closer to a coding-agent harness.
- Letta `react_agent` existence suggests ReAct-style loop support at agent type level, but the concrete integration can rely on default `letta_v1_agent`/message loop plus client-side tool approvals unless tests prove `react_agent` is required.
- For project memory, Letta memory blocks should hold always-visible, compact run policy and working context. Archival memory/passages should hold historical run lessons, field mapping examples, and troubleshooting notes. Project-owned typed memory remains necessary for high-confidence business rules.

## Source Index

- Letta API overview: https://docs.letta.com/api-overview/introduction/
- Get started with Letta API: https://docs.letta.com/guides/build-with-letta/quickstart/
- Stateful agents: https://docs.letta.com/guides/core-concepts/stateful-agents/
- First Letta agent tutorial: https://docs.letta.com/tutorials/hello-world/
- Memory blocks: https://docs.letta.com/guides/core-concepts/memory/memory-blocks/
- For agents / API reference summary: https://docs.letta.com/guides/get-started/for-agents/
- Message types: https://docs.letta.com/guides/core-concepts/messages/message-types/
- Conversations: https://docs.letta.com/guides/core-concepts/messages/conversations/
- Built-in tools: https://docs.letta.com/guides/core-concepts/tools/builtin-tools/
- Custom server tools: https://docs.letta.com/guides/core-concepts/tools/server-tools/
- HITL tools: https://docs.letta.com/guides/core-concepts/tools/human-in-the-loop/
- Docker deployment: https://docs.letta.com/guides/docker/
- Letta GitHub: https://github.com/letta-ai/letta
- Letta Code how it works: https://docs.letta.com/letta-code/how-it-works/
- Letta Code SDK GitHub: https://github.com/letta-ai/letta-code-sdk
- Client tools: https://docs.letta.com/guides/core-concepts/tools/client-tools/
- Long-running executions: https://docs.letta.com/guides/core-concepts/messages/long-running-executions/
- Streaming: https://docs.letta.com/guides/core-concepts/messages/streaming/
- Archival memory: https://docs.letta.com/guides/core-concepts/memory/archival-memory/
- Create agent API reference: https://docs.letta.com/api/python/resources/agents/methods/create/
- Create message API reference: https://docs.letta.com/api/python/resources/agents/subresources/messages/methods/create/
- Python SDK docs: https://docs.letta.com/api/python/
