# Task18 Letta Runtime Refactor Plan

Goal: Implement the active execution plan in `docs/exec-plans/active/refactor-letta_agent_runtime.md` and verify the refactored Agent can execute the black-box task: `请分析M678最近三个月的月度良率变化趋势；如果有恶化，请给出恶化原因`.

## Phases

| Phase | Status | Objective | Evidence |
| --- | --- | --- | --- |
| 1 | completed | Restore project context and identify public interfaces for TDD | codegraph/source reads, plan reads |
| 2 | completed | RED/GREEN: explicit `runtime=letta` routes through LettaRuntime without touching OMP/Python paths | `tests/unit/agent/test_letta_runtime.py` |
| 3 | completed | RED/GREEN: Letta client-side tool loop dispatches project Skills and returns `SkillResult` | `tests/unit/agent/test_letta_runtime.py` |
| 4 | completed | Add dependency/config/docs wiring needed by the adapter | config tests, CLI test, dependency lock |
| 5 | completed | Run focused agent/skill tests plus lint/type checks as feasible | 67 relevant tests pass; touched-file ruff and pyright pass; full pyright has unrelated existing debt |
| 6 | blocked | Execute the M678 three-month monthly yield trend black-box task through refactored runtime | blocked by missing Letta Cloud/local server connection; local deployment report written to `docs/generated/letta_local_deployment_assessment_2026-06-22.md` |

## TDD Rules

- Use public interfaces: `RuntimeRouter.run_spec`, `LettaRuntime.run_spec`, `scripts/run_task_spec.py` where possible.
- Add one behavior test at a time, then implement the minimal code to pass.
- Keep OMP as explicit fallback; do not delete current code.
- Preserve `RunStore`, `TraceWriter`, `SkillResult`, `memory_candidates.json`, and `run_summary.json` contracts.

## Decisions

- User has already asked to follow the active plan, so implementation may proceed without another approval checkpoint.
- If real Letta credentials/server are unavailable, unit/integration code can be completed, but the goal cannot be marked complete until the black-box runtime execution is proven.

## Errors Encountered

| Error | Attempt | Resolution |
| --- | --- | --- |
| `tdd` skill not found under `.codex/skills` | Read wrong skill root first | Re-read from user-provided `.agents/skills/tdd/SKILL.md` |
| `uv run pyright` not found | Validation command from AGENTS.md | Added `pyright` to the dev extra; touched production/test files pass pyright |
| Local Letta server not deployable in current environment | Checked Docker and WSL status | Hardware is sufficient, but Docker CLI is absent and no usable WSL distro is configured; user/admin must install WSL2 + Docker Desktop before starting Docker/Postgres Letta |
