# System Design Index

## Folder Routes

| Folder | When To Read | Read Guidance | Commands |
|---|---|---|---|
| `references/design/system_design/agent/` | Agent Runtime, Skill, Spec, tool registry, trace, or workflow contract changes. | Read the child index, then the contract documents needed for the changed boundary. | Run `uv run pytest tests/unit/agent tests/unit/skills -v --tb=short`. |

## Local Documents

| Document | When To Read | Commands |
|---|---|---|
| `rules_boundary.md` | Deciding whether a rule belongs in specs/templates, references, or Python code. | No default command; verify the chosen owner with focused tests or spec validation. |

## Update Rule

Use this area for cross-module rules, runtime contracts, system boundaries, and architecture decisions.
