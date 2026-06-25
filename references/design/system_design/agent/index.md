# Agent System Design Index

## Folder Routes

No child folders yet.

## Read Guidance

| Document | When To Read | Commands |
|---|---|---|
| `spec_contract.md` | TaskSpec fields, SpecBuilder behavior, workflow contracts, or run-spec execution changes. | Run focused Agent/Spec tests and any affected workflow tests. |
| `skill_contract.md` | Skill request/result/error/artifact contracts or Skill implementation boundaries change. | Run `uv run pytest tests/unit/skills -v --tb=short`. |
| `design-agent_skill_boundary.md` | Deciding whether behavior belongs in Agent orchestration, Skill implementation, or Runtime adapters. | Run both Agent and Skill focused tests for boundary changes. |

## Update Rule

Keep Agent, Skill, Spec, and runtime boundary contracts in this folder.
