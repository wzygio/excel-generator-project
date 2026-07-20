# AGENTS.md

## Project Overview

This project is an Excel-based OLED yield-report assistant. It downloads FineReport source reports, analyzes local Excel workbooks, and prepares traceable yield-report outputs through a Spec / Skill / Runtime architecture.

Read `CONTEXT.md` for its domain purpose and stable operating model, and `ARCHITECTURE.md` for its current runtime structure. Harness profile: `agent-workflow-v1`. Prefer explicit, testable, traceable report workflows over broad automatic inference.

## Code Intelligence Policy

- Use CodeGraph first when `.codegraph/` exists.
- Keep `ARCHITECTURE.md` shallow and use code intelligence for deep lookup.

## Context Router

- For domain purpose, vocabulary, and hard boundaries, read `CONTEXT.md`.
- For project shape, ownership, or runtime flow, read `ARCHITECTURE.md`.
- For Harness routing, start at `references/index.md`.
- For requirements and design knowledge, use `.scratch/`, `docs/PRD/`, and `references/design_references/`.
- For execution plans, use `.planning/`.
- For development and validation knowledge, use `references/dev_references/` and `references/test_references/`.
- For durable decisions and delivery knowledge, use `docs/ADR/` and `references/summary_references/`.
- For retained pre-profile design material, use `references/plan_references/`; new durable guidance belongs in the standard routes above.
- For user-maintainable task specs and runtime traces, use `specs/`.

## Iteration Router

- Update `CONTEXT.md` and the domain glossary when stable terminology, invariants, or the operating model changes.
- Update `ARCHITECTURE.md` and design references when ownership or runtime flow changes.
- Update development references when coding rules or restrictions change.
- Update test references when validation, smoke, or observability changes.
- Update `references/retrospective.md` when durable artifact classes or Harness routing changes.
- Keep Harness `index.md` files folder-only.

## Agent skills

### Issue tracker

Issues are tracked as Local Markdown files under `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Local issues use the canonical default state vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository using root `CONTEXT.md` and `docs/ADR/`. See `docs/agents/domain.md`.

## Safety Boundary

- Do not print, copy, commit, or persist secrets from `.env`, credentials, cookies, tokens, or portal sessions.
- Do not delete or overwrite user-provided Excel/source files under `resources/` unless the user explicitly asks.
- Do not commit runtime outputs from `output/`, `downloads/`, `specs/runs/`, caches, browser artifacts, or decrypted resource folders.
- Preserve unrelated user changes.
