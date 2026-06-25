# Reflect Router

This file defines the end-of-iteration Reflect mechanism. It should describe how the Harness reflects, not store run-specific results.

## When To Read

Read this file near the end of a substantial task, after implementation and verification, when deciding what should be preserved as Harness knowledge.

Do not keep this file in the default task context. Reflect is an end-stage mechanism and should stay lightweight.

## Reflect Flow

1. Review the active planning files for completed work, errors, decisions, and verification.
2. Inspect the current diff and generated observations or audits.
3. Separate durable mechanism changes from run-specific results.
4. Promote stable knowledge to the correct reference area.
5. Store generated or historical status under `references/generated/`.
6. Keep `AGENTS.md` and index files short; route details into lower references.

## Where To Write

| Content | Target |
|---|---|
| Current task progress, attempts, and command results | Active `.planning/<plan-id>/progress.md` |
| Discoveries, decisions, and reusable findings from the current task | Active `.planning/<plan-id>/findings.md` first, then promote if durable |
| Stable architecture or contract decisions | `references/design/` |
| Stable coding rules, restrictions, schemas, or templates | `references/dev_references/` |
| Stable validation, observability, command, or debug guidance | `references/test_references/` |
| Generated audits, cleanup notes, status snapshots, scans, or historical summaries | `references/generated/` |
| Long-lived project plans | `references/plans/` or `references/exec-plans/` |

## Promotion Criteria

Promote a finding out of planning files only when it is:

- reusable across future tasks,
- tied to a stable project mechanism or contract,
- not merely a one-run result,
- safe to keep in repository context,
- and easier for future agents to discover from a routed reference than from planning history.

## Generated Output Rule

Do not append status snapshots, latest check results, one-off cleanup items, or generated summaries to this file. Write those artifacts under `references/generated/` and link/promote only stable policy changes to the appropriate reference.
