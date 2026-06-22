# Progress Log: Anomaly Monitor Development

## Session: 2026-06-22 Task3 Merge

### Task3: Merge Anomaly Monitor Into Runtime-Refactor Mainline
- **Status:** complete
- Actions taken:
  - Confirmed there is no local `master` branch; the runtime-refactor mainline in this repository is `codex/refactor` at `abc0ae6`.
  - Created backup branch `codex/feat-anomaly-monitor-task1-2-pre-task3` before applying the merge.
  - Stashed the dirty anomaly-monitor worktree, fast-forwarded `codex/feat-anomaly-monitor-task1-2` to `codex/refactor`, then replayed anomaly-monitor changes.
  - Resolved conflicts by keeping the refactor/Letta Runtime kernel and integrating only the anomaly-monitor skill registration, SpecBuilder routing, legacy bridge allowlist, and Workbench UI affordance.
  - Added ASCII keyword support for `anomaly_monitor` goals after a Runtime bridge smoke exposed PowerShell Chinese stdin mojibake.
  - Verified Runtime path through `scripts/agent_workbench_bridge.py`: `run-20260622-170733` executed `anomaly_monitor` with Python runtime and produced HL 1 / true anomaly 1.
  - Verified browser Playwright smoke on `http://127.0.0.1:3101`: fixed “异常监控” button completed, showed HL 1 / 真实异常 1, listed two artifacts, and had no console errors or failed requests.
- Verification:
  - `uv run pytest tests/unit/agent/test_anomaly_monitor_spec.py tests/unit/skills/test_anomaly_monitor_skill.py -v --tb=short` -> 17 passed.
  - `uv run pytest tests/unit/agent tests/unit/skills -v --tb=short` -> 93 passed.
  - `uv run ruff check <touched backend paths>` -> passed.
  - `uv run pyright <touched backend paths>` -> 0 errors.
  - `npm run typecheck` -> passed.
  - `$env:DEEPSEEK_API_KEY='codex-build-placeholder'; npm run build` -> passed, with existing Turbopack NFT tracing warning on `app/api/yield-skill/route.ts`.

## Session: 2026-06-15

### Task2-fix: HL Noise Reduction
- **Status:** in_progress
- Actions taken:
  - Analyzed `output/anomaly_monitor_smoke/anomaly_monitor_result.json`: initial smoke had 423 HL rows.
  - Added TDD coverage for dynamic concentration top-unit ratio.
  - Tightened concentration to Top1 50% and Top 20% units cumulative 80%; focused concentration tests pass.
  - Re-ran smoke for `M626,C550,M756,M673,C522`: HL dropped to 328 but still exceeds target.
  - Split remaining HL: 304 non-CT rows and 24 CT rows, pointing to station filtering and mwdl candidate over-expansion.
  - Added tests for mwdl DAY-summary requirement, mwdl per product/defect/station dedupe, CT-only final HL, and CT-only notice draft station rendering.
  - Implemented mwdl candidate narrowing and CT-only verdict gating.
  - Updated notice drafts to render the final verdict station instead of `occurrence_station`.
  - Re-ran `output/anomaly_monitor_smoke`: total 248, HL 15, skipped 233, blocked 0, true anomaly 15, station over spec 0.
  - Verified markdown has 15 HL draft headings and all 15 `发生站点` lines are CT.
  - Verification passed: `uv run pytest tests/unit/agent tests/unit/skills -q` -> 53 passed.
  - Verification passed: focused `uv run ruff check ...` -> all checks passed.
  - Type check note: `uvx pyright --venvpath . ...` still reports pandas/openpyxl static typing noise in `sources.py` and test workbook setup; runtime tests and smoke are green.
- **Status:** complete

### Task1: HL Logic Optimization
- **Status:** complete
- Actions taken:
  - Confirmed the target rows are present in current source data: `M756 屏体异物(黑白点/凹点)`, `C546&C547 S向亮线`, and `C530 S向亮线`.
  - Fixed combined product filtering so `C546&C547` survives Spotfire product selection.
  - Added source-HL final selection: one strongest CT `hl_data` candidate per product.
  - Added mild MAP concentration text for selected source candidates, using valid-output panel MAP distribution.
  - Re-ran `output/anomaly_monitor_smoke`: total 611, HL 26, skipped 585, blocked 0.
  - Completion audit confirmed all three target anomalies are HL in JSON and present in markdown; M756 shows `MAP较集中: 1FE0/2FE0`.
  - Verification passed: `uv run pytest tests/unit/agent tests/unit/skills -q` -> 56 passed.
  - Verification passed: focused `uv run ruff check ...` -> all checks passed.

### Phase 1: Context And TDD Setup
- **Status:** complete
- Actions taken:
  - Created new worktree `D:\wzy\Python\excel-generator-project-anomaly-monitor`.
  - Created branch `codex/feat-anomaly-monitor-task1-2`.
  - Created implementation planning files and set active plan.
  - Inspected runtime registry, SpecBuilder, Spec validation, existing Skill tests, and Workbench page.
  - Added failing anomaly-monitor Skill and SpecBuilder tests.
- Files created/modified:
  - `.planning/.active_plan`
  - `.planning/task17_anomaly_monitor_dev/task_plan.md`
  - `.planning/task17_anomaly_monitor_dev/findings.md`
  - `.planning/task17_anomaly_monitor_dev/progress.md`

## Test Results
| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| Worktree bootstrap | `git worktree add -b codex/feat-anomaly-monitor-task1-2` | Clean isolated worktree | Created successfully | Pass |
| Red focused tests | `uv run pytest tests/unit/skills/test_anomaly_monitor_skill.py tests/unit/agent/test_anomaly_monitor_spec.py -v --tb=short` | Fail before implementation | Failed on missing `yield_report.skills.anomaly_monitor` | Pass |
| Focused anomaly tests | same command after implementation | All focused tests pass | 6 passed | Pass |

### Phase 2: Backend Skill Implementation
- **Status:** complete
- Actions taken:
  - Added shared Excel reader for standard/COM-readable workbooks.
  - Added `anomaly_monitor` Skill package with models, source loading, deterministic analyzers, notice templates, implementation, tool entrypoint, and SKILL.md.
  - Registered `anomaly_monitor` in the default runtime.
  - Extended SpecBuilder with anomaly-monitor goal detection and TaskSpec generation.
- Files created/modified:
  - `src/yield_report/infrastructure/excel_reader.py`
  - `src/yield_report/skills/anomaly_monitor/*`
  - `src/yield_report/agent/registry.py`
  - `src/yield_report/agent/spec_builder.py`
  - `tests/unit/skills/test_anomaly_monitor_skill.py`
  - `tests/unit/agent/test_anomaly_monitor_spec.py`

### Phase 3: UI Integration
- **Status:** complete
- Actions taken:
  - Added `anomaly_monitor` module to the Workbench module selector, suggestions, Copilot tool enum, default workflow steps, result details, and source cards.
- Files created/modified:
  - `ui/copilotkit-agent/app/page.tsx`

## Verification Loop
| Phase | Command | Result | Notes |
|-------|---------|--------|-------|
| Red | `uv run pytest tests/unit/skills/test_anomaly_monitor_skill.py tests/unit/agent/test_anomaly_monitor_spec.py -v --tb=short` | Failed as expected | Missing `yield_report.skills.anomaly_monitor` before implementation. |
| Green | `uv run pytest tests/unit/skills/test_anomaly_monitor_skill.py tests/unit/agent/test_anomaly_monitor_spec.py -v --tb=short` | 6 passed | Covers ratio parsing, HL detection, artifacts, missing input, side-effect gates, SpecBuilder, runtime registration. |
| Regression | `uv run pytest tests/unit/agent tests/unit/skills -v --tb=short` | 46 passed | Agent and Skill suite remains green. |
| Lint | `uv run ruff check src/yield_report/infrastructure/excel_reader.py src/yield_report/skills/anomaly_monitor src/yield_report/agent/registry.py src/yield_report/agent/spec_builder.py tests/unit/skills/test_anomaly_monitor_skill.py tests/unit/agent/test_anomaly_monitor_spec.py` | Passed | Full `ruff check .` still has existing repository lint debt outside this task. |
| Type | `uvx pyright --venvpath . <touched backend paths>` | Passed | `uv run pyright` is unavailable because `pyright` is not installed in the project env. |
| UI Type | `npm run typecheck` | Passed | Required `npm ci` first because this isolated worktree had no `node_modules`. |
| UI Build | `$env:DEEPSEEK_API_KEY='codex-build-placeholder'; npm run build` | Passed | Build without the env var fails at `/api/copilotkit`, as expected. Turbopack still reports an existing NFT tracing warning. |
| UI Smoke | Browser at `http://127.0.0.1:3100` | Passed | Anomaly tab rendered, switched to "真实异常识别", showed "识别异常", and browser console had no errors. |

### Phase 4: Verification Loop
- **Status:** complete
- Notes:
  - `npm ci` completed and reported 13 low/moderate dependency audit findings in the existing dependency tree.
  - Local dev server remains available for manual UI review at `http://127.0.0.1:3100` with a placeholder API key.

### Phase 5: Final Review
- **Status:** complete
- Actions taken:
  - Removed the incidental `next-env.d.ts` dev-build path change from the final diff.
  - Inspected `git status` and diff summary for unintended tracked changes.

### Task2: Fixed Workflow One-Click Buttons
- **Status:** complete
- Actions taken:
  - Added a `FIXED_WORKFLOWS` UI configuration for daily report generation and anomaly monitoring.
  - Replaced the single sidebar "全自动日报" action with two fixed one-click buttons.
  - Made fixed workflow execution use deterministic goal text instead of whatever query was left in the composer.
  - Allowed fixed workflow modules to execute without manual composer input.
  - Added `anomaly_monitor` to the legacy `/api/yield-skill` module allowlist and `copilotkit_skill_bridge.py`.
  - Adjusted segmented-control and sidebar button CSS for four modules and multiple fixed workflow buttons.

## Task2 Verification
| Phase | Command | Result | Notes |
|-------|---------|--------|-------|
| Lint | `uv run ruff check scripts/copilotkit_skill_bridge.py src/yield_report/infrastructure/excel_reader.py src/yield_report/skills/anomaly_monitor src/yield_report/agent/registry.py src/yield_report/agent/spec_builder.py tests/unit/skills/test_anomaly_monitor_skill.py tests/unit/agent/test_anomaly_monitor_spec.py` | Passed | Focused on touched Python paths and existing Task1-2 backend paths. |
| Type | `uvx pyright --venvpath . <touched backend paths>` | Passed | `uv run pyright` is still unavailable in the project env. |
| Regression | `uv run pytest tests/unit/skills/test_anomaly_monitor_skill.py tests/unit/agent/test_anomaly_monitor_spec.py -v --tb=short` | 6 passed | Rechecked anomaly monitor behavior after bridge update. |
| Regression | `uv run pytest tests/unit/agent tests/unit/skills -v --tb=short` | 46 passed | Agent and Skill suite remains green. |
| UI Type | `npm run typecheck` | Passed | Covers page and API route TypeScript changes. |
| UI Build | `$env:DEEPSEEK_API_KEY='codex-build-placeholder'; npm run build` | Passed | Existing Turbopack NFT tracing warning remains. |
| UI Smoke | Browser at `http://127.0.0.1:3100` | Passed | Both one-click buttons rendered; clicking "一键异常监控" set the fixed goal, switched to anomaly monitor, and reached `/api/agent-runs` with no console errors. |

### Task2 Follow-Up: Data Source And Business Flow Correction
- **Status:** complete
- Actions taken:
  - Read the encrypted rule workbook through `fr_file_decryption` from `docs/dev_docs/屏体大数据科-良率监控智能体需求梳理.xlsx`.
  - Replaced anomaly-monitor SpecBuilder defaults that pointed to missing `resources/anomaly_monitor/*` files.
  - Added CT anomaly workbook normalization into canonical daily candidates.
  - Added requested-date filtering with latest-available-date fallback.
  - Fixed date parsing in source loading and rule analysis.
  - Prevented same-source CT rows from being treated as already-HL matches.
  - Re-aligned `true_anomaly` and `real_anomalies` to the rule workbook output `HL异常数据`.
  - Added UI result counts for total, HL, true anomaly, key-station over-spec, skipped, and blocked.
  - Deduplicated merged Agent/Skill warnings to avoid repeated UI warnings.

## Task2 Follow-Up Verification
| Phase | Command | Result | Notes |
|-------|---------|--------|-------|
| Red | `uv run pytest tests/unit/skills/test_anomaly_monitor_skill.py::test_anomaly_monitor_derives_candidates_from_ct_exception_source -v --tb=short` | Failed as expected | Exposed historical rows leaking into latest-date candidates, then same CT row matching itself as already-HL. |
| Green | same focused test after fixes | Passed | CT workbook fallback now derives latest-date candidates and skips self-HL matches. |
| Regression | `uv run pytest tests/unit/skills/test_anomaly_monitor_skill.py -v --tb=short` | 5 passed | Covers real-anomaly counts and CT source fallback. |
| Regression | `uv run pytest tests/unit/agent/test_anomaly_monitor_spec.py -v --tb=short` | 2 passed | SpecBuilder points anomaly monitor to the real CT workbook aliases. |
| Regression | `uv run pytest tests/unit/agent tests/unit/skills -v --tb=short` | 47 passed | Agent and Skill suite remains green. |
| Lint | `uv run ruff check <touched backend paths>` | Passed | Focused Ruff on touched Python paths. |
| Type | `uvx pyright --venvpath . <touched backend paths>` | Passed | Zero errors/warnings. |
| UI Type | `npm run typecheck` | Passed | Workbench UI remains typed. |
| UI Build | `$env:DEEPSEEK_API_KEY='codex-build-placeholder'; npm run build` | Passed | Existing Turbopack NFT tracing warning remains. |
| Real Data Smoke | direct `anomaly_monitor` run with `resources/CT良率异常波动管理表.xlsx` | Passed | `M678`, report date `2026-06-15`, fell back to `2026-06-03`; counts: total 1, HL 1, true anomaly 1. |
| UI Smoke | Browser at `http://127.0.0.1:3100` | Passed | "一键异常监控" no longer reports missing source files and shows the `PEP9 PHT后有机胶过孔异常` notice draft. |

### Task2-fix-2: Source Evidence For Real Anomaly Screening
- **Status:** complete
- Actions taken:
  - Added a red test requiring `source_summary` and `source_evidence` in the public Skill result.
  - Implemented source summaries for loaded aliases and source-backed evidence rows for real anomalies.
  - Added UI rendering for source row counts/date in the anomaly-monitor result panel.
  - Added source summaries to the Markdown artifact.
  - Updated the Skill contract docs with the new output fields.

## Task2-fix-2 Verification
| Phase | Command | Result | Notes |
|-------|---------|--------|-------|
| Red | `uv run pytest tests/unit/skills/test_anomaly_monitor_skill.py::test_anomaly_monitor_derives_candidates_from_ct_exception_source -v --tb=short` | Failed as expected | Missing `source_summary` before implementation. |
| Green | same focused test after implementation | Passed | Result includes source row counts, selected candidate date, and real-anomaly evidence rows. |
| Regression | `uv run pytest tests/unit/skills/test_anomaly_monitor_skill.py -v --tb=short` | 5 passed | Anomaly-monitor unit suite remains green. |
| Regression | `uv run pytest tests/unit/agent tests/unit/skills -v --tb=short` | 47 passed | Agent and Skill suite remains green. |
| Lint | `uv run ruff check src/yield_report/skills/anomaly_monitor/implementation.py tests/unit/skills/test_anomaly_monitor_skill.py` | Passed | Focused Ruff on Task2-fix-2 backend/test files. |
| Type | `uvx pyright --venvpath . src/yield_report/skills/anomaly_monitor src/yield_report/agent/spec_builder.py tests/unit/skills/test_anomaly_monitor_skill.py tests/unit/agent/test_anomaly_monitor_spec.py` | Passed | Zero errors/warnings. |
| UI Type | `npm run typecheck` | Passed | Workbench UI remains typed after source-summary rendering. |
| UI Build | `$env:DEEPSEEK_API_KEY='codex-build-placeholder'; npm run build` | Passed | Existing Turbopack NFT tracing warning remains. |
| Real Data Smoke | direct `anomaly_monitor` run with `resources/CT良率异常波动管理表.xlsx` | Passed | `ct_exception` 2293 rows, `daily_anomaly_initial` 1 row on `2026-06-03`, true anomaly 1. |
| UI Smoke | Browser at `http://127.0.0.1:3100` | Passed | One-click anomaly monitoring shows true anomaly plus source counts: `batch_history 2293`, `ct_exception 2293`, `daily_anomaly_initial 1 · 2026-06-03`. |

### Task3: Merge anomaly_monitor into Runtime-refactor mainline
- **Status:** in_progress
- Scope: merge `codex/feat-anomaly-monitor-task1-2` into the Runtime-refactor mainline while preserving master/refactor Agent Runtime architecture.
- Note: this repository currently has no local `master` branch. The branch containing the Agent Runtime refactor is `codex/refactor` at `abc0ae6`; treat that as the authoritative target unless a real `master` branch appears.
- Required evidence before completion:
  - Backend Runtime can register and execute `anomaly_monitor` as a Skill.
  - Relevant Agent/Skill tests pass after merge.
  - Frontend renders the anomaly-monitor affordance and browser/Playwright smoke reaches a real anomaly result.
