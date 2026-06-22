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
