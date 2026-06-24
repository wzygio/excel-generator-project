# Daily Report Refactor Task2 Findings

## Prompt Requirements
- Task2 Step0 changes the earlier plan: do not preserve the old `Task0Task4Orchestrator`; avoid code pollution.
- Fixed-button daily-report should continue to use Python exemption.
- Letta smoke for Step2 must go through Letta, not Python exemption.
- The end date should be obtained through Spec builder/LangGraph path, not by manually changing Skill inputs during smoke.

## Initial Project State
- Root planning files record a prior partial implementation: current `daily_report` already calls an in-project `Task0Task4Orchestrator`.
- The requested refactor is stricter: replace that in-project orchestrator with the user-installed native `daily-report-generator` pipeline.
- Current active planning pointer before this task was `task21_remote_workbench_ui_fixes`.
- Basic Preparation is a thin wrapper that calls `daily_report_cli.py run --task task0 --workspace <duty workspace> --mode inspect/write`.
- `daily-report-generator` currently has `--now` but no `--end-date`; `PipelineRunner` does not expose end date to task requests.
- `task0_basic_preparation.toml` currently runs `task0_report_download.py --write` without `--download-sources`, so it does not satisfy the Step1 smoke expectation of creating a dated resources folder.
- The underlying duty `task0_report_download.py` accepts `--end-date`, but its default download folder still uses `datetime.now()` instead of the requested end date.
- Current `LettaRuntime` has hard-coded `PROJECT_CLIENT_TOOLS` and inline tool-name-to-Skill mapping; it does not yet implement the `RuntimeTool` registry from the Letta guidance.
- Step1 task0 smoke succeeded for `--end-date 2026-06-23`; it created/refreshed `D:\wzy\工作-值班工作\相关文件\resources\20260623-16：00`.
- Excel COM verified the downloaded daily-yield workbook has `6/23` as the last date header in the CT sheet.
- Native generator subprocesses must force UTF-8 IO on Windows; otherwise JSON artifact paths become mojibake when child scripts print through GBK stdout.

## Open Questions To Resolve In Code
- Whether CopilotKit requires the current `DailyReportRequest` shape, or whether only TaskSpec/Skill callers depend on it.
- Whether the native generator CLI can accept enough request fields directly, or whether the project facade must translate.
- Whether external duty workspace/network/Letta credentials are available for the requested black-box smokes.

## Step0 Corrected Plan Decision
- Keep `DailyReportRequest` stable for existing CopilotKit/TaskSpec callers, and extend the native generator CLI/contract to accept the missing runtime fields. This avoids forcing UI callers to change while still moving business execution into the native pipeline.
- Remove the in-project `Task0Task4Orchestrator` path from `execute_daily_report`; use a native pipeline facade instead.
- Preserve fixed-button Python exemption in `RuntimeRouter`; Letta smoke will explicitly request Letta runtime and exercise the Letta client tool path.
- Letta client tools should be generated from a local registry and fail closed for unknown workflow skills/tools.

## Final Smoke Findings
- A daily_report TaskSpec should expose only `yield_daily_report` to Letta. The native daily-report generator already owns Task0-Task4; exposing low-level download/analysis tools encouraged Letta to take a slower and less reliable path.
- Letta may pass plausible but wrong operational arguments. The native facade must validate `orchestrator_workspace` instead of trusting it; a valid duty workspace contains `scripts/task0_report_download.py`.
- For explicit historical reports, `report_date` is authoritative. The facade normalizes native runner `now` to `<report_date> 16:00` so the output suffix remains deterministic.
- Final black-box run `agent-daily-report-20260624-160217` used `constraints.spec_builder=langgraph`, `runtime=letta`, and produced `D:\wzy\工作-值班工作\相关文件\V3良率日报每日异常填报表-20260623-16：00.xlsx`.
