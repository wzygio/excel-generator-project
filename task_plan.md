# Daily Report Full Skill Replacement Plan

## Goal
Replace `src/yield_report/skills/daily_report` with the full Task0-Task4 OLED daily report orchestrator while keeping the runtime working directory and adding a final file download surface.

## Requirements
- Runtime can call the full daily report Skill and receive a file.
- UI smoke test: clicking the daily report button produces a downloadable complete report.
- E2E test: service is reachable and the daily report workflow can be accessed.
- The replacement must preserve the existing Skill path used by runtime callers.

## Phases

| Phase | Status | Purpose |
|---|---|---|
| 1. Understand source skills | complete | Read current daily_report implementation and the Task0-Task4 child skills. |
| 2. Define public interface | complete | Map current request/result contract to full orchestrator execution and download artifacts. |
| 3. TDD replacement | complete | Add black-box tests, then implement replacement. |
| 4. Verification | complete | Run unit/black-box tests and service reachability checks. |
| 5. UI smoke | complete | Use Playwright MCP to click the UI and confirm downloadable report output. |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| `task0_task4_orchestrator` import missing | First red test run | Added full Task0-Task4 adapter module and wired `execute_daily_report`. |
| Excel COM fallback monkeypatch targeted old module name | First green attempt | Patched the test to mock the shared workbook reader helper module. |
| Batch-yield query routed to daily report | UI smoke for `请查询M626的最近的批次良率` | Added a source-report download branch in SpecBuilder. |
| `report_type=batch_yield` was resolved as a report dict | First fixed UI smoke | Generated report aliases now use `source_<report_type>` to avoid runtime reference collisions. |
| Task0/Excel lock left workbook unavailable | Daily-report UI smoke | Added Task0 timeout handling plus hidden Excel cleanup/file-unlock wait, then reran after killing old services. |
| Playwright saw historical failure text | First daily-report UI poll | Waited for the new `/api/agent-runs` response and artifact link instead of scanning the full page tail. |

---

# Letta Client Tools Assessment Addendum

## Goal
Evaluate whether the current Agent Runtime has converted necessary business tools into Letta client tools according to `agent-letta.md` section 10, excluding the LangGraph-based SpecBuilder agent.

## Phases

| Phase | Status | Purpose |
|---|---|---|
| 1. Read target guidance | complete | Read `agent-letta.md` section 10 and identify the recommended client-tool registry shape. |
| 2. Inspect current runtime | complete | Compare `LettaRuntime` client tool wiring against registered project Skills. |
| 3. Gap analysis | complete | Decide whether current hard-coded tools are sufficient or a pluggable registry is needed. |
| 4. Recommendation | complete | Produce a concise implementation plan or no-change rationale. |

## Recommendation Summary
- Current state is a partial conversion: three hard-coded Letta client tools exist, but the project has not implemented the pluggable `RuntimeTool` registry recommended by the Letta guidance.
- SpecBuilder is intentionally out of scope because it has been moved to a separate LangGraph agent.
- Recommended next implementation is to create a fail-closed Letta client-tool registry over approved business Skills and artifact-read tools, then refactor `LettaRuntime` to export and execute tools through that registry.

---

# Agent Architecture Refactor Plan

## Goal
Refactor the current `yield_report` implementation from the existing TDD-era module shape into a standard, enterprise-grade Agent architecture that is aligned with LangGraph and preserves verified report behavior.

## Current Phase
Complete

## Requirements
- Search current Agent/LangGraph architecture guidance and incorporate the local reference `D:\wzy\Visionox-Docs_Backup\dev-docs\agent_dev\agent-LangGraph.md`, especially `## 4. 一个典型 LangGraph 项目结构`.
- Analyze the current program structure before moving code.
- Identify whether the refactor needs only module movement or also import, interface, adapter, runtime, test, and workflow rewrites.
- Produce an execution plan with a final target checklist.
- Execute the plan iteratively until the checklist is complete.
- Preserve existing user work and runtime artifacts; do not delete user-provided Excel/resources.

## Phases

| Phase | Status | Purpose |
|---|---|---|
| 1. Research and architecture baseline | complete | Gather external/current LangGraph Agent structure guidance and project-specific reference docs. |
| 2. Current-state analysis | complete | Use CodeGraph and docs to map current `yield_report` modules, entrypoints, runtime flow, interfaces, tests, and coupling. |
| 3. Target architecture and checklist | complete | Define enterprise Agent package structure, migration rules, compatibility boundaries, and final checklist. |
| 4. Refactor implementation | complete | Move/add/refactor code in small verified steps, updating imports/interfaces/tests as needed. |
| 5. Verification and hardening | complete | Run targeted and broader checks; fix regressions until the checklist is complete. |
| 6. Delivery summary | complete | Summarize final architecture, changed files, verification, and residual risks. |

## Target Checklist
- [x] `yield_report` has a clear Agent architecture with graph/state/nodes/tools/runtime boundaries.
- [x] LangGraph-owned workflow orchestration is explicit and documented.
- [x] Existing Skills and report logic remain callable through stable public entrypoints or intentional compatibility adapters.
- [x] Imports are updated and no stale module paths remain in source/tests/docs touched by the refactor.
- [x] Runtime interfaces have typed request/result contracts and fail-closed tool/workflow dispatch.
- [x] Existing daily report, report download, data analysis, anomaly monitor, and SpecBuilder behavior is preserved or intentionally rehomed.
- [x] Focused tests cover new architecture boundaries and compatibility behavior.
- [x] Relevant unit tests pass.
- [x] `ruff`/typing-sensitive checks are run where risk justifies them.
- [x] Planning files record research, decisions, errors, and verification results.

## Decisions Made

| Decision | Rationale |
|---|---|
| Preserve existing planning history and append this refactor plan | Previous plan sections are completed audit history; appending keeps continuity without overwriting useful context. |
| Use CodeGraph first for code analysis | `.codegraph/` exists and project instructions require CodeGraph before grep/read for structural questions. |
| Scope first implementation slice to LangGraph Spec graph package | Existing Skill/Runtime contracts are already mostly Agent-shaped; this brings the LangGraph piece to the requested standard structure with limited blast radius. |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| `Get-ChildItem -Name` with multiple filename arguments failed in PowerShell | 1 | Replaced with explicit per-file `Test-Path` checks. |
| `docs/plans/index.md` referenced by AGENTS but missing | 1 | Used the existing `docs/exec-plans/index.md` and `docs/exec-plans/README.md` planning convention instead. |
| `ruff check` reported unsorted imports and one unused import after the split | 1 | Ran `uv run ruff check ... --fix`, then reran ruff and tests successfully. |

## Verification

| Command | Result |
|---|---|
| `uv run pytest tests/unit/agent/test_spec_graph.py -q --tb=short` | 3 passed |
| `uv run pytest tests/unit/agent/test_spec_builder.py tests/unit/agent/test_anomaly_monitor_spec.py -q --tb=short` | 14 passed |
| `uv run pytest tests/unit/agent tests/unit/skills -q --tb=short` | 113 passed |
| `uv run ruff check src/yield_report/agent/spec_builder.py src/yield_report/agent/langgraph_spec_agent.py src/yield_report/agent/spec_graph tests/unit/agent/test_spec_graph.py` | passed |

---

# Pydantic AI Runtime Migration Plan

## Goal
Migrate the default Agent Runtime from Letta to a lightweight Pydantic AI based runtime while preserving the LangGraph Spec Builder and keeping Letta Runtime as an explicit optional runtime.

## Requirements
- Do not migrate or rewrite the LangGraph/Spec Builder path.
- Keep `LettaRuntime` available for explicit `runtime=letta` runs.
- Make Pydantic AI the default runtime for non-exempt Agent tasks.
- Preserve deterministic Python runtime exemptions for rule-built `daily-report` and `anomaly-monitor` specs.
- Keep Skill execution traceable through existing `TaskSpec`, `SkillResult`, `Trace`, artifact, and memory-candidate contracts.
- Output the migrated architecture design under `docs/generated`.

## Phases

| Phase | Status | Purpose |
|---|---|---|
| 1. Restore context and plan | complete | Read existing planning files, inspect current state, and append this migration plan. |
| 2. Runtime baseline and docs | complete | Use CodeGraph and official Pydantic AI docs to map current runtime boundaries and required API surface. |
| 3. Implement Pydantic AI runtime | complete | Add Pydantic AI runtime adapter, configuration, tool dispatch, and fail-closed output handling. |
| 4. Preserve optional Letta | complete | Update router/config/tests so Letta remains callable but no longer default. |
| 5. Architecture documentation | complete | Write the post-migration architecture design to `docs/generated`. |
| 6. Verification | complete | Run focused runtime/config tests, lint touched files, and record results. |

## Decisions Made

| Decision | Rationale |
|---|---|
| Keep Spec Builder unchanged | The user explicitly requires the existing LangGraph-based Spec Builder architecture to stay in place. |
| Keep Letta optional | Letta still has value for external stateful/API-backed tasks, but should not be the stable default runtime. |
| Build a runtime adapter first, not a broad autonomous shell agent | The project needs traceable, fail-closed business Skill execution before general Codex-like CLI autonomy. |
| Use `pydantic-ai-slim[openai]` | Official docs recommend this lightweight package for OpenAI-compatible providers, matching the current DeepSeek-compatible setup. |

## Verification

| Command | Result |
|---|---|
| `uv run pytest tests/unit/agent/test_pydantic_ai_runtime.py tests/unit/test_config_loader.py -q --tb=short` | 30 passed |
| `uv run pytest tests/unit/agent/test_letta_runtime.py tests/unit/agent/test_omp_runtime.py tests/unit/agent/test_spec_builder.py -q --tb=short` | 48 passed |
| `uv run pytest tests/unit/agent tests/unit/test_config_loader.py -q --tb=short` | 105 passed |
| `uv run ruff check ...` on touched runtime/config/test/script files | passed |
| `uv run pytest tests/unit/agent tests/unit/skills -q --tb=short` | 119 passed, 2 failed in external `daily-report-generator` Skill tests |
| `git diff --check` | passed; only Git LF-to-CRLF warnings |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| Context7 tools were not exposed after tool discovery | 1 | Used official Pydantic documentation via web lookup and recorded the source in findings. |
| PowerShell rejected Bash-style `python - <<'PY'` heredoc | 1 | Switched to a PowerShell here-string piped into `uv run python -`. |
| Search scope accidentally included `.env` | 1 | Do not include `.env` or secret-bearing files in further searches, generated docs, or summaries. |
| Generated architecture document did not exist yet | 1 | Create `docs/generated/agent-runtime-pydantic-ai-migration.md` as the requested output. |
| Broad `tests/unit/agent tests/unit/skills` run failed in external `daily-report-generator` Skill tests | 1 | Treat as residual unrelated failure; focused Runtime/config tests pass and no migration code touched the external Skill script. |
