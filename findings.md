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
