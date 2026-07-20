# Docs Artifact Router

## Purpose

Navigate durable project artifacts under `docs/`. Reusable guidance belongs in `references/`; temporary task state belongs in `.scratch/` and `.planning/`.

## Artifact Routes

- `docs/PRD/` — Approved requirement and product-specification documents.
- `docs/ADR/` — Durable architectural decisions and their consequences.
- `docs/dev_docs/` — Development prompts, tutorials, and generated engineering guidance.
- `docs/agents/` — Repository-specific Agent/Harness operating configuration.
- `docs/others/` — Retained project documents outside the other artifact classes.
- `docs/dev_plans/` — Retained legacy development plans.
- `docs/dev_prompt/` — Retained legacy development prompts.
- `docs/generated/` — Retained historical generated documents.
- `docs/project_files/` — User-provided project reference workbooks; do not overwrite them.

## Update Rule

When a durable artifact class is added under `docs/`, add its folder route here. Keep this router folder-level; do not list individual documents.
