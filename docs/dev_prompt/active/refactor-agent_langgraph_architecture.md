# Refactor Plan: Agent + LangGraph Architecture

Status: implemented; awaiting user acceptance before moving to `completed/`
Created: 2026-06-24
Source request: `docs/prompt/refactor-project_arch.md`
Primary local reference: `D:\wzy\Visionox-Docs_Backup\dev-docs\agent_dev\agent-LangGraph.md`

## Goal

Bring `yield_report` to a standard enterprise Agent architecture aligned with LangGraph while preserving the existing Spec / Skill / Runtime contracts and report behavior.

The target runtime chain remains:

```text
User goal
  -> LangGraph Spec sub-agent / fixed-flow rule builder
  -> TaskSpec
  -> RuntimeRouter
  -> Letta or fixed-flow Python runtime
  -> Skill tools
  -> SkillResult / trace / memory / artifacts
```

## Research Baseline

Relevant guidance:

- Local LangGraph reference section 4 recommends splitting LangGraph code into state, nodes, edges, graph assembly, checkpointer, agents, tools, services, API, specs, and tests.
- LangGraph official docs model graph workflows around State, Nodes, and Edges.
- LangGraph production structure expects one or more graphs, graph configuration, dependency declaration, and environment boundaries.
- LangGraph persistence guidance separates checkpointers for thread-scoped graph state from stores for durable cross-thread memory.
- LangGraph testing guidance recommends direct node tests, graph tests, and checkpointer-backed partial execution tests.

## Current State Assessment

Already aligned:

- `src/yield_report/agent/spec_model.py` owns `TaskSpec`, `SkillCall`, `RunContext`, `SkillResult`, artifacts, errors, and memory candidates.
- `src/yield_report/skills/` already uses vertical capability slices: `report_download`, `data_analysis`, `daily_report`, `anomaly_monitor`.
- `src/yield_report/agent/runtime.py` executes Skill workflow steps and writes trace, summary, artifacts, and memory candidates.
- `src/yield_report/agent/runtime_adapter.py` routes runtime execution and keeps fixed-flow Python exemptions narrow.
- `src/yield_report/agent/client_tools.py` exposes a typed Letta client-tool registry.
- `src/yield_report/agent/langgraph_spec_agent.py` already uses LangGraph `StateGraph` for Spec draft/validate/repair/finalize.

Gaps:

- LangGraph Spec agent is monolithic rather than split into `state`, `nodes`, `edges`, `graph`, and checkpointer modules.
- `SpecBuilder` uses LangGraph indirectly, but individual graph nodes and graph assembly lack focused unit tests.
- `docs/agent/architecture.md` still contains older guidance saying not to introduce LangGraph, while `docs/agent/spec_contract.md` now makes LangGraph Spec construction the default path.
- `application/`, `core/`, and `infrastructure/` remain as compatibility implementation layers. They should not be deleted in this refactor; Skills should continue wrapping them until each capability can be safely absorbed into adapters/services.
- `docs/plans/index.md` is referenced by AGENTS but is absent; the existing plan entrypoint is `docs/exec-plans/index.md`.

## Target Architecture

```text
src/yield_report/
├── agent/
│   ├── spec_model.py              # Stable Agent/Skill contracts
│   ├── spec_builder.py            # Facade: fixed-flow rule builder vs LangGraph Spec graph
│   ├── spec_graph/                # LangGraph Spec sub-agent
│   │   ├── state.py               # Graph state/result/dependency types
│   │   ├── nodes.py               # load_context/draft/parse_validate/repair/finalize
│   │   ├── edges.py               # routing decisions
│   │   ├── graph.py               # StateGraph assembly and compile helper
│   │   ├── checkpointer.py        # optional graph checkpointer factory
│   │   └── agent.py               # LangGraphSpecAgent facade
│   ├── runtime.py                 # Deterministic Skill runtime
│   ├── runtime_adapter.py         # Letta-first runtime routing plus fixed-flow exemptions
│   ├── letta_runtime.py           # Stateful Agent runtime adapter
│   ├── client_tools.py            # Approved runtime tool registry
│   ├── registry.py                # Python Skill registry
│   ├── run_store.py               # specs/runs ownership
│   ├── trace.py                   # trace writer
│   └── memory.py                  # memory facade
├── skills/                        # Vertical business capabilities
├── application/                   # Compatibility orchestration layer
├── core/                          # Compatibility pure-domain helpers
└── infrastructure/                # Compatibility IO/adapters
```

## Refactor Scope

This is not just file movement.

Required changes:

- Move LangGraph-specific Spec construction into a graph package.
- Preserve compatibility imports for existing callers.
- Update `SpecBuilder` to import the canonical graph facade.
- Add direct graph/node tests.
- Update docs so the LangGraph target architecture and current implementation agree.
- Keep existing public request/result contracts stable unless tests prove a contract bug.

Not in this slice:

- Deleting `application/`, `core/`, or `infrastructure/`.
- Rewriting business Skill implementations.
- Replacing Letta with LangGraph for full runtime execution.
- Adding new dependencies.

## Execution Phases

| Phase | Status | Work | Verification |
|---|---|---|---|
| 1 | complete | Create `agent/spec_graph/` and move graph responsibilities into state/nodes/edges/graph/checkpointer/agent modules. | New focused unit tests passed. |
| 2 | complete | Keep `langgraph_spec_agent.py` as a compatibility wrapper and update `SpecBuilder` to the canonical path. | Existing `test_spec_builder.py` passed. |
| 3 | complete | Update architecture/design docs to reflect LangGraph as the default Spec builder and the new package map. | Diff inspected and paths verified by tests/imports. |
| 4 | complete | Run focused Agent/Skill tests and fix regressions. | `uv run pytest tests/unit/agent tests/unit/skills -q --tb=short` passed. |
| 5 | complete | Run lint/typing checks if touched surface warrants it. | `uv run ruff check ...` passed; pyright not run because no broad typing contract change was made. |

## Final Checklist

- [x] LangGraph Spec construction is organized under `src/yield_report/agent/spec_graph/`.
- [x] Graph state, nodes, edges, graph assembly, and checkpointer concerns are separated.
- [x] `SpecBuilder` uses the canonical `spec_graph` facade.
- [x] Existing `yield_report.agent.langgraph_spec_agent` import path remains compatible.
- [x] Direct graph/node tests cover successful build and repair behavior.
- [x] Existing SpecBuilder tests still pass.
- [x] Agent/Skill unit tests pass.
- [x] Docs no longer contradict the current LangGraph default Spec-builder policy.
- [x] Planning files record research, decisions, errors, and verification.

## Verification Results

| Command | Result |
|---|---|
| `uv run pytest tests/unit/agent/test_spec_graph.py -q --tb=short` | 3 passed |
| `uv run pytest tests/unit/agent/test_spec_builder.py tests/unit/agent/test_anomaly_monitor_spec.py -q --tb=short` | 14 passed |
| `uv run pytest tests/unit/agent tests/unit/skills -q --tb=short` | 113 passed |
| `uv run ruff check src/yield_report/agent/spec_builder.py src/yield_report/agent/langgraph_spec_agent.py src/yield_report/agent/spec_graph tests/unit/agent/test_spec_graph.py` | passed |
