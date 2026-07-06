# Findings: Nanobot Runtime Analysis

## Research Notes
- Official repository cloned from `https://github.com/HKUDS/nanobot.git` into `D:\Projects\nanobot`.
- `pyproject.toml` names the package `nanobot-ai` at version `0.2.2` and classifies it as `Development Status :: 3 - Alpha`.
- Console script entrypoint is `nanobot = "nanobot.cli.commands:app"`.
- Source-local `AGENTS.md` describes the high-level runtime as `Channels -> MessageBus -> AgentLoop -> AgentRunner -> provider/tools -> outbound channel`.
- Source-local `AGENTS.md` lists the WebUI as a Vite React app under `webui/`, with the gateway command `nanobot gateway`.

## Source Architecture Findings
- Core execution is a general agent loop, not a project-specific workflow DAG:
  - inbound channel messages enter a bus;
  - `AgentLoop` owns session keys, context construction, tool registration, MCP connections, hooks, and direct processing;
  - `AgentRunner` performs the provider call / tool call / tool result loop until final output or limits;
  - outbound adapters send the final/streaming result back to the channel.
- `nanobot/agent/loop.py` exposes `process_direct(...)`, which can be used by the Python SDK and accepts hooks, a session key, per-run metadata, and an optional custom tool registry.
- `nanobot/agent/runner.py` uses `AgentRunSpec` for the loop contract. The spec includes messages, tools, model settings, workspace, session key, streaming callbacks, checkpoint callbacks, and failure policy.
- Tools are first-class extension points:
  - tool classes inherit from `nanobot.agent.tools.base.Tool`;
  - each tool has `name`, `description`, `parameters`, `execute`, plus optional `enabled(ctx)` and `create(ctx)`;
  - `ToolLoader` discovers built-in tools from `nanobot.agent.tools` and external plugin tools from the `nanobot.tools` Python entry-point group;
  - `ToolRegistry` validates tool names and JSON-object parameters before execution.
- Skills are instruction/context packages rather than deterministic executable pipeline steps:
  - workspace skills live under `<workspace>/skills/<skill-name>/SKILL.md`;
  - built-in skills live under `nanobot/skills`;
  - `SkillsLoader` summarizes skills in the system context and loads full content when selected;
  - a skill can tell the agent how to use a tool or CLI, but execution still depends on the available tools or shell permissions.
- MCP is also a supported extension path. The WebUI includes APIs for configuring/testing MCP presets and custom MCP servers, and the runtime connects MCP tools into the tool registry.
- The WebUI is a Vite React app served by the WebSocket channel/gateway. Its HTTP routes expose bootstrap, settings, sessions, skills, automations, workspaces, MCP presets, media, and sidebar state.
- The WebUI is feature-rich for chat/session/tool debugging, but custom domain pages are not exposed as a simple plugin surface. Adding a dedicated OLED yield-report dashboard would require patching the React app and Python HTTP routes.
- The Python SDK (`Nanobot.from_config`, `run`, `run_streamed`, `stream`) is a practical embedding surface for local integration. It supports session continuity, streaming events, hooks, and per-run metadata.

## Deployment Findings
- `D:\Projects` existed and did not already contain a `nanobot` git repository.
- Clone completed successfully; local branch is `main...origin/main` with no local changes immediately after clone.
- Python deployment uses a local `.venv` under `D:\Projects\nanobot`.
- Editable Python install succeeded with `uv pip install -e .`.
- WebUI source can be built with npm; `npm ci` and `npm run build` succeeded even though bun is not installed.
- Built WebUI assets are served from `D:\Projects\nanobot\nanobot\web\dist`.
- `nanobot webui --help` confirms support for `--config`, `--workspace`, `--background`, `--no-open`, `--port`, and `--gateway-port`.
- `nanobot webui --yes` still requires a valid provider/model config; it cannot fill provider credentials automatically.
- `npm ci` reported 10 dependency vulnerabilities in the frontend dependency tree. This should be tracked separately before production exposure, but it did not block local build/deployment.
- A local isolated config was created at `D:\Projects\nanobot\.local\config.json` with:
  - local WebSocket/WebUI on `127.0.0.1:8765`;
  - gateway health on `127.0.0.1:18790`;
  - local no-key Ollama preset `llama3.2`;
  - heartbeat, dream, and transcription disabled for a quiet local deployment.
- `nanobot status --config ... --workspace ...` passed.
- `nanobot webui --yes --no-open --background --config ... --workspace ...` started successfully after the local config was present.
- HTTP verification passed:
  - `http://127.0.0.1:18790/health` returned `200 {"status": "ok"}`;
  - `http://127.0.0.1:8765` returned HTTP 200 and served the WebUI HTML.
- Background gateway status reports `Running: yes`, PID `31076`, and log file `D:\Projects\nanobot\.local\logs\gateway.a7d82ad76d571ec8.log`.

## Migration Fit Findings
- Nanobot can support custom OLED business workflows, but through an agentic skill/tool model rather than this project's existing deterministic `TaskSpec.workflow` model.
- A nanobot skill alone is not enough for this project. The skill can describe the workflow and examples, but a custom Tool or MCP server must expose the actual deterministic report execution operations.
- The cleanest integration is a custom nanobot tool plugin that wraps this project's existing execution kernel:
  - accept `spec_path`, `TaskSpec` JSON, or a stable `workflow_name + arguments` payload;
  - validate input with the existing project Pydantic models;
  - delegate to the current `RuntimeRouter` / project runtime / CLI;
  - return compact summaries plus artifact paths, warnings, and failure reasons.
- Nanobot's WebUI would immediately help with chat-level debugging, tool-call inspection, sessions, skill prompts, settings, MCP setup, and automations. It would not automatically replace a domain-specific report UI.
- Current Pydantic AI Runtime is still a better production default for this repository because it is small, test-covered, fail-closed around allowed runtime tools, and preserves `TaskSpec` / `SkillResult` traceability.
- Nanobot is stronger where the user currently feels pain: WebUI, multi-session chat, tool experimentation, MCP configuration, automation scheduling, and agentic invocation of skill instructions.
- Recommended architecture:
  1. Keep current Pydantic AI Runtime as the deterministic execution kernel.
  2. Add nanobot as an optional local sidecar/workbench.
  3. Expose a small set of project tools to nanobot via the `nanobot.tools` entry-point group.
  4. Add a workspace skill such as `yield-report` that teaches nanobot when and how to call those tools.
  5. Consider an optional `NanobotRuntime` adapter only after the sidecar tool path passes smoke tests and preserves the trace contract.
- A full replacement would be higher risk because nanobot is alpha, broader in surface area, and does not natively model this project's `TaskSpec` DAG, fixed-flow exemptions, or `SkillResult` output contract.

## Risks
- The local WebUI is running with an Ollama model placeholder. If Ollama/model is not actually available, sending a chat message will fail at model-call time.
- Frontend dependency vulnerabilities were reported by npm audit. This is acceptable for isolated local source inspection, but should be handled before exposing beyond localhost.
- The downloaded project classifies itself as Alpha in `pyproject.toml`; its API surface may shift.
- A nanobot migration that relies only on natural-language skills would weaken determinism and traceability. The project should keep business execution inside typed tools or the existing runtime kernel.
- Customizing nanobot WebUI beyond existing settings/skills/automations likely means maintaining a fork or patch set against upstream frontend/backend code.
