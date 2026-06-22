# Remote Workbench UI Fixes Findings

## Initial State
- Worktree already has uncommitted V-Agent push changes and unrelated `docs/exec-plans/active/feat-anomaly_monitor.md`, `docs/prompt/HL_answer.md`.
- Next dev server is listening on `0.0.0.0:3000` with process `35332`.
- No obvious enabled inbound firewall block rule for Node/3000 was found from the first quick check.

## UI/API Trace
- Conversation storage supports list/read/save but no delete function or DELETE route yet.
- The right-side artifact panel already links to `/api/artifact?path=...`, but assistant result messages only render the text body, so daily-report success messages show a local path without an in-message download button.
- LAN URL checks from this host:
  - `GET http://10.72.26.31:3000/` returns HTTP 200 and includes Next static assets.
  - `GET http://10.72.26.31:3000/api/conversations` returns HTTP 200.
- Current `CopilotKitProvider` uses relative `runtimeUrl="/api/copilotkit"`, so it should follow the LAN host. No hard-coded `localhost` was found in the layout.

## Final Findings
- HTTP can receive data only when the current component is an HTTP server/listener. The V-Agent screenshot's "发起HTTP请求" node is an outbound client action, so it cannot passively receive our POST by itself; it can call our exposed API and consume the response.
- Remote users must open `http://10.72.26.31:3000/`, not `http://localhost:3000/`. On another computer, `localhost` points to that other computer.
- Next dev needs both a LAN listener (`0.0.0.0`) and allowed dev origins for cross-host browser resources. The dev config now allows `10.72.26.31` and `HF-9CSMGR3-P`.
- The page and `/api/conversations` were reachable over LAN before the UI fix, so the remaining "clicked but no effect" symptom was most likely browser-side resource/API execution rather than a total network outage.
- The artifact API already supported server-side downloads; the missing piece was surfacing download buttons directly in result messages.
