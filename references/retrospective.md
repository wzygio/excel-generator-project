# Harness Garbage Collection

This Agent-maintained file records periodic cleanup checks for the project Harness.

## Cleanup Checklist

- Check AGENTS.md / `.roorules` for business-module details that should move to lower Harness files.
- Verify links in the Harness index, design index, plans index, and observability reference.
- Move completed execution plans from the active plans folder to the completed plans folder.
- Remove or refresh stale generated summaries under `references/generated/`.
- Confirm referenced commands, test paths, trace paths, and ignored runtime directories still exist.

## Current Status

- Last generated: 2026-06-25 Harness refactor.
- Latest check: `uv run python scripts/harness_check.py --write-audit` returned `ok`.
- Known cleanup items:
  - Review whether legacy empty `references/plan_references/` folders can be removed after Git/user review.
  - Keep AGENTS root short; add new details to routed references instead.
