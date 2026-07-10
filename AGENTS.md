# AGENTS.md

## Project Overview

This project is an Excel-based OLED yield-report assistant. It downloads FineReport source reports, analyzes local Excel workbooks, and prepares traceable yield-report outputs through a Spec / Skill / Runtime architecture.

This is not a generic BI platform. Prefer explicit, testable, traceable report workflows over broad automatic inference.

## Code Intelligence Policy

- Keep `ARCHITECTURE.md` shallow. Use it for project map and ownership boundaries; use CodeGraph for symbol, caller, callee, and file-level tracing.

## Context Router

- For project shape, ownership boundaries, or runtime flow, read `ARCHITECTURE.md`.
- For Harness routing, start at `references/index.md`.
- For system, Agent, Skill, Spec, module, or feature design, use `references/design/`.
- For coding conventions, restrictions, reusable implementation knowledge, and table/schema references, use `references/dev_references/`.
- For validation, smoke tests, observability, and debugging, use `references/test_references/`.
- For active or historical plans, use `references/plans/` and `.planning/`.
- For generated scans, audits, and agent-maintained summaries, use `references/generated/`.
- For user-maintainable task specs and runtime traces, use `specs/`.

## Iteration Router

- If module ownership, runtime flow, or public architecture changes, update `ARCHITECTURE.md` and the relevant folder under `references/design/`.
- If business rules, Spec fields, Skill contracts, or report behavior change, update the appropriate design reference rather than expanding this root file.
- If coding conventions, dependency policy, or safety restrictions change, update `references/dev_references/`.
- If validation commands, smoke flows, trace locations, or debugging practice changes, update `references/test_references/`.
- After substantial work, update the active planning files. Write generated feedback, audit, and cleanup notes under `references/generated/`; update `references/retrospective.md` only when the Reflect mechanism itself changes.
- Keep Harness `index.md` files folder-only; do not list individual files in indexes.

## Safety Boundary

- Do not print, copy, commit, or persist secrets from `.env`, credentials, cookies, tokens, or portal sessions.
- Do not delete or overwrite user-provided Excel/source files under `resources/` unless the user explicitly asks.
- Do not commit runtime outputs from `output/`, `downloads/`, `specs/runs/`, caches, browser artifacts, or decrypted resource folders.
- Preserve unrelated user changes in the working tree. If existing changes affect the task, work with them rather than reverting them.
- Add dependencies only through project dependency files and explain why existing dependencies are insufficient.
