# Daily Report Refactor Task2 Plan

## Goal
Complete Task2 from `docs/prompt/refactor-daily_report.md`: adjust the plan, optimize the native daily-report generator for an explicit end date, refactor the in-project `daily_report` skill to use the native pipeline directly, and verify through Letta-driven smoke where possible.

## Requirements
- Do not keep the old in-project `Task0Task4Orchestrator` interface as a compatibility path after refactor.
- Preserve fixed-button daily-report Python exemption mode.
- Make `DailyReportRequest` and `daily-report-generator` compatible without forcing CopilotKit callers to change unless required.
- Add a final functionality checklist from Step0 and drive implementation against it.
- Use TDD: one public behavior test, minimal implementation, then repeat.
- Smoke Step1 through Basic Preparation/task0 with explicit end date behavior.
- Smoke Step2 through Letta, not Python exemption, with the end date parsed by the Spec builder path rather than manually injected into the Skill call.

## Final Functionality Checklist
- [x] Native `daily-report-generator` accepts an optional explicit end/report date and defaults to current business date when omitted.
- [x] Basic Preparation/task0 writes or refreshes the expected dated resource folder for the specified end date.
- [x] The daily-yield workbook in that folder has its last daily date equal to the requested end date.
- [x] Project `daily_report` delegates to the native generator pipeline rather than maintaining a separate Task0-Task4 script orchestrator.
- [x] `DailyReportRequest` remains compatible with existing CopilotKit/TaskSpec inputs, or the native CLI accepts the needed fields.
- [x] Letta client tools are registry-based, fail closed for unknown tools/workflows, and can execute `yield_daily_report`.
- [x] Fixed-button daily-report Python exemption remains supported.
- [x] Step2 smoke creates the expected final daily report in the external duty workspace with suffix `20260623-16：00`.

## Phases

| Phase | Status | Purpose |
|---|---|---|
| 0. Restore and inspect | complete | Read task prompt, existing plans, Skill docs, and current code contracts. |
| 1. Step0 corrected plan | complete | Convert prior analysis into an implementation checklist and architectural decision. |
| 2. Step1 native date support | complete | TDD support for explicit end date in daily-report-generator and smoke task0. |
| 3. Step2 daily_report refactor | complete | TDD replace in-project orchestrator with native pipeline facade. |
| 4. Letta tool registry | complete | TDD replace hard-coded Letta tools with registry dispatch for daily_report. |
| 5. Smoke and verification | complete | Run focused tests, Step1 smoke, and Letta/UI black-box smoke if environment allows. |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| task0 smoke masked real error with `UnicodeDecodeError` on stderr | First Step1 smoke | Added `errors="replace"` to native generator subprocess capture. |
| Wrapper failed printing captured replacement characters under GBK stdout | Second Step1 smoke | Reconfigured native generator stdout/stderr to UTF-8 with replacement. |
| Returned artifact path was mojibake because child Python emitted GBK JSON | Third Step1 smoke | Forced `PYTHONIOENCODING=utf-8` for nested task subprocesses. |
| FineReport large-data report loading exceeded default waits | Full native smoke | Made duty task0 waits environment-aware and raised browser/report/download defaults for this flow. |
| Letta first called low-level report download tools during daily_report workflow | First Letta smoke | Scoped daily_report workflow client tools to `yield_daily_report` only. |
| Letta supplied project root as `orchestrator_workspace` | Letta smoke | Native facade now ignores workspaces that do not contain the native duty task0 script. |
| Letta supplied current-day `orchestrator_now` for a historical report date | Letta smoke | Native facade normalizes runner `now` from `report_date`, preserving the expected `20260623-16：00` suffix. |
