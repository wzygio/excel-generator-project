# Task Plan: Daily Report Wrapper and Configuration Refactor

## Goal
Make the project-local `daily_report` skill a thin Agent wrapper over the public `daily-report-generator` CLI, remove project-owned duplication of daily-report business logic, and relocate remaining hard-coded Agent configuration into validated Pydantic-backed configuration at the correct project boundary.

## Current Phase
Complete

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
- [x] Replace local daily-report generation logic with delegation to the public CLI.
- [x] Move Agent-owned configuration to the correct configuration/reference location and load it through Pydantic.
- [x] Remove or isolate duplicated business logic and scattered literals without disturbing unrelated user changes.
- [x] Update affected architecture/design/development references.
- **Status:** complete

### Phase 4: Tests and Verification
- [x] Add or update focused tests for wrapper command construction, config validation, and caller behavior.
- [x] Run targeted tests, lint/type checks where configured, and relevant smoke verification.
- [x] Search again for prohibited hard-coded business values and inspect the final diff.
- **Status:** complete

### Phase 5: Handoff
- [x] Record final ownership decisions, changed files, validation evidence, and any residual risks.
- [x] Mark all planning artifacts complete.
- **Status:** complete

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
| Focused tests retained one obsolete assertion that fixed-flow `daily_report` receives `sections`. | 1 | Updated the test to assert the new minimal public-wrapper payload; production behavior is intentional. |
| The same SpecBuilder test had a second obsolete `analysis_results` assertion immediately after the first. | 2 | Removed the remaining legacy assertion and kept one exact-payload assertion. |
| Parallel verification used an expected no-match `rg` command whose exit code 1 rejected the combined tool call and hid pytest output. | 1 | Check for any surviving pytest process, then rerun sequentially with explicit no-match handling. |
| Direct Pyright invocation did not discover the workspace virtual environment and reported only missing third-party imports. | 1 | Rerun with `--pythonpath .venv\\Scripts\\python.exe`; treat environment-resolution failures separately from source type errors. |
| Pyright still reported the identical missing imports with explicit `--pythonpath`. | 2 | Inspect supported CLI/environment configuration and use a different venv-resolution mechanism for the third attempt. |
| A combined Pyright-help/config search named optional config files that do not exist, causing `rg` exit 2 and hiding help output. | 1 | The useful result showed `[tool.pyright]` has `venv` but no `venvPath`; apply the focused configuration fix directly. |
| A later parallel legacy-runner audit again paired a potentially no-match `rg` with a file read, repeating the rejected-call pattern. | 2 | Stop parallelizing no-match searches; run the file read and normalized-exit search sequentially. |
| Ruff found one import-order issue after adding `ConfigLoader` to the Streamlit app. | 1 | Apply Ruff's mechanical import fix, then rerun the focused app checks. |
| Guessed `tests/unit/test_local_file_loader.py`, which does not exist. | 1 | Locate loader coverage by symbol search before adding/updating tests. |
| The first LocalFileLoader refactor patch mismatched escaped backslashes in the module docstring. | 1 | Leave the docstring out of the structural patch and apply smaller exact regions. |
| A follow-up cosmetic loader-docstring patch hit the same escaped-path mismatch. | 2 | Stop editing that non-executable historical description; the constants and runtime path ownership are already removed. |
| Full unit run exposed eager SpecBuilder source validation in a non-fixed LLM flow. | 1 | Resolve configured source paths lazily only in rule-built workflows that consume them. |
| Black-box data analysis still lost source metadata after changing the process working directory. | 2 | Make the default `ConfigLoader` directory project-root-relative instead of current-working-directory-relative. |
| Root architecture boundary used a third-level source path and failed the shallow-map Harness rule. | 1 | Refer to the `daily_report` facade by component name without embedding a deep project path. |
| Harness tests also fail on the user's pre-existing reference-tree deletion/reorganization. | 1 | Do not recreate or revert unrelated reference directories; report this independent baseline failure after fixing task-owned checks. |
| A combined planning/config patch contained an empty hunk separator. | 1 | Split the exact planning and source patches without an empty hunk. |
| The first config-loader regression patch guessed the test method name. | 1 | Located the exact module-singleton test and inserted the CWD regression beside it. |
| Appending another shell expression after PowerShell stop-parsing caused the planning checker to receive malformed trailing arguments and report no plan. | 1 | Rerun the previously successful checker command alone; keep diff checking separate. |

## Notes
- The previously active plan `2026-07-06-nanobot-runtime-analysis` is complete and unrelated.
- Do not edit the public skill unless inspection proves its documented CLI is missing a required stable contract; this task primarily changes the project-local wrapper.
- Preserve user-provided Excel/source files and unrelated working-tree changes.
