# Remote Workbench UI Fixes Progress

## 2026-06-22
- Created isolated plan under `.planning/task21_remote_workbench_ui_fixes`.
- Traced conversation API/store, history JSX, artifact panel, and LAN API checks.
- Added `DELETE /api/conversations/[conversationId]` and a history-card delete button.
- Tightened history-card CSS so long titles, summaries, and status text wrap inside the right panel.
- Added artifact download buttons to assistant result messages and reused the existing `/api/artifact` download API.
- Added Next dev `allowedDevOrigins` for `10.72.26.31` and `HF-9CSMGR3-P`, then restarted the dev server on `0.0.0.0:3000`.
- Verified:
  - `npm run typecheck`
  - `npm run build`
  - `GET http://10.72.26.31:3000/`
  - `GET http://10.72.26.31:3000/api/conversations`
  - create/delete temporary conversation through the LAN API
  - download latest `daily_report_output.xlsx` through `/api/artifact`
