# Task Plan: Daily Report Wrapper and Configuration Refactor

## Goal
Make the project-local `daily_report` skill a thin Agent wrapper over the public `daily-report-generator` CLI, remove project-owned duplication of daily-report business logic, and relocate remaining hard-coded Agent configuration into validated Pydantic-backed configuration at the correct project boundary.

## Current Phase
Phase 3

## Phases

### Phase 1: Project and Contract Discovery
- [x] Read the project architecture, Harness routing, coding conventions, restrictions, and relevant design/test references.
- [x] Inspect the local `daily_report` skill and its callers; reconcile stale prior CodeGraph notes with the current on-disk tree.
- [x] Inspect the public `daily-report-generator` CLI contract and identify the supported invocation boundary.
- [x] Inventory occurrences of `V3CT修正良率及不良率By月周天报表` and related hard-coded values.
- **Status:** complete

### Phase 2: Ownership and Refactor Design
- [x] Classify each hard-coded value as public-skill business logic, Agent runtime configuration, or unrelated project configuration.
- [x] Define the smallest wrapper contract and Pydantic configuration model compatible with existing callers.
- [x] Identify documentation, tests, and architecture references that must change.
- **Status:** complete

### Phase 3: Implementation
- [ ] Replace local daily-report generation logic with delegation to the public CLI.
- [ ] Move Agent-owned configuration to the correct configuration/reference location and load it through Pydantic.
- [ ] Remove or isolate duplicated business logic and scattered literals without disturbing unrelated user changes.
- [ ] Update affected architecture/design/development references.
- **Status:** in_progress

### Phase 4: Tests and Verification
- [ ] Add or update focused tests for wrapper command construction, config validation, and caller behavior.
- [ ] Run targeted tests, lint/type checks where configured, and relevant smoke verification.
- [ ] Search again for prohibited hard-coded business values and inspect the final diff.
- **Status:** pending

### Phase 5: Handoff
- [ ] Record final ownership decisions, changed files, validation evidence, and any residual risks.
- [ ] Mark all planning artifacts complete.
- **Status:** pending

## Key Decisions
| Decision | Rationale |
|---|---|
| The public skill owns Mod0-Mod4 orchestration, business values, and report generation. | This follows the explicit `daily-report-generator` Runtime Contract and the user's required architecture. |
| The local skill may keep only Agent-facing adaptation and validated project configuration. | The project is an Agent runtime; it needs a stable invocation boundary but must not duplicate report business logic. |
| Skip CodeGraph for the current worktree and use exact text/source inspection. | The repository policy says to skip CodeGraph when `.codegraph/` is absent; it is currently absent. |

## Errors Encountered
| Error | Attempt | Resolution |
|---|---:|---|
| Nested PowerShell variables were expanded by the outer shell before execution. | 1 | Stopped using the interpolated command form. |
| `rtk` argument forwarding removed quotes from a second nested PowerShell read command. | 2 | Switched Markdown reads to `rtk rg`; no project files were changed by either failure. |
| CodeGraph could not resolve `_resolve_generator_root` or `_run_generator_cli` even though current source from `run_native_daily_report` calls them. | 1 | Treat the graph as partially stale for this edited file and inspect the on-disk file directly after the required CodeGraph-first attempt. |
| A planning-document patch did not match the current `findings.md` context. | 1 | Re-read the active planning files and applied a narrower exact patch. |
| A parallel `rg` search returned exit code 1 for no matches and suppressed the other result. | 1 | Recorded the no-match as evidence and reran the independent read separately. |
| Guessed `tests/unit/test_agent_spec_builder_fixed_flows.py`, which does not exist. | 1 | Use `rg --files` to discover exact test names and rerun only valid paths. |
| Two attempts to read a line range through nested `rtk proxy powershell` lost quoting/variables. | 1-2 | Used PowerShell stop-parsing (`--%`) so the complete skill instructions could be read without repeating the failing quoting forms. |
| A combined planning-file patch referenced a decision row in the wrong file. | 1 | Located the exact rows with `rg` and split the correction into exact-file patches. |
| `uv run` could not read the user-level uv cache under the managed filesystem profile. | 1 | Use the repository's existing `.venv\\Scripts\\python.exe` and `.venv\\Scripts\\pytest.exe` directly for validation. |
| The first broad `SpecBuilder` patch assumed a one-line `_normalize_sections` implementation. | 1 | Located exact contexts with `rg` and split the refactor into smaller patches. |

## Notes
- The previously active plan `2026-07-06-nanobot-runtime-analysis` is complete and unrelated.
- Do not edit the public skill unless inspection proves its documented CLI is missing a required stable contract; this task primarily changes the project-local wrapper.
- Preserve user-provided Excel/source files and unrelated working-tree changes.
