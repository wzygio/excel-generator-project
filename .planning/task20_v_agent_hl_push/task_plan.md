# V-Agent HL Push Plan

## Goal
When the anomaly HL workflow generates the local HL output, the backend also posts the formatted HL anomaly content to a V-Agent endpoint so the external Agent can forward it to a group.

## Constraints
- Do not modify unrelated user changes.
- Keep the change backend-focused unless an existing frontend hook needs only API compatibility.
- Do not hard-code secrets or internal endpoints.
- Keep the local file generation behavior intact.

## Phases

| Phase | Status | Purpose |
|---|---|---|
| 1. Restore context | complete | Read existing worktree state and create this plan. |
| 2. Trace HL workflow | complete | Locate the abnormal HL button/API/Skill path and current formatted output. |
| 3. Implement V-Agent API client | complete | Add configurable POST delivery with safe error handling and traceable result. |
| 4. Wire workflow | complete | Trigger delivery after successful local HL generation. |
| 5. Tests | complete | Add focused tests for payload creation, opt-in config, and failure behavior. |
| 6. Operator guide | complete | Explain V-Agent platform settings and manual verification flow. |
| 7. Screenshot-compatible pull endpoint | complete | Let V-Agent POST the screenshot URL with empty body and receive latest HL text. |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| Patch context failed on existing Chinese warning string | First `apply_patch` | Re-read the UTF-8 line through PowerShell JSON and patched using exact source text. |
| V-Agent settings image not available in current prompt | Operator guide | Provide generic HTTP/Webhook trigger mapping and note that field names may need alignment to the actual V-Agent UI. |
