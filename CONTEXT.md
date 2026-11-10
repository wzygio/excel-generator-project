# Project Context

## Purpose

构建面向 OLED 半导体显示屏制造的数据处理、报表自动化与共享工具工作区。

## Operating Model

- This is a Python workspace managed with `uv`.
- Project-specific application and domain packages live under `src/`, separate from `src/shared_kernel/`.
- Reusable infrastructure, interfaces, and utilities live under `src/shared_kernel/`.
- Project modules may depend on `shared_kernel`; `shared_kernel` must not depend on project-specific OLED workflows.
- When a UI exists, keep presentation concerns outside domain and reusable infrastructure modules.
- Rebuildable runtime outputs belong under `output/` and are not source-of-truth project knowledge.

## Hard Boundaries

- Preserve public behavior when consolidating or refactoring `shared_kernel`; compatibility changes require explicit acceptance criteria and regression tests.
- Keep secrets and environment-specific credentials out of source code, logs, generated documentation, and committed artifacts.
- Treat code, executable tests, approved ADRs, and user-maintained specifications as evidence; do not describe planned capabilities as implemented.
- Keep reusable infrastructure independent from project-specific OLED concepts.

## Fast Routing

- DDD Python project-type instructions: `AGENTS.md` (shared by NTFS hard links)
- Project-specific instructions and task routes: this `CONTEXT.md`
- Architecture and module boundaries: `ARCHITECTURE.md`
- Harness and reusable knowledge routes: `references/index.md`
- Domain vocabulary and design knowledge: `references/design_references/`
- Coding rules and restrictions: `references/dev_references/`
- Validation, diagnostics, and observability guidance: `references/test_references/`
- Local Markdown issues and triage history: `.scratch/`
- Active file-based plans and checklists: `.planning/`
- Durable architectural decisions: `docs/ADR/`
- Development prompts and retained engineering guidance: `docs/dev_docs/`

## Project Agent Rules

This CONTEXT owns this project's specific instructions, constraints and task
triggers. The global AGENTS owns user-wide operating/safety rules; this project's
AGENTS owns the shared DDD Python workflow. Update the appropriate owner and any
affected routes together. This user-requested ownership model takes precedence
over earlier template descriptions of where project instructions belong.

- Retain the recorded Harness label `agent-workflow-v1`; changes to it require an
  explicit reconciliation. This project's report flow uses Spec / Skill / Runtime
  boundaries and preserves source Excel workbooks under `resources/`.
- Requirements/design work uses `.scratch/`, `docs/PRD/` and
  `references/design_references/`; execution plans use `.planning/`.
- Development and validation knowledge uses `references/dev_references/` and
  `references/test_references/`; durable decisions and delivery knowledge use
  `docs/ADR/` and `references/summary_references/`. Retain historical material in
  `references/plan_references/`; direct new knowledge through the maintained routes.
- User-maintainable task specs and runtime traces use `specs/`. Generated reports,
  downloads, `specs/runs/`, caches, browser artifacts and decrypted resources remain
  outside commits; maintained inputs retain their own lifecycle.
- Keep project indexes folder-only. Update development/test references as their
  contracts change and `references/retrospective.md` as durable artifact routing changes.
  Follow `docs/agents/domain.md` for the single-context model and `docs/ADR/` decisions.

- For local Markdown issues and PRDs, follow `docs/agents/issue-tracker.md`.
- For issue state changes, follow `docs/agents/triage-labels.md`, including its
  configured canonical role/status vocabulary rather than inventing new states.
- Before domain behavior/documentation changes, follow `docs/agents/domain.md`.
