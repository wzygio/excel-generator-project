# Findings: Anomaly Monitor Development

## Inputs From Task1
- Reference template provides deterministic pieces: batch/concentration checks, report draft template, and data-shaping ideas.
- Workbook is authoritative:
  - MVI batch output ratio must be `> 10%`.
  - Other stations require `> 30%`.
  - Already-HL means same batch, or within 10 days with consistent concentration.
  - Spec is average of first three valid batches with `lot_input_ratio > 95%`; new-sample fallback is unavailable in current sources.
  - Key-station selection rule is blank and must remain configurable or blocked.
- Current architecture expects new Skills under `src/yield_report/skills/<name>/` with `models.py`, `tool.py`, `implementation.py`, `SKILL.md`, and registration in `src/yield_report/agent/registry.py`.

## Current Worktree
- Branch/worktree: `codex/feat-anomaly-monitor-task1-2` at `D:\wzy\Python\excel-generator-project-anomaly-monitor`.
- Initial status is clean.
- Existing active planning pointer was `task11_agent_arch`; this task uses `task17_anomaly_monitor_dev`.

## Risks
- UI file may differ from the dirty main worktree; implement against this clean branch only.
- Workbook rules have known blanks; tests should assert warnings/blocked behavior for those blanks.
- Direct ledger writes and group-message pushes remain disabled by default and only produce warnings when requested.
- Full-repository lint is not green because of pre-existing files outside this task; touched backend paths are clean.

## Implemented Outcome
- Added the registered `anomaly_monitor` Skill and deterministic analyzer pipeline.
- Implemented rule coverage for batch output gate, concentration evidence, already-HL matching, spec calculation, blocked decisions, and HL notice draft generation.
- Added TaskSpec builder routing for anomaly-monitor goals with source-file aliases and side effects disabled.
- Added Workbench UI module, preset prompt, Copilot frontend tool enum support, source card, workflow steps, and result summary rendering.
- Added focused unit tests for Skill behavior and Spec/runtime integration.

## Task3 Merge Findings
- There is no local `master` branch in this repository. The branch containing the current Agent Runtime refactor is `codex/refactor` at `abc0ae6`.
- `codex/refactor` already contains the committed historical anomaly-monitor branch base, but not the current dirty/untracked `anomaly_monitor` Skill package and tests.
- The refactor mainline has moved the UI from the older direct `yield-skill` module panel to `/api/agent-runs -> SpecBuilder -> RuntimeRouter`; anomaly monitor must use that path.
- The current Runtime mainline includes Letta support, but `config/global.yaml` defaults `agent.default_runtime` to `python`, so anomaly-monitor auto runs execute through the deterministic Python Skill runtime unless a caller explicitly requests Letta/OMP.
- PowerShell stdin can garble Chinese JSON into `?` when testing the bridge manually. SpecBuilder now also recognizes ASCII `anomaly_monitor`/`anomaly ... HL` goals so this does not silently fall back to `daily_report`.
- The Playwright smoke must click the sidebar fixed workflow button `button.daily-button.secondary`; the page has several other “异常监控” buttons used for intent switching and prompt chips.

## Task2 Data Source Correction
- The original UI failure came from generated anomaly-monitor specs referencing non-existent files under `resources/anomaly_monitor/`.
- The only real local anomaly-monitor source currently available is `resources/CT良率异常波动管理表.xlsx`.
- The encrypted rule workbook confirms the 1.1.1 source contract expects five inputs, but the local workspace does not contain the Spotfire daily initial, CT mapping, concentration, or batch-history exports as separate files.
- The practical fallback is to reuse `CT良率异常波动管理表.xlsx` as:
  - `daily_anomaly_initial`: normalized and filtered candidate rows.
  - `ct_exception`: historical HL/exception records.
  - `batch_history`: provisional batch-history rows when no richer batch source is present.
- `true_anomaly` should mean all rows whose decision is `HL`, because the rule workbook names 1.1.2 output `HL异常数据`.
- `station_over_spec` is a subtype count for rows triggered by the key-station spec branch.
- Real-data smoke for `M678` on report date `2026-06-15` falls back to latest available date `2026-06-03` and identifies one real anomaly: `PEP9 PHT后有机胶过孔异常` at `CUT`.

## Task2-fix-2 Evidence Gap
- Before Task2-fix-2, the Skill could screen a real anomaly but only exposed the supporting source row deep inside `real_anomalies[*].raw`.
- This made the UI and top-level JSON weak as proof that related data had actually been acquired.
- The result payload now exposes:
  - `source_summary`: loaded row counts, compact date windows, date range, and source tables.
  - `source_evidence.real_anomaly_rows`: source-backed fields for each real anomaly, including notice and reply text.
- Real-data evidence for `M678` on `2026-06-15`:
  - `ct_exception`: 2293 rows loaded from `CT良率异常波动管理表.xlsx`.
  - `daily_anomaly_initial`: 1 candidate selected for `2026-06-03`.
  - `real_anomalies`: 1 row, `PEP9 PHT后有机胶过孔异常`, station `CUT`, owner `陈若春`, status `Open`.

## Task2-fix HL Noise Analysis
- `output/anomaly_monitor_smoke/anomaly_monitor_result.json` originally had 916 verdicts and 423 HL rows.
- After tightening concentration to Top1 50% and dynamic top-unit cumulative 80%, the same smoke run had 970 verdicts and 328 HL rows.
- The remaining 328 HL rows split into 304 non-CT `当站超规` rows and 24 CT rows.
- Concentration over-triggering was real but not the dominant remaining source; the larger issue is that mwdl fallback creates multiple LOT candidates for the same product/defect/station and the verdict path allowed non-CT stations to become final HL.
- Fixed Top5 cumulative ratio is invalid for small produced-unit counts: when there are only five units, Top5 is automatically 100%. The algorithm should use a fixed fraction of produced units, currently Top 20% via floor with a minimum of one unit.
- User clarified the final business rule: only `发生站点=CT` rows should be HL.
- Final Task2-fix smoke result for the five-product run (`M626,C550,M756,M673,C522`) is total 248, HL 15, skipped 233, blocked 0.
- Final HL rows are all CT in JSON, and the markdown notice draft station lines are all `发生站点=CT`.
- The final 15 HL rows are all concentration-triggered after stricter dynamic unit-ratio screening.

## Task1 HL Logic Optimization
- The three user-provided target anomalies are present in the current 2026-06-22 source data; this is not a missing-source problem.
- `C546&C547` was missed because Spotfire product parsing split the combined model into `C546` and `C547`, while the source rows use the combined `C546&C547` key.
- `M756 屏体异物(黑白点/凹点)` was present as a CT `hl_data` row but skipped because the previous final-HL logic required strong concentration or recalculated history over-limit.
- `C530 S向亮线` and `C546&C547 S向亮线` are valid CT source-HL candidates with no strong concentration; they need source-table initial-screening logic rather than concentration-only logic.
- Final source-HL selection now keeps one strongest CT `hl_data` row per product, ranked by daily loss, batch loss, batch gap, and NG quantity.
- `M756 屏体异物(黑白点/凹点)` has valid-output MAP distribution with `1F-E0` and `2F-E0` as the leading MAPs; report text now emits `MAP较集中: 1FE0/2FE0` without relaxing the strong concentration trigger.

## Resources
- `docs/exec-plans/active/feat-anomaly_monitor.md`
- `ARCHITECTURE.md`
- `docs/agent/skill_contract.md`
- `docs/agent/spec_contract.md`
- `src/yield_report/agent/registry.py`
- `src/yield_report/agent/spec_builder.py`
- `src/yield_report/agent/spec_validation.py`
- `ui/copilotkit-agent/app/page.tsx`
