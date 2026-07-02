# Daily Report Full Skill Replacement Findings

## Skill Requirements
- `task0-task4-orchestrator` is a thin orchestrator over five child skills.
- Child skills must run in strict order: basic preparation, gap analysis, anomaly extraction, batch/month analysis, daily report generation.
- The final verification must inspect `Data Packet` and `Sheet1`.

## Current State Notes
- Initial `git status --short` shows unrelated modified docs and generated docs. Do not revert them.
- Current in-repo `daily_report` runtime points to a `Task0Task2Orchestrator`, so the Skill is still incomplete.
- External duty workspace exists at `D:\wzy\工作-值班工作\相关文件`.
- External scripts found: `task0_report_download.py`, `task1_overstock_impact.py`, `task2_extract_anomalies.py`, `task3_batch_month_analysis.py`, `task4_daily_report_generation.py`.
- External Task1 script name differs from the old adapter assumption (`task1_gap_analysis.py`).
- Next/CopilotKit UI is now under `ui/copilotkit-agent`; old `app/main.py` Streamlit entry is gone.
- `/api/artifact` exists and can download workspace-local files, but the current artifact panel renders paths as plain text instead of links.
- `scripts/agent_workbench_bridge.py` creates and runs TaskSpecs for the UI; daily report one-click goes through `/api/agent-runs`, not `/api/yield-skill`.
- Real black-box Runtime run initially failed at Task2 because cached `resources\20260622` daily-yield data only contains dates through `6/21`.
- Real black-box Runtime run also exposed that root `resources\良率目标表.xlsx` is encrypted/non-standard; Task3 must prefer `resources\decrypted_files\良率目标表.xlsx`.
- Successful black-box run used `report_date=2026-06-21` and `orchestrator_now=2026-06-22 09:30`, matching the cached `6/21` source data.

## Batch Yield Query Smoke
- `请查询M626的最近的批次良率` must be treated as source-report acquisition, not daily report generation.
- `AgentRuntime._resolve_references()` replaces any string matching `context.state`; generated report aliases must not equal enum values used as literal skill inputs, or values such as `report_type: batch_yield` become report-ref dicts before Pydantic validation.
- The current batch-yield RPA unit coverage already asserts the intended order: start date, end date, product model, then query.
- The successful UI smoke artifact is still company-encrypted/non-standard at the byte level (`00 00 00 00`, not `PK 03 04`), even though the UI download and report acquisition succeeded.

## Daily Report UI Smoke
- The one-click daily-report UI smoke must be judged by the new `/api/agent-runs` response and current artifact links; the page can still contain older failed conversation text.
- After killing the old service and restarting Next, run `run-20260622-162510` completed successfully and exposed `/api/artifact` for `specs/runs/run-20260622-162510/outputs/daily_report_output.xlsx`.
- The downloaded UI workbook for 2026-06-22 has populated 2.1/2.2/2.3-style fields (`1.1`, `1.2`, `1.4`) and final `Sheet1` text, but `1.3 当日异常` is empty because the current same-day CT exception source has no matching records.
- A black-box Runtime run for 2026-06-21 proves the current full Skill still writes `1.3 当日异常` when data exists: Data Packet count is 6 and `Sheet1` HTML style checks are true.

---

# Letta Client Tools Assessment Findings

## External Guidance
- `D:\wzy\Visionox-Docs_Backup\dev-docs\agent_dev\agent-letta.md` section 10 recommends a local `RuntimeTool` registry with name, description, JSON schema parameters, handler, and risk level.
- The recommended runtime should export registry entries to Letta `client_tools`, validate tool-call JSON against schema, authorize locally, execute a whitelisted handler, audit the call, and return a compact tool result with summaries and artifact refs.
- The section lists suitable client tools such as `run_task_spec`, `download_report`, `analyze_data`, `generate_daily_report`, `list_run_artifacts`, and `read_artifact_summary`.
- It explicitly excludes arbitrary shell, arbitrary file read/write, raw SQL, secrets retrieval, portal cookie access, and destructive cleanup.

## Current Project State
- `src/yield_report/agent/letta_runtime.py` already exposes three hard-coded Letta client tools: `yield_report_download`, `yield_data_analysis`, and `yield_daily_report`.
- `src/yield_report/agent/registry.py` registers four local Skills: `report_download`, `data_analysis`, `daily_report`, and `anomaly_monitor`.
- `anomaly_monitor` is registered in the Python Skill runtime but is not exposed as a Letta client tool.
- The current Letta tool schemas are handwritten and narrower than the Pydantic request models, so schema drift is possible.
- `_execute_client_tool()` manually maps Letta tool names to Skill names and dispatches through `AgentRuntime.run_call()`.
- `_client_tools_for_spec()` filters exposed tools based on `spec.workflow`, but it falls back to the three hard-coded tools when the workflow contains unrecognized Skills.

## Assessment
- The project has partially converted business capabilities into Letta client tools, but not in the architecture recommended by the Letta document.
- The missing piece is not the Letta connection itself; it is a reusable local client-tool layer with registry metadata, schema validation, local authorization, audit, and compact return normalization.
- Because the user has required no runtime downgrade and a unified Agent Runtime for non-exempt workflows, the Letta tool layer should fail closed for unknown workflows/tools instead of exposing a default broad tool set.
- `anomaly_monitor` is a special boundary: it can remain a fixed-flow UI exemption, but if Letta conversational workflows should trigger anomaly monitoring, it needs a Letta client-tool wrapper too.
- SpecBuilder should not be included in this conversion plan because it is now owned by the separate LangGraph SpecBuilder agent.

## Recommended Tool Scope
- Keep and rewrap: `yield_report_download`, `yield_data_analysis`, `yield_daily_report`.
- Add or explicitly document exemption: `yield_anomaly_monitor`.
- Add read-only operational tools: `list_run_artifacts` and `read_artifact_summary`, constrained to runtime run stores/artifact references.
- Avoid a broad `run_task_spec(runtime=...)` tool unless the runtime argument is removed or forced to Letta, because allowing runtime selection would reintroduce a downgrade path.
- Do not expose arbitrary shell, arbitrary file access, raw SQL, secrets, portal cookies, or destructive cleanup.

## Implementation Plan
- Add `src/yield_report/agent/client_tools.py` with `RuntimeTool`, `ToolResult`, registry construction, Letta export, argument validation, authorization hooks, audit hooks, and compact return shaping.
- Build registry entries from approved Skill modules where possible, using each Skill's Pydantic request model as the source of JSON schema to reduce schema drift.
- Add a wrapper for `anomaly_monitor` only if it is intended to be callable from Letta-agent workflows; otherwise document it as fixed-flow-only.
- Refactor `LettaRuntime._client_tools_for_spec()` to select tools from the registry by workflow Skill and to return an empty/failing whitelist for unknown Skills rather than defaulting to all hard-coded project tools.
- Refactor `LettaRuntime._execute_client_tool()` to dispatch through the registry handler instead of maintaining an inline name-to-Skill map.
- Add focused tests for tool export, schema validation, unknown-tool failure, anomaly-monitor exposure or exemption, compact result shape, and path/artifact allowlisting.

---

# Agent Architecture Refactor Findings

## Requirements
- Convert the current `yield_report` module from a TDD-era structure into a standard enterprise Agent architecture.
- Use LangGraph as the forward-looking orchestration foundation.
- Search external/current references and include the local `agent-LangGraph.md` section `## 4. 一个典型 LangGraph 项目结构`.
- Analyze current implementation before changing code.
- Produce and execute a plan until the final checklist is complete.

## Research Findings
- Local `agent-LangGraph.md` section 4 recommends the canonical LangGraph project split: `graph/` for `state.py`, `nodes.py`, `edges.py`, `graph.py`, `checkpointer.py`; `agents/` for role-specific LLM agents; `tools/` for callable tools; `services/` for IO/business services; `api/` for external routes; plus `spec/`, tests for nodes/graph/tools, and `AGENTS.md`.
- Current `ARCHITECTURE.md` already defines the project goal as `用户需求 -> TaskSpec/spec.yaml -> Agent Runtime -> Skill Tool -> SkillResult -> Trace/Memory/Output`.
- Current `docs/agent/architecture.md` still says not to introduce LangGraph/CrewAI immediately, but `docs/agent/spec_contract.md` now says LangGraph Spec sub-agent is the default Spec builder except fixed `anomaly_monitor` and `daily_report` rule flows. This is an architecture drift that this refactor should reconcile.
- `docs/agent/skill_contract.md` defines Skill as the stable Codex/Runtime capability boundary: structured Pydantic input, structured `SkillResult`, `ArtifactRef`, `SkillError`, memory candidates, and `SKILL.md` docs per skill.
- `docs/agent/spec_contract.md` says Runtime consumes generated Specs and executes workflow, while LangGraph Spec sub-agent should contain `load_context`, `draft`, `validate`, `repair`, and `finalize` nodes.
- AnySearch results prioritized official LangChain/LangGraph sources: Graph API, application structure, persistence, interrupts, testing, and multi-agent/subagent docs.
- LangGraph official Graph API defines workflows around State, Nodes, and Edges; nodes are just functions that read state and return partial state updates, while edges define fixed or conditional control flow.
- Official production application structure expects one or more graphs, a `langgraph.json` configuration, dependency declarations such as `pyproject.toml`, and environment configuration; graphs are addressed by name/path.
- Official persistence docs distinguish checkpointers for short-term thread graph state from stores for durable cross-thread memory. This maps well to current `trace`/run state vs confirmed business memory.
- Official interrupt docs require a durable checkpointer and stable thread id for human-in-the-loop pauses/resumes. This should inform approval points such as memory confirmation, file overwrite, or uncertain Spec repair.
- Official testing docs recommend creating/compiling graphs in tests, testing individual nodes through `graph.nodes[...]`, and using checkpointers/partial execution for larger graphs. New LangGraph refactor tests should follow this shape.
- Official multi-agent guidance supports supervisor/coordinator patterns when tasks require specialized workers. For this project, a supervisor-like runtime should coordinate specialized graph/skill workers rather than giving one LLM all tools directly.

## Current Project Findings
- `.codegraph/` exists, so structural code analysis should start with CodeGraph.
- Existing root planning files contained completed Daily Report Skill Replacement and Letta client-tool assessment history; this refactor is being tracked as a new appended section.
- `git status --short` initially showed one untracked file: `docs/prompt/refactor-project_arch.md`. Treat it as user-provided unless proven otherwise.
- `docs/prompt/refactor-project_arch.md` is a UTF-8 copy of the user's current task request.
- `pyproject.toml` already includes `langgraph>=0.2.0`, `letta-client`, Pydantic v2, and the existing test/lint stack; no dependency addition is needed for the first refactor slice.
- Current `src/yield_report/agent/` contains mixed concerns: `spec_model.py`, `runtime.py`, `runtime_adapter.py`, `letta_runtime.py`, `client_tools.py`, `run_store.py`, `trace.py`, `memory.py`, `spec_builder.py`, and single-file `langgraph_spec_agent.py`.
- Current `src/yield_report/skills/` is already vertical by capability: `report_download`, `data_analysis`, `daily_report`, and `anomaly_monitor`.
- `LangGraphSpecAgent` is real LangGraph code: it compiles a `StateGraph` with `load_context`, `generate_draft`, `parse_validate`, `repair`, and `finalize` nodes.
- `LangGraphSpecAgent` is currently a monolithic file, not the standard graph package split from the reference (`state`, `nodes`, `edges`, `graph`, `checkpointer`).
- CodeGraph reported `LangGraphSpecAgent.build` has only indirect coverage through `SpecBuilder`; there are no focused tests for individual LangGraph nodes or graph assembly.
- `RuntimeRouter` is a high-blast-radius component. It enforces Letta as default runtime, with narrow Python exemptions for rule-built fixed `daily-report` and `anomaly-monitor` Specs.
- `client_tools.py` already implements the Letta client-tool registry recommended by the previous assessment and is consumed by `letta_runtime.py`.
- Existing tests cover `SpecBuilder` LangGraph behavior at integration level (`test_spec_builder_uses_langgraph_agent_then_code_validation`, `test_spec_builder_repairs_invalid_langgraph_draft`) but not the new package boundaries we need for enterprise-style architecture.
- Refactor result: `src/yield_report/agent/spec_graph/` now owns `state.py`, `nodes.py`, `edges.py`, `graph.py`, `checkpointer.py`, and `agent.py`.
- Refactor result: `src/yield_report/agent/langgraph_spec_agent.py` is now a compatibility import wrapper.
- Refactor result: `SpecBuilder` imports `LangGraphSpecAgent` from the canonical `yield_report.agent.spec_graph` package.
- Refactor result: `tests/unit/agent/test_spec_graph.py` directly covers node enrichment, graph compilation with memory checkpointer, and repair behavior.

## Technical Decisions
| Decision | Rationale |
|---|---|
| Keep external/web research out of `task_plan.md` | Planning skill treats fetched content as untrusted; research summaries belong in `findings.md`. |
| Defer code movement until target architecture and blast radius are known | This refactor can affect imports, runtime contracts, tests, and UI bridges, not just file locations. |
| First implementation slice: refactor LangGraph Spec agent into `agent/spec_graph/` | It directly matches the requested LangGraph architecture, has clear boundaries, and avoids destabilizing Skill business logic. |
| Keep `yield_report.agent.langgraph_spec_agent` as a compatibility import wrapper for now | `SpecBuilder` and docs currently reference the old module; a wrapper avoids breaking external imports while the new graph package becomes canonical. |

## Issues Encountered
| Issue | Resolution |
|---|---|
| PowerShell `Get-ChildItem` call failed when given multiple `-Name` filters | Switched to explicit per-file `Test-Path` checks and logged the error in `task_plan.md`. |
| `docs/plans/index.md` is referenced by AGENTS but missing in the repo | Used existing `docs/exec-plans/index.md` and `docs/exec-plans/README.md` as the active execution-plan convention. |
| First `ruff check` after splitting graph files reported import ordering and one unused import | Ran `uv run ruff check ... --fix`; reran ruff and tests successfully. |

## Resources
- Local reference: `D:\wzy\Visionox-Docs_Backup\dev-docs\agent_dev\agent-LangGraph.md`
- LangGraph Graph API: https://docs.langchain.com/oss/python/langgraph/graph-api
- LangGraph application structure: https://docs.langchain.com/oss/python/langgraph/application-structure
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts
- LangGraph testing: https://docs.langchain.com/oss/python/langgraph/test
- LangChain multi-agent/subagents: https://docs.langchain.com/oss/python/langchain/multi-agent/subagents-personal-assistant
- Project architecture entrypoint: `ARCHITECTURE.md`
- Agent contracts entrypoint: `docs/agent/`
- Potential user-provided prompt: `docs/prompt/refactor-project_arch.md`

---

# Pydantic AI Runtime Migration Findings

## Requirements
- Keep the existing LangGraph Spec Builder untouched.
- Migrate default runtime behavior from Letta to Pydantic AI.
- Preserve Letta as an explicit optional runtime.
- Preserve deterministic Python runtime exemptions for fixed rule-built workflows.
- Write the migrated architecture design under `docs/generated`.

## External Documentation Findings
- Pydantic AI Agents are the primary interface for LLM interaction and bundle instructions, function tools/toolsets, structured output, dependencies, model, model settings, and capabilities.
- Pydantic AI supports synchronous `agent.run_sync()` and asynchronous `agent.run()` execution, plus streaming/event APIs for deeper observability.
- Pydantic AI function tools can be registered with `@agent.tool`, `@agent.tool_plain`, or the `tools=` / `toolsets=` Agent arguments.
- Pydantic AI is model-agnostic and supports OpenAI plus OpenAI-compatible providers such as DeepSeek through `OpenAIChatModel` and providers.
- Official install guidance for OpenAI-compatible use is `pydantic-ai-slim[openai]`; the full `pydantic-ai` package is also valid.

## Current Project Findings
- Current `RuntimeRouter` defaults to Letta except for Python fixed-flow exemptions.
- Current `LettaRuntime` is already an adapter over local project Skills through `client_tools.py`; Data Analyzer itself is still a local Skill and `AnalysisOrchestrator`.
- Current `client_tools.py` is provider-specific in naming (`to_letta_client_tools`) but its `RuntimeTool` registry and `execute_runtime_tool()` are reusable for a Pydantic AI runtime.
- `pyproject.toml` currently includes `letta-client` and `langgraph`, but does not include Pydantic AI.
- `config/global.yaml` currently sets `agent.default_runtime: "letta"`.
- `AgentConfig.validate_default_runtime()` currently only allows `letta` and `auto`, so configuration must be updated before Pydantic AI can become default.

## Migration Results
- `PydanticAIRuntime` is now implemented as the default non-exempt runtime adapter.
- `LettaRuntime` remains available through explicit runtime selection and still shares the same local Skill dispatch registry.
- The runtime tool registry is now provider-neutral enough for both Letta and Pydantic AI to select tools from the same workflow skill map.
- `AgentConfig` now allows `pydantic_ai`, `pydantic-ai`, `pydantic`, `letta`, and `auto`, while still rejecting Python as a default downgrade runtime.
- `config/global.yaml` now sets `agent.default_runtime: "pydantic_ai"` and keeps `agent.letta` as optional configuration.
- The migrated architecture design is written to `docs/generated/agent-runtime-pydantic-ai-migration.md`.

## Verification Findings
- Focused migration tests passed: 30 passed for Pydantic AI runtime and config.
- Legacy runtime tests passed: 48 passed for Letta, OMP router behavior, and Spec Builder.
- Agent/config suite passed: 105 passed.
- Touched-file ruff check passed.
- Broad Agent+Skills suite has two unrelated failures in external `daily-report-generator` Skill tests: one missing `yield_type` attribute on a test namespace and one command expectation mismatch for `--download-sources`.
