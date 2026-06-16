# Task Plan: Anomaly Monitor Task1

## Goal
Analyze the reference anomaly-monitor template, business rules, and current project architecture, then produce a complete development plan for the anomaly monitor module without implementing code.

## Current Phase
Phase 6

## Phases

### Phase 1: Planning Context
- [x] Read user request and execution-plan Task1.
- [x] Restore existing planning context and create isolated planning files.
- [x] Capture initial requirements and constraints.
- **Status:** complete

### Phase 2: Reference Template Analysis
- [x] Inspect `D:\wzy\Python\agents-projects\packages\anomaly_monitor`.
- [x] Identify reusable workflows, domain models, APIs, UI pieces, and tests.
- [x] Record migration risks and mismatches with this repository.
- **Status:** complete

### Phase 3: Rule Workbook Analysis
- [x] Inspect/decrypt `docs\dev-docs\屏体大数据科-良率监控智能体需求梳理.xlsx`.
- [x] Read sheet `值班智能体-需求梳理`.
- [x] Extract anomaly-monitor rules, especially steps 1.1.1-1.1.3 and any later dependencies.
- **Status:** complete

### Phase 4: Current Architecture Mapping
- [x] Use `.understand-anything/knowledge-graph.json` for project structure.
- [x] Read `ARCHITECTURE.md` and relevant Harness docs.
- [x] Map backend, agent/skill/spec, and CopilotKit UI extension points.
- **Status:** complete

### Phase 5: Development Plan Draft
- [x] Define target module boundaries and data contracts.
- [x] Break implementation into testable tasks.
- [x] Include validation strategy, risks, and migration notes.
- **Status:** complete

### Phase 6: Review And Delivery
- [x] Verify referenced paths exist or note blockers.
- [x] Update planning files with final findings.
- [x] Deliver the plan to the user and ask for confirmation before implementation.
- **Status:** complete

## Key Questions
1. Which reference-template components can be reused directly, and which must be adapted to the current Spec / Skill / Runtime architecture?
2. What are the authoritative anomaly rules from the encrypted workbook, and how do they differ from the reference template?
3. Where should the new fixed workflow live across backend modules, agent/skill contracts, specs, and the CopilotKit UI?
4. What tests and smoke checks are required before implementation is accepted?

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Create isolated planning directory `task16_anomaly_monitor_task1` | Existing active plan points to unrelated UI refactor work; this task needs separate persistent context. |
| Do not implement code in Task1 | The execution plan explicitly says the goal is to produce a complete development plan first. |
| Treat anomaly monitor as a new fixed workflow candidate | `ARCHITECTURE.md` says fixed, repeated workflows should be Spec-driven and Skill-backed, while legacy layers remain compatibility implementation. |
| Reuse template business rules selectively, not package shape wholesale | The template uses old `packages.*` imports, Streamlit UI, direct Excel ledger writes, and optional CrewAI logic that do not match the current project architecture. |
| Keep the full implementation plan in `.planning/task16_anomaly_monitor_task1/development_plan.md` until user confirmation | Project Harness says non-trivial plans should be confirmed before updating long-lived `docs/plans` or active execution plans. |
| Use current Skill runtime as the primary integration surface | `registry.py`, `RuntimeRouter`, `RunStore`, and Workbench bridge already expect registered Python Skills with Pydantic request models. |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| Initial plan file read appeared garbled | 1 | Re-read with explicit UTF-8 encoding. |
| `fr_file_decryption.read_excel()` failed on Chinese path/sheet in PowerShell stdin | 1 | Avoided Chinese command literals by globbing paths from Python and then used Excel COM direct read by sheet index. |
| COM SaveAs from `fr_file_decryption` produced a non-standard encrypted-header `.xlsx` copy | 1 | Used a temporary COM UsedRange read probe and noted implementation should reuse/extract the existing `daily_report.ExcelSheetReader` style reader. |

## Notes
- User asked to complete Task1 only: planning and analysis, no implementation.
- Preserve unrelated working-tree changes.
- Full development plan artifact: `.planning/task16_anomaly_monitor_task1/development_plan.md`.
