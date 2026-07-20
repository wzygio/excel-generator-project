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

- Agent operating rules: `AGENTS.md`
- Architecture and module boundaries: `ARCHITECTURE.md`
- Harness and reusable knowledge routes: `references/index.md`
- Domain vocabulary and design knowledge: `references/design_references/`
- Coding rules and restrictions: `references/dev_references/`
- Validation, diagnostics, and observability guidance: `references/test_references/`
- Local Markdown issues and triage history: `.scratch/`
- Active file-based plans and checklists: `.planning/`
- Durable architectural decisions: `docs/ADR/`
- Development prompts and retained engineering guidance: `docs/dev_docs/`
