# Development Plan: Anomaly Monitor

## Goal
Add an `anomaly_monitor` fixed workflow that reads the required anomaly-monitor sources, identifies true HL anomalies according to the workbook rules, generates traceable HL notice drafts, and integrates with the existing Spec / Skill / Runtime / CopilotKit Workbench architecture.

Task1 is planning only. Do not implement until the user confirms this plan.

## Source Of Truth
- Authoritative rules: `docs/dev_docs/屏体大数据科-良率监控智能体需求梳理.xlsx`.
- Reference template: `D:\wzy\Python\agents-projects\packages\anomaly_monitor`.
- Current architecture: `ARCHITECTURE.md`, `docs/agent/*`, `src/yield_report/agent/*`, `src/yield_report/skills/*`, `ui/copilotkit-agent`.

## Target Architecture

Add a fourth business Skill:

```text
src/yield_report/skills/anomaly_monitor/
├── SKILL.md
├── models.py
├── tool.py
├── implementation.py
├── analyzers.py
├── sources.py
└── templates.py
```

Recommended supporting refactor:

```text
src/yield_report/infrastructure/excel_reader.py
```

Move or wrap the existing `daily_report.ExcelSheetReader` behavior there so both `daily_report` and `anomaly_monitor` can read standard and enterprise-encrypted Excel files without relying on COM SaveAs copies.

## Data Contracts

### Request Model
`AnomalyMonitorRequest`

- `report_date: str | None`
- `product_models: list[str] | None`
- `source_files: dict[str, Path]`
- `report_refs: list[Any]`
- `mode: Literal["detect", "draft_notice", "record", "full"] = "detect"`
- `write_ledgers: bool = False`
- `push_notifications: bool = False`
- `rules_profile: str = "default"`
- `emit_intermediate_artifacts: bool = True`

### Source Aliases

- `daily_anomaly_initial`: 当日异常初筛表.
- `ct_exception`: CT良率异常波动管理表.
- `ct_map_ng`: CT MAP-NG, recent five days.
- `ct_map_ratio`: CT MAP-RATIO, recent five days.
- `ct_concentration`: CT LOT/SHEET/GLASS/工单集中性.
- `batch_history`: 批次月周天数据.
- `owner_mapping`: 通报责任人 / 值班表 source, optional.

### Output Data

- `anomaly_rows`: normalized input rows.
- `verdicts`: each row's eligibility, concentration, already-HL result, spec result, final status.
- `hl_anomalies`: rows requiring HL.
- `notice_drafts`: generated HL notification text.
- `blocked_items`: rows skipped due missing rule/source.
- `source_files`: actual paths used.

Artifacts:

- `anomaly_monitor_result.json`
- `anomaly_monitor_summary.md`
- optional `anomaly_monitor_candidates.xlsx`

## Authoritative Rule Flow

1. Data Read
   - Load workbook/table sources listed above.
   - Normalize fields from workbook: TYPE, prod_code, defect_desc, oper_group, daily/month/week/batch loss, batch worsening, batch output rate, batch gap, multiplier, latest HL time, HL count, ng_qty, HL reason.

2. Analysable Batch Gate
   - If station is `MVI`, require batch output ratio `> 10%`.
   - Other stations require batch output ratio `> 30%`.
   - Rows failing the gate are skipped with a structured reason.

3. Concentration Check
   - Workbook says rule is same as AI anomaly analysis.
   - First implementation should port template `ConcentrationAnalyzer` as deterministic provisional logic, but label it `provisional_ai_anomaly_concentration`.
   - If authoritative AI anomaly-analysis rules are supplied later, replace this analyzer without changing the Skill contract.

4. Already-HL Check
   - Match latest HL record from CT abnormality management table.
   - Already HL if latest HL batch equals current worsened batch.
   - Also already HL if latest HL batch and current worsened batch differ by less than 10 days and concentration evidence is consistent.

5. Key-Station Spec Check
   - Workbook does not define key-station selection. Implement as a configurable rule and return `needs_confirmation`/blocked warning when absent.
   - Spec value = average defect rate of first three valid high-frequency batches where `batch_history.lot_input_ratio > 95%`.
   - If fewer than three valid batches exist, source a product `新品送样` work-order defect rate; if unavailable, block that row with a recoverable warning.

6. Final Verdict
   - HL if concentration is present.
   - Otherwise, if not already HL and key-station batch loss exceeds spec, HL.
   - Keep template labels `真实异常` / `当站超规` only if they still match workbook semantics after user confirmation; workbook speaks in terms of `HL异常数据`.

7. HL Notice Draft
   - Generate workbook-format text:
     - 产品型号
     - 不良名称
     - 发生站点
     - 是否再发
     - 首次通报
     - 基础分析
     - 异常良损
     - 异常原因
     - Inline监控
     - 是否止血
     - 影响范围
     - 改善措施
     - 整合对接
     - 责任部门
     - 责任科室
   - Keep manual fields as placeholders unless source data provides them.

8. Ledger Write / Push
   - Phase 1 implementation should not auto-write shared Excel ledgers or push group messages.
   - Add optional gated modes only after detection and draft artifacts are stable.

## Implementation Phases

### Phase A: Contract And Fixtures
- Add `src/yield_report/skills/anomaly_monitor/` files.
- Add Pydantic models for source refs, normalized rows, concentration evidence, verdicts, drafts, and request/result payload.
- Add workbook-derived rule constants in code-owned typed config or `config/global.yaml` with matching `AppConfig` model updates.
- Add synthetic fixtures under tests, not real production workbooks.

Tests:
- model validation
- percent parsing
- date/batch parsing
- source alias validation

### Phase B: Shared Excel Reader
- Extract `ExcelSheetReader` from `daily_report` into infrastructure or add a reusable wrapper.
- Support standard xlsx with openpyxl and encrypted files via COM UsedRange.
- Keep decrypted/runtime outputs under ignored run directories only.

Tests:
- openpyxl path with fixture workbook
- COM path behind focused unit boundary or skipped/manual marker when Excel unavailable
- missing sheet error shape

### Phase C: Source Normalization
- Implement source resolution from request `source_files`, `report_refs`, and Spec `inputs.local_files`.
- Normalize each required source into typed row dictionaries.
- Return recoverable SkillError when required source is absent.

Tests:
- missing required source
- alias path resolution
- column synonyms and empty-row handling

### Phase D: Rule Engine
- Port and adapt deterministic pieces from template:
  - batch output gate
  - concentration analyzer
  - already-HL matcher
  - spec calculator
  - final verdict assembler
- Keep IO out of analyzers; analyzers accept normalized rows/dataframes.

Tests:
- MVI `>10%` vs other station `>30%`
- concentration true/false
- already-HL same batch
- already-HL within 10 days plus same concentration
- valid batch spec using first three `lot_input_ratio >95%`
- blocked row when key-station/new-sample source missing

### Phase E: Skill Tool And Artifacts
- Implement `tool.py` and `implementation.py` returning `SkillResult`.
- Write JSON and Markdown artifacts to `context.output_dir`.
- Include warnings and `blocked_items`.
- Add `anomaly_monitor` to `src/yield_report/agent/registry.py`.
- Update `SpecValidator` registered skill sets where hard-coded.

Tests:
- `tool.run()` success path
- structured failure path
- artifact generation
- trace integration through `AgentRuntime`

### Phase F: Spec Builder / Scripts
- Extend `SpecBuilder` to recognize goals containing `异常监控`, `真实异常`, `HL通报`, or `异常识别`.
- Build a TaskSpec workflow:
  - optional source preparation/download step if source aliases map to existing report_download capabilities
  - `run_anomaly_monitor` skill step
- Update `scripts/create_daily_report_spec.py` or add a more general `scripts/create_task_spec.py` only if needed.

Tests:
- anomaly-monitor goal builds a valid spec
- validation accepts `anomaly_monitor`
- run store snapshot includes artifacts and memory candidates

### Phase G: CopilotKit Workbench UI
- Keep one Workbench, not a separate Streamlit UI.
- Add anomaly-monitor preset/options to the existing page.
- Display returned workflow steps, warnings, artifacts, and anomaly rows/drafts.
- Add explicit confirmation UI before ledger write or notification push in later phases.

Validation:
- `cd ui/copilotkit-agent && npm run typecheck`
- `cd ui/copilotkit-agent && npm run build`
- browser smoke for create/run anomaly-monitor spec if UI changes are included

### Phase H: Optional Ledger Write And Push
- Only after user confirmation:
  - implement `write_ledgers=True` as a separate, traceable action
  - check file lock and backup/append behavior
  - implement notification push as dry-run first
- Do not mutate shared network Excel files by default.

## Validation Commands

Focused backend:

```bash
uv run pytest tests/unit/skills/test_anomaly_monitor_skill.py -v --tb=short
uv run pytest tests/unit/agent tests/unit/skills -v --tb=short
```

Quality and typing when config/contracts change:

```bash
uv run ruff check .
uv run pyright
```

UI, if touched:

```bash
cd ui/copilotkit-agent
npm run typecheck
npm run build
```

## Risks And Open Questions

- `关键站点选取规则` is blank in the workbook. Need user/business clarification or a configured fallback before full automatic verdicts are trustworthy.
- `集中性判定逻辑` references `AI异常分析`, but this workbook does not include that rule. Template logic can be a provisional deterministic implementation only.
- Required sources for CT maps, concentration, and batch history are not all present in current `resources/`; report download/local-file acquisition must be defined.
- `fr_file_decryption` COM SaveAs did not produce a standard zip-xlsx for this workbook. Prefer direct COM reading like current `daily_report` code.
- Direct ledger writes and group pushes are high-risk side effects and should be separated behind confirmation.
- Existing worktree has unrelated user changes; implementation must preserve them.

## Acceptance Criteria

- `anomaly_monitor` is registered as a Python Skill and executable by TaskSpec.
- Given controlled fixtures, it produces deterministic verdicts matching workbook rules.
- Missing rule/source cases return recoverable errors or warnings, not silent false negatives.
- It writes traceable JSON/Markdown artifacts under `specs/runs/<run_id>/outputs/`.
- Workbench can create/run an anomaly-monitor spec and show results.
- No automatic ledger write or chat push occurs unless explicitly enabled and confirmed.
