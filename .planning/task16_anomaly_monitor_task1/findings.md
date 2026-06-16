# Findings & Decisions: Anomaly Monitor Task1

## Requirements
- Analyze reference template at `D:\wzy\Python\agents-projects\packages\anomaly_monitor`.
- Analyze anomaly-monitor business rules from encrypted workbook `docs\dev-docs\屏体大数据科-良率监控智能体需求梳理.xlsx`, sheet `值班智能体-需求梳理`.
- Use `.understand-anything` and `ARCHITECTURE.md` to understand the current project.
- Produce a complete development plan for the anomaly monitor module using planning-with-files.
- Do not implement code during Task1.

## Research Findings
- `docs/exec-plans/active/feat-anomaly_monitor.md` defines Task1 as a planning-only task.
- The reference template may only partially implement steps `1.1.1-1.1.3`; workbook rules are authoritative.
- Existing `.planning/.active_plan` previously pointed to `task15_runtime_ui_refactor`; this task uses `task16_anomaly_monitor_task1`.
- `ARCHITECTURE.md` identifies the current mainline as `src/yield_report/agent/`, `src/yield_report/skills/`, and `ui/copilotkit-agent/`, with legacy `application/core/infrastructure` retained as compatibility implementation.
- `docs/agent/architecture.md` says stable repeated business abilities should be exposed as Skills and orchestrated by TaskSpec / Runtime / Trace.
- `docs/agent/skill_contract.md` requires each Skill to provide structured request/result/error/artifact contracts and tests for model validation, success paths, failure paths, trace, and artifact generation.
- Reference template file list shows a small Python package with `application`, `core`, `infrastructure`, and Streamlit-like `interface` folders. Candidate reusable files include `core/anomaly_detector.py`, `core/ai_anomaly_detector.py`, `core/concentration_analyzer.py`, `core/spotfire_replicator.py`, repositories, and dashboard/view-model code.
- Reference template workflow: load HL/CT/MWDL/batch data, build a processed HL table, run row-level anomaly detection, generate report text for `真实异常`, optionally display/edit in Streamlit, and write selected rows to two Excel ledgers.
- Deterministic template rule in `AnomalyDetector`: require `batch_ratio > 0.1%`, `lot_input_ratio > 20%`, `multiplier > 30%`, and `ng_qty > 20`; then mark as hit if current batch ratio exceeds CT historical max or concentration analysis is present; CT station becomes `真实异常`, non-CT station becomes `当站超规`.
- `ConcentrationAnalyzer` checks Lot/Map/Sheet concentration using top-1 and CR-5 style thresholds, then emits compact text such as `Lot集中: ...` or `Map/Lot无明显集中性`.
- `HLDataRepository` implements reusable data-shaping ideas: numeric conversion, `batch_gap`, `worsening_text`, multiplier, latest-row selection by product/defect/station, history join, and batch-yield join.
- `MWDLDataRepository` implements historical MWDL shaping: ratio normalization, defect group join, and batch-yield join for `lot_input_ratio`.
- `HLReportWriter` contains a reusable report-text template, but output fields with manual placeholders (`异常原因`, `是否止血`, department fields) should be modeled as draft/confirmation fields rather than silently written.
- The reference `AIAnomalyDetector` is not production-ready for this repo: it depends on CrewAI/LangChain/Qwen, contains placeholder `pass` logic, and bypasses the project's `llm_manager` requirement.
- No tests, docs, or usable dependency metadata were found in the reference template; `pyproject.toml` is empty and `uv.lock` only contains metadata.
- Migration risks: old `packages.*` import roots, direct Streamlit UI, direct mutable Excel ledger writes, local config model duplication, nested config access bug risk, no test coverage, and potentially stale rules compared with workbook.
- Rule workbook is enterprise encrypted. `fr_file_decryption.inspect_file` detects encrypted header `00 00 00 00 ...`; direct `read_excel()` failed because the COM SaveAs output still had a non-standard encrypted header, but a temporary Excel COM UsedRange reader successfully extracted rule text.
- Rule workbook sheets: `值班智能体-需求梳理`, `1.1.1 数据读取-图表样例`, `1.1.1 数据读取-规则库`, `1.1.2 异常识别-规则库`, `1.1.3 异常通报-规则库`, `1.1.4 回复审核-规则库`, `1.2.1 异常进度追踪-规则库`, `1.2.2 改善效果确认-规则库`, plus daily-report sheets.
- Step `1.1.1 数据读取` requires five sources: 当日异常初筛表, CT良率异常波动管理表, CT不良率Mapping图 (`CT MAP-NG` and `CT MAP-RATIO` for recent five days), CT LOT/SHEET/GLASS/工单集中性, and 批次月周天数据.
- Step `1.1.2 异常识别` authoritative sequence: check analysable batch by batch output ratio, check concentration, check whether already HL, then check whether key-station batch loss exceeds spec.
- Workbook batch-output rule: `MVI > 10%`; other stations `> 30%`.
- Workbook concentration rule says `同AI异常分析`; no detailed rule was found in this workbook. Template `ConcentrationAnalyzer` is the closest available implementation but should be treated as a provisional port until the AI anomaly-analysis rule is supplied.
- Workbook already-HL rule: compare latest HL time from initial table to CT abnormality management table; considered already HL if latest HL batch equals current worsened batch, or if latest HL batch and current batch are within 10 days and concentration is consistent.
- Workbook key-station rule header exists but has no content; this is an implementation blocker unless clarified or placed behind configurable/manual confirmation.
- Workbook spec rule: spec is the average defect rate of the first three valid high-frequency batches where `批次月周天数据-lot_input_ratio > 95%`; if fewer than three valid batches exist, use the product's `新品送样` work-order defect rate.
- Step `1.1.3 HL通报生成` requires an HL notice text template, records into HL记录表 and 异常管理表, and push to CT异常沟通群. Initial implementation should generate draft artifacts and make write/push actions gated.
- Notification owner rules in workbook map factory/group to owners: `Array_AD -> 施明君`, `Array_Line -> 徐慕凡`, `Array_Mura -> 施健丰`, `Array_Pixel -> 田凤`, `ARRAY_RS查杀 -> 郑帮留`, `ARRAY其他 -> 黄从城`, OLED uses duty roster, TP -> `朱栩`, 屏体 -> `霍丽`.
- Current architecture has existing `ExcelSheetReader` logic in `daily_report` that reads standard xlsx or enterprise-encrypted files via COM UsedRange. This is a better implementation basis than relying on decrypted copies.
- Current runtime extension points: add Skill under `src/yield_report/skills/<name>`, register it in `src/yield_report/agent/registry.py`, allow it in `SpecBuilder`/`SpecValidation`, and expose through `scripts/agent_workbench_bridge.py` and `ui/copilotkit-agent/app/api/agent-runs/route.ts`.
- Current resources include `CT良率异常波动管理表.xlsx`, `spotfire.xlsx`, daily-yield files, and target decomposition. They do not currently include all anomaly-monitor-specific sources from the workbook, so the first implementation must define source aliases and acquisition expectations.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Treat workbook as source of truth over template behavior | The execution plan explicitly states the old template rules may be inaccurate. |
| Keep Task1 output as planning artifacts and user-facing plan | The user requested planning first and no execution. |
| Rebuild adapters around current `yield_report` Skill contracts | The template's data and UI adapters are tied to another project; only pure transformation/judgement logic should be migrated. |
| Treat direct ledger write and group push as later gated steps | They mutate shared business files or external channels and need explicit confirmation, trace, and rollback expectations. |
| Extract or share Excel COM reading before building anomaly sources | Rule workbook and CT exception files may be enterprise encrypted; existing `daily_report` already solved direct COM reading better than SaveAs-based decrypt copies. |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| Default PowerShell read of execution plan produced mojibake | Re-read with `-Encoding UTF8`. |
| `fr_file_decryption` was not installed in default Python | Used `PYTHONPATH=D:\wzy\Python\packages\file_decryption\src` to call the package API. |
| Decrypted workbook copy remained non-standard/encrypted | Used a temporary COM UsedRange probe for Task1 research; implementation plan recommends extracting shared Excel reader instead of relying on SaveAs output. |

## Resources
- `docs/exec-plans/active/feat-anomaly_monitor.md`
- `D:\wzy\Python\agents-projects\packages\anomaly_monitor`
- `docs\dev-docs\屏体大数据科-良率监控智能体需求梳理.xlsx`
- `.understand-anything/knowledge-graph.json`
- `ARCHITECTURE.md`
- `docs/agent/architecture.md`
- `docs/agent/skill_contract.md`
- `D:\wzy\Python\agents-projects\packages\anomaly_monitor\src\core\anomaly_detector.py`
- `D:\wzy\Python\agents-projects\packages\anomaly_monitor\src\core\concentration_analyzer.py`
- `D:\wzy\Python\agents-projects\packages\anomaly_monitor\src\application\hl_report_service.py`
- `D:\wzy\Python\agents-projects\packages\anomaly_monitor\src\infrastructure\repositories\hl_data_repository.py`
- `D:\wzy\Python\agents-projects\packages\anomaly_monitor\src\infrastructure\repositories\mwdl_data_repository.py`
- `src/yield_report/agent/spec_model.py`
- `src/yield_report/agent/runtime.py`
- `src/yield_report/agent/registry.py`
- `src/yield_report/agent/spec_builder.py`
- `src/yield_report/agent/spec_validation.py`
- `src/yield_report/skills/daily_report/implementation.py`
- `ui/copilotkit-agent/app/api/agent-runs/route.ts`

## Visual/Browser Findings
- None yet.
