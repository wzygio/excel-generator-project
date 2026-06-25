# Test Reference Index

## Folder Routes

| Folder | When To Read | Read Guidance | Commands |
|---|---|---|---|
| `references/test_references/acceptance/` | Defining done criteria, checklist gates, or product acceptance expectations. | Read the child index before writing acceptance criteria. | Run the acceptance smoke or focused tests named by the task. |
| `references/test_references/methods/` | Choosing unit, integration, E2E, smoke, or verification strategy. | Read the methods index and validation guidance. | Run the smallest verification command that covers the changed behavior. |
| `references/test_references/tools/` | Need exact project commands, service startup, or Harness check commands. | Read the tools index and project command list. | Use the documented command exactly, then record result in progress. |
| `references/test_references/debug_router/` | A regression is hard to localize or needs a debug workflow. | Read the child index and any debug playbook present. | Start with reproduction, then targeted logs/traces. |

## Local Documents

| Document | When To Read | Commands |
|---|---|---|
| `observability.md` | Before diagnosing failed runs, choosing Observation inputs, or wiring runtime output into Verify. | Inspect concise observation artifacts first, then run focused verification. |

## Update Rule

Use this area for acceptance criteria, test methods, executable test tools, observability, and debug routing.
