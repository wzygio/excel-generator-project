# Harness Reference Index

Use this folder as the project Harness knowledge base. Keep the folder routes stable and load details only through the target folder's index.

## Folder Routes

| Folder | When To Read | Read Guidance | Commands |
|---|---|---|---|
| `references/project-info/` | Project background, source-of-truth, ownership, glossary, or durable context is needed. | Read the folder index, then the stable background documents named there. | Usually no command; verify paths with `git status --short` when moving docs. |
| `references/project-conf/` | Configuration, environment, dependency, or non-secret setup behavior changes. | Read the folder index, then any config explanation documents it names. | Run `uv sync`, `uv run pyright`, or targeted config tests when config behavior changes. |
| `references/design/` | Architecture, Agent, Skill, Spec, module, feature, or rules-boundary decisions change. | Read the relevant child folder index before reading design documents. | Use CodeGraph for code flow, then run focused unit tests for touched contracts. |
| `references/exec-plans/` | Long-lived execution-plan conventions or cross-plan indexes are needed. | Read the folder index before creating or moving execution plans. | No default command; inspect diffs and verify referenced plan folders exist. |
| `references/plans/` | Active/completed plan routing or planning conventions are needed. | Read the child folder index for active or completed planning material. | Use the active `.planning` files for current work; inspect with `git status --short`. |
| `references/dev_references/` | Coding rules, restrictions, schemas, templates, or implementation guidance is needed. | Read the target child index, then only the rule/schema/template documents relevant to the current change. | Run `uv run ruff check .`, `uv run pyright`, or focused tests when rules affect code. |
| `references/generated/` | Agent-generated audits, scans, cleanup notes, or reflect outputs are needed. | Read the index first; load generated artifacts only when they are directly relevant. | Regenerate with the documented tool, then inspect the diff. |
| `references/test_references/` | Verification, smoke, observability, debugging, or test-command choices are needed. | Read observability and the relevant child index before choosing commands. | Run the smallest relevant pytest/ruff/pyright/harness/smoke command. |
