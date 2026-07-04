# Findings & Decisions

## Requirements
- Build a standalone Streamlit UI under `app/` for daily report generation.
- UI must call `src/yield_report/skills/daily_report/` reliably.
- UI must provide generated report download.
- Create startup scripts patterned after `D:\wzy\Python\array-projects` / `start_ela_system`.
- Add/update Windows Task Scheduler task, preferably existing `2.Excel日报自动生成`, to auto-start.

## Research Findings
- Active planning context before this task was `2026-06-25-harness-optimization`, a completed and unrelated Harness optimization plan.
- Root-level legacy planning files currently show as deleted in git status; this task uses an isolated `.planning/` directory and does not restore or modify those root files.
- `daily_report` wrapper defaults to current repo workspace and writes generated reports under `output/artifacts/reports/generated`.
- `app/` had no standalone Streamlit daily-report entry before this work.
- `pyproject.toml` did not list `streamlit`; `streamlit>=1.37.0` is now added as a project dependency.
- Existing scheduled task `2.Excel日报自动生成` existed but was Disabled. It runs `wscript.exe D:\wzy\Python\excel-generator-project\run_hidden.vbs`, starts in the repo root, and has daily 7:00, daily 16:00, and weekend 14:00 triggers.
- Reference `D:\wzy\Python\array-projects\start_ela_system.bat` kills any process listening on its configured port, changes to repo root, sets `PYTHONPATH`, activates `.venv`, then runs Streamlit.
- This repo had no `run_hidden.vbs` at the root even though the scheduled task pointed to it.
- `start_daily_report_ui.bat` and `run_hidden.vbs` now exist at the repo root.
- Scheduled task `2.Excel日报自动生成` is now Enabled/Ready. Its next run is `2026-07-04 07:00:00`.
- A local startup health check passed at `http://localhost:8502` with HTTP 200.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Service layer between UI and skill | Gives Streamlit a small stable API and makes generation/download behavior testable without launching a browser. |
| Use existing `daily_report` skill result artifacts for downloads | Keeps business logic behind the skill wrapper and avoids duplicating report-generation rules in UI. |
| Mirror array-project startup shape | It already solves single-instance-on-port, virtualenv activation, hidden launch, and Task Scheduler compatibility. |
| Use port `8502` | The existing task comment already pointed to `http://10.72.26.31:8502`; keeping it avoids changing user-facing access. |
| Preserve existing scheduled triggers | The task already had useful daily/weekend triggers, so only enabling the task was necessary after creating the missing VBS target. |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| Startup script files were missing while the task pointed to `run_hidden.vbs` | Added `start_daily_report_ui.bat` and `run_hidden.vbs`. |
| Generated-report ordering test was timestamp-sensitive on Windows | Set deterministic mtimes in the test. |

## Resources
- `src/yield_report/skills/daily_report/`
- `app/`
- `D:\wzy\Python\array-projects`
- Existing task scheduler name: `2.Excel日报自动生成`
- Existing project task command: `wscript.exe D:\wzy\Python\excel-generator-project\run_hidden.vbs`

## Visual/Browser Findings
- Streamlit startup health check returned HTTP 200 on `http://localhost:8502`.
