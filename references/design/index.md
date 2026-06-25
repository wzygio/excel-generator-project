# Design Index

Use this folder as the entrypoint for project design knowledge.

## Folder Routes

| Folder | When To Read | Read Guidance | Commands |
|---|---|---|---|
| `references/design/system_design/` | System shape, rules boundary, Agent/Skill/Spec contracts, or cross-layer flow changes. | Read the child index, then the matching system or contract documents. | Use CodeGraph for flow checks; run Agent/Skill tests when contracts change. |
| `references/design/module_design/` | Domain modules, shared kernel behavior, or module ownership changes. | Read the child index, then module notes relevant to the touched code. | Run focused unit tests for the changed module and `uv run pyright` for shared types. |
| `references/design/feat_design/` | Feature-level behavior, Spec builder flow, or workflow-specific decisions change. | Read the child index, then the relevant feature design notes. | Run focused feature tests and the smallest matching smoke path. |

## Update Rule

Add or update design folders when module responsibilities, public contracts, data flow, or product rules change. Keep detailed business rules out of the root router.
