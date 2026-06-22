# Remote Workbench UI Fixes Plan

## Goal
Make the Agent Workbench usable from other computers and improve session management: explain the V-Agent HTTP request role, add conversation deletion, constrain conversation card width, expose artifact download buttons, and diagnose/fix remote button clicks that appear to do nothing.

## Constraints
- Preserve unrelated working tree changes.
- Keep V-Agent screenshot configuration workable; adapt our code where needed.
- Avoid changing backend skill behavior unless needed for remote UI correctness.
- Verify with focused UI/backend checks.

## Phases

| Phase | Status | Purpose |
|---|---|---|
| 1. Context and plan | complete | Read skill instructions, inspect current status, create plan. |
| 2. Trace UI/API flow | complete | Locate conversation list, artifact rendering, API calls, and remote URL assumptions. |
| 3. Implement session delete | complete | Add DELETE API and UI delete control with safe event handling. |
| 4. Fix session card layout | complete | Prevent long text/path/status from overflowing the history panel. |
| 5. Add artifact download actions | complete | Render download links/buttons for daily-report outputs. |
| 6. Fix remote click behavior | complete | Make API calls work when accessed by LAN IP and expose failures clearly. |
| 7. Verify | complete | Run typecheck/build and smoke HTTP/API checks. |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
