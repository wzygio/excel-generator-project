# V-Agent HL Push Findings

## Notes
- Current task starts on `main` at `23e89c4`.
- Existing unrelated worktree changes at start: `docs/exec-plans/active/feat-anomaly_monitor.md` modified and `docs/prompt/HL_answer.md` untracked.
- The workbench anomaly button calls `/api/agent-runs`, which builds a TaskSpec through `SpecBuilder`; it does not pass `push_notifications` from the frontend.
- The legacy direct bridge `/api/yield-skill` still exists and dispatches through `scripts/copilotkit_skill_bridge.py`.
- Existing `AnomalyMonitorRequest.push_notifications` was a gated placeholder; it is the narrowest backend-owned switch for V-Agent delivery.

## Implementation Notes
- V-Agent delivery is configured only through environment variables:
  - `YIELD_REPORT_V_AGENT_WEBHOOK_URL`
  - optional `YIELD_REPORT_V_AGENT_TOKEN`
  - optional `YIELD_REPORT_V_AGENT_TIMEOUT_SECONDS`
  - optional `YIELD_REPORT_V_AGENT_HEADERS_JSON`
- The outbound JSON body exposes a stable `message` field for simple V-Agent prompt variables and structured fields for richer workflows.
- Missing endpoint or no HL drafts skips network delivery without failing local artifact generation.
- The current prompt did not include the V-Agent settings screenshot; final setup guidance uses generic HTTP/Webhook trigger terminology.
- The later V-Agent screenshot is an outbound HTTP request node. It can call the local app at `http://10.72.26.31:3000/`, expects Text output, and currently has an empty JSON body plus 10 second timeout.
- Because a full anomaly-monitor run can exceed 10 seconds, the screenshot-compatible path should return a cached latest HL message instead of running the workflow inside the V-Agent HTTP request.
