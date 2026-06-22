# Task Plan: Anomaly Monitor Development

## Goal
Implement the Task1 anomaly-monitor development plan in this isolated worktree: add a registered `anomaly_monitor` Skill, deterministic rule engine, TaskSpec integration, UI preset support, and verification artifacts.

Task2 extends the same worktree with one-click buttons for every fixed business workflow.
Task2 data-source follow-up fixes the anomaly-monitor source mapping and rule-flow semantics so
the one-click workflow can run against the real local CT anomaly workbook.
Task2-fix tightens the real-data anomaly screening so the smoke summary no longer emits hundreds
of HL rows: concentration uses stricter dynamic unit ratios, mwdl fallback candidates are not
over-expanded, and only `发生站点=CT` rows can become final HL anomalies.

## Current Phase
Task3 complete: merged into Runtime-refactor mainline

## Phases

### Phase 1: Context And TDD Setup
- [x] Create isolated git worktree and branch.
- [x] Create implementation planning files.
- [x] Inspect relevant runtime, Skill, and UI files in this worktree.
- [x] Add failing focused tests for the anomaly-monitor Skill and Spec integration.
- **Status:** complete

### Phase 2: Backend Skill Implementation
- [x] Add anomaly-monitor models, analyzers, templates, sources, tool, and implementation.
- [x] Register the Skill in the default runtime.
- [x] Add SpecBuilder and validation support.
- [x] Keep ledger write and notification push gated/disabled by default.
- **Status:** complete

### Phase 3: UI Integration
- [x] Add Workbench preset/options for anomaly monitor.
- [x] Display anomaly monitor rows/drafts/warnings from Skill result data.
- [x] Preserve existing daily-report and analysis workflows.
- **Status:** complete

### Phase 4: Verification Loop
- [x] Run focused tests and fix failures.
- [x] Run agent/skill test suite.
- [x] Run ruff and pyright where feasible.
- [x] Run UI typecheck/build and browser smoke if UI changes require it.
- [x] Record verification-loop report.
- **Status:** complete

### Phase 5: Final Review
- [x] Inspect diff for unintended changes.
- [x] Update planning progress and summarize outcomes.
- **Status:** complete

### Task2: Fixed Workflow One-Click Execution
- [x] Identify fixed workflows currently represented in the Workbench.
- [x] Add one-click buttons for daily report generation and anomaly monitoring.
- [x] Ensure fixed buttons use deterministic goal text instead of stale composer input.
- [x] Keep old `/api/yield-skill` module validation aligned with registered modules.
- [x] Verify UI typecheck/build and browser smoke.
- **Status:** complete

### Task2 Follow-Up: Data Source And Business Flow Correction
- [x] Decode and inspect the encrypted rule workbook for 1.1.1-1.1.2 source/rule contracts.
- [x] Replace missing `resources/anomaly_monitor/*` defaults with the real CT anomaly workbook fallback.
- [x] Normalize `CT良率异常波动管理表.xlsx` rows into daily initial candidates and batch-history rows.
- [x] Filter candidates to the requested report date, falling back to the latest available date for the selected product.
- [x] Fix date parsing and avoid treating the same CT source row as an already-HL historical match.
- [x] Align `true_anomaly` / `real_anomalies` with the rule output `HL异常数据`.
- [x] Verify the one-click anomaly workflow screens real data without missing-source errors.
- **Status:** complete

### Task2-fix-2: Source Evidence For Real Anomaly Screening
- [x] Audit the current anomaly-monitor result payload for proof that related source data was acquired.
- [x] Add TDD coverage requiring source row counts, candidate dates, and source-backed real-anomaly evidence.
- [x] Emit `source_summary` with compact date windows for `daily_anomaly_initial`, `ct_exception`, and `batch_history`.
- [x] Emit `source_evidence.real_anomaly_rows` with source table, product, defect, station, losses, notice text, reply text, status, and owner.
- [x] Render source row counts in the UI result panel for one-click anomaly monitoring.
- [x] Verify against the real local CT anomaly workbook and the Browser one-click flow.
- **Status:** complete

### Task2-fix: HL Noise Reduction
- [x] Analyze why `output/anomaly_monitor_smoke/anomaly_monitor_summary.md` had too many HL rows.
- [x] Add TDD coverage for dynamic concentration top-unit ratio.
- [x] Add TDD coverage for mwdl fallback candidate narrowing and CT-only final HL station rule.
- [x] Implement stricter concentration and candidate/station filtering.
- [x] Re-run anomaly_monitor smoke until final HL count is <= 15.
- [x] Record verification evidence and updated result artifact paths.
- **Status:** complete

### Task3: Merge Anomaly Monitor Into Runtime-Refactor Mainline
- [x] Confirm target branch for "master" in this repository.
- [x] Inspect anomaly-monitor branch changes against the Runtime-refactor mainline.
- [x] Merge/replay anomaly-monitor backend Skill into the refactored Agent Runtime.
- [x] Merge/replay UI one-click anomaly monitor affordance into the current Workbench UI.
- [x] Resolve conflicts by keeping Runtime kernel/architecture from the refactor branch.
- [x] Verify backend Runtime executes `anomaly_monitor`.
- [x] Run focused Agent/Skill tests and relevant lint/type checks.
- [x] Run browser/Playwright smoke for the "异常监控" flow and verify a real anomaly is screened.
- **Status:** complete

## Key Decisions
| Decision | Rationale |
|----------|-----------|
| Work in `D:\wzy\Python\excel-generator-project-anomaly-monitor` | Task1-2 explicitly asks for a new worktree and the main worktree has unrelated dirty changes. |
| Start with synthetic fixtures and deterministic tests | Real workbook/source files are encrypted or incomplete; tests must be stable and not mutate business files. |
| Treat missing key-station rule as recoverable warning/blocker | Workbook leaves the rule blank; implementation must not silently fabricate final certainty. |
| Keep write/push disabled by default | Ledger writes and group messages are external side effects requiring explicit confirmation. |
| Use CT anomaly workbook as fallback candidate source | The requested Spotfire daily initial table is not present locally; the available `CT良率异常波动管理表.xlsx` is the only real source that can drive a traceable smoke run. |
| Treat all `HL` decisions as `真实异常` | The rule workbook defines 1.1.2 output as `HL异常数据`; key-station over-spec is a trigger/subtype, not the only real-anomaly definition. |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| Initial apply_patch targeted the main worktree path | 1 | Re-applied using absolute paths for the new worktree. |
| `uv run pyright` unavailable | 1 | Used `uvx pyright --venvpath .` without changing project dependencies. |
| `npm run build` required `DEEPSEEK_API_KEY` | 1 | Re-ran build with a one-shot placeholder environment variable for build validation only. |
| Full `uv run ruff check .` hit existing repository lint baseline | 1 | Fixed the one issue in this task's files, then verified the touched backend paths with focused Ruff. |
| Next dev/build touched `next-env.d.ts` | 2 | Confirmed empty diff and refreshed the index so it stays out of the implementation diff. |

## Checklist
- [x] `anomaly_monitor` is registered in Python runtime.
- [x] Skill writes JSON and Markdown artifacts under `context.output_dir`.
- [x] Rules cover batch gate, concentration, already-HL, spec calculation, and draft generation.
- [x] TaskSpec builder recognizes anomaly-monitor goals.
- [x] UI can send an anomaly-monitor preset request.
- [x] Verification-loop phases are run and documented.
