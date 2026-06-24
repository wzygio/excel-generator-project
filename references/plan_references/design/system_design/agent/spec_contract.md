# Spec 契约

## 1. 目标

Spec 是用户需求与 Agent 执行之间的任务契约。它既要让用户能用自然语言修改流程，也要让 Codex、UI 和 Python 工具能稳定执行。

Spec 描述的是“要完成什么”“需要哪些输入与约束”“按什么 Skill 顺序执行”“产出什么可追溯结果”。Spec 不应包含 Python 代码，也不应直接写死浏览器点击、Excel COM 操作、FineReport 页面步骤等执行细节；这些细节属于 Skill 或底层适配器。

本项目的智能体是强人工交互 Agent。Spec 制定本身是 Agent Runtime 内部的需求解析步骤，默认由 LangGraph Spec sub-agent 完成；Codex 不在执行链路中，也不得生成 run_id 或 Spec 字段。

## 2. 构建来源

Spec 构建模式必须显式标记为以下模式之一：

| 模式 | 构建方式 | 适用场景 |
|------|----------|----------|
| `langgraph` | LangGraph Spec sub-agent 构建、校验、自动修复 | 默认模式，适用于除固定业务流程外的所有 Spec 构建请求。 |
| `rule` | 固定模板规则构建、代码校验 | 仅适用于显式声明的 `anomaly_monitor` 和 `daily_report` 固定业务流程。 |

约束：

- LangGraph Spec sub-agent 是默认构建模式，不绑定某一种入口。
- 规则构建只允许在请求显式声明为固定业务流程，且 capability 为 `anomaly_monitor` 或 `daily_report` 时使用。
- 除 `anomaly_monitor` 和 `daily_report` 固定业务流程外，任何 Spec 构建请求都必须进入 LangGraph Spec sub-agent。
- 规则构建不得作为 LangGraph 构建失败后的静默兜底。LangGraph 多次修复仍失败时，应返回 `needs_confirmation` 或结构化错误。
- Runtime 不负责主要构建 Spec。Runtime 消费已生成的 Spec，执行 workflow，写入 trace、memory candidates、run summary 和 outputs。

## 3. LangGraph Spec Sub-Agent 约束

LangGraph Spec sub-agent 生成 Spec 时必须参考以下材料：

1. 本文件：`docs/agent/spec_contract.md`。
2. 相关模板：`specs/templates/<capability>_spec.yaml`，例如 `daily_report_spec.yaml`、`anomaly_monitor_spec.yaml`。
3. Skill 契约：`docs/agent/skill_contract.md`。
4. 目标 Skill 的说明和输入模型：`src/yield_report/skills/<skill>/SKILL.md` 与 `models.py`。
5. 当前注册 Skill 清单和 `TaskSpec` / `SkillCall` 字段模型。

如果上述材料无法读取，Spec sub-agent 不应凭空生成可执行 Spec。它应将 Spec 状态设为 `needs_confirmation`，或返回结构化构建错误。

LangGraph Spec sub-agent 必须至少包含以下节点：

1. `load_context`：加载契约、模板、Skill 契约和注册 Skill 清单。
2. `draft`：由 Agent Runtime 内部 LLM 生成 Spec 初稿。
3. `validate`：解析为 `TaskSpec` 并运行代码校验。
4. `repair`：将校验错误反馈给 LLM 自动修复，最多重试 2 次。
5. `finalize`：通过则进入 `ready`，失败则进入 `needs_confirmation`。

LLM 输出必须经过代码约束：

- 只输出 JSON 或 YAML 数据，不输出解释性文本。
- 必须能解析为 `TaskSpec`。
- 必须通过 Pydantic 字段校验和 `SpecValidator` 交叉字段校验。
- `workflow[*].skill` 必须来自已注册 Skill。
- `workflow[*].input` 必须符合对应 Skill 的请求模型。
- `memory.reuse_policy` 必须为 `confirmed_only`。
- 不得生成浏览器点击步骤、Excel 单元格手工操作步骤或 Python 代码片段。
- 校验失败时，必须进入 repair 节点自动修复；超过最大修复次数后仍失败则进入 `needs_confirmation`。

建议 LLM Builder 的提示词至少包含：

```text
你是良率日报 Agent Runtime 内部的 Spec sub-agent。
请严格依据 docs/agent/spec_contract.md、选中的 specs/templates/*.yaml、
docs/agent/skill_contract.md 和目标 Skill 输入模型生成 TaskSpec。
只输出 JSON，不输出解释。不得写 Python 代码或浏览器操作步骤。
```

## 4. 文件位置

长期模板：

```text
specs/templates/<capability>_spec.yaml
```

每次运行：

```text
specs/runs/<run_id>/spec.yaml
```

测试样例：

```text
tests/fixtures/specs/<case_name>.yaml
```

目录约束：

- `specs/templates/` 存放可复用、可审查、可版本管理的模板。
- `specs/runs/` 是运行态目录，默认不进入 git。
- `tests/fixtures/specs/` 存放测试用稳定样例，允许进入 git。
- 运行中发现的稳定业务规则，不得直接从 `specs/runs/` 复制为事实来源；应整理后沉淀到模板、文档或受代码支持的 spec 字段。
- 临时调试、烟测和失败重跑都应留在 `specs/runs/`，不得污染模板目录。

建议运行目录结构：

```text
specs/runs/<run_id>/
├── spec.yaml
├── trace.jsonl
├── memory_candidates.json
├── run_summary.json
└── outputs/
```

## 5. run_id 命名

`run_id` 必须体现业务意图，禁止使用只有时间戳的命名，例如 `run-YYYYMMDD-HHMMSS`。

推荐格式：

```text
<source>-<capability>-<YYYYMMDD-HHMMSS>
```

字段约定：

| 字段 | 示例 | 说明 |
|------|------|------|
| `source` | `agent`、`ui`、`api`、`smoke`、`test` | 触发来源，由 Agent Runtime 入口元数据确定。 |
| `capability` | `daily-report`、`anomaly-monitor`、`yield-trend`、`report-download`、`data-analysis` | 主要业务能力，必须来自代码枚举或固定流程声明。 |
| timestamp | `20260623-143015` | 唯一性后缀。 |

示例：

```text
agent-daily-report-20260623-143015
agent-yield-trend-20260623-143015
ui-anomaly-monitor-20260623-143015
smoke-daily-report-20260623-143015
test-report-download-20260623-143015
```

命名规则：

- 使用小写 kebab-case。
- 只允许英文字母、数字和 `-`。
- `source` 不得来自 LLM、Codex 或用户自然语言自由文本。
- `capability` 不得自由拼接；必须通过枚举校验。
- 允许用时间戳保证唯一性，但时间戳不得成为唯一语义。

## 6. 生命周期

| 状态 | 含义 |
|------|------|
| `draft` | 由用户需求初步生成，尚未确认。 |
| `ready` | 已可执行。 |
| `running` | Runtime 正在执行。 |
| `needs_confirmation` | 存在需要用户确认的输入、下载、memory、写表或 LLM 解释决策。 |
| `completed` | 执行完成。 |
| `failed` | 执行失败，trace 中应有错误详情。 |

## 7. 顶层字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `schema_version` | 是 | 当前为 `1`。 |
| `run_id` | 是 | 运行 ID；运行态 Spec 必填，模板中可为空。 |
| `status` | 是 | 生命周期状态。 |
| `user_goal` | 是 | 用户原始目标或整理后的目标。 |
| `constraints` | 否 | 全局约束，如禁止联网、仅使用本地文件、构建来源。 |
| `inputs` | 是 | 报表、日期、产品、文件等输入要求。 |
| `workflow` | 是 | Skill 调用序列。 |
| `outputs` | 是 | 期望产物。 |
| `memory` | 否 | memory 复用与写入策略。 |
| `trace` | 否 | trace 输出配置。 |

约定：

- `created_at`、`updated_at` 等审计字段只有在 `TaskSpec` 模型支持后才能写入顶层字段。
- 触发来源应写入 `constraints.spec_source`，例如 `agent`、`smoke` 或 `test`。
- LangGraph 构建时应写入 `constraints.spec_builder: langgraph` 和 `constraints.builder_mode: langgraph`。
- 规则构建时应写入 `constraints.spec_builder: rule` 和 `constraints.builder_mode: rule`，并写明 `constraints.fixed_flow: true`。
- capability 应写入 `constraints.capability`。

## 8. inputs

```yaml
inputs:
  report_date: "2026-06-01"
  product_models:
    - M678
  date_range:
    start: "2026-05-26"
    end: "2026-06-01"
  reports:
    - alias: daily_yield
      report_type: daily_yield
      required: true
      filters:
        product_models:
          - M678
        end_date: "2026-06-01"
    - alias: batch_yield
      report_type: batch_yield
      required: false
  local_files: []
```

约定：

- `alias` 是下游 workflow 引用报表的稳定 ID。
- `report_type` 使用 Skill 契约中的枚举。
- `filters` 表达业务筛选条件，不表达页面操作细节。
- `local_files` 可用于用户手动指定文件路径。
- 对话框任务中缺失关键输入时，LLM Builder 应生成 `needs_confirmation`，而不是擅自扩大范围。

## 9. workflow

```yaml
workflow:
  - id: download_daily_yield
    skill: report_download
    input:
      report_ref: daily_yield
    save_as: daily_yield_file

  - id: analyze_ct_trend
    skill: data_analysis
    depends_on:
      - download_daily_yield
    input:
      question: "分析 M678 近一周日度 CT 良率变化趋势"
      report_refs:
        - daily_yield_file
      metrics:
        - CT良率
      analysis_intent: trend
    save_as: ct_trend_result

  - id: generate_daily_report
    skill: daily_report
    depends_on:
      - analyze_ct_trend
    input:
      sections:
        - ct_trend
      analysis_results:
        - ct_trend_result
    save_as: daily_report_file
```

约定：

- `id` 在单个 Spec 内唯一。
- `skill` 必须对应已注册 Skill。
- `depends_on` 表示运行顺序依赖。
- `save_as` 表示把结果写入 RunContext，供后续步骤引用。
- `input` 可以引用 `inputs` 中的 alias 或上游 `save_as`。
- 固定按钮流程可以使用模板中固定 workflow；对话框流程由 LLM 根据用户意图选择 workflow。

## 10. outputs

```yaml
outputs:
  daily_report:
    required: true
    format: xlsx
    directory: outputs
    filename_template: "良率日报_{report_date}_{product_models}.xlsx"
  analysis_summary:
    required: true
    format: markdown
  trace:
    required: true
    format: jsonl
```

约定：

- 运行态产物目录应优先使用当前 run 目录下的 `outputs/`。
- 输出声明必须描述最终可交付物，不应列出临时缓存文件。

## 11. memory

```yaml
memory:
  reuse_policy: confirmed_only
  candidate_policy: record_pending
  allowed_record_ids: []
```

约定：

- `reuse_policy` 默认必须为 `confirmed_only`。
- 新增 memory 只能以 pending 候选写入。
- 自动复用 memory 时，trace 必须记录 record ID 和匹配理由。
- 对话框任务中引用历史规则时，应让用户可见地确认关键复用项。

## 12. trace

```yaml
trace:
  level: step
  include_inputs: true
  include_outputs: true
  include_errors: true
  path: trace.jsonl
```

每条 trace 建议包含：

| 字段 | 说明 |
|------|------|
| `timestamp` | 步骤时间。 |
| `run_id` | 运行 ID。 |
| `step_id` | workflow 步骤 ID。 |
| `skill` | Skill 名称。 |
| `status` | `started`、`succeeded`、`failed`。 |
| `input_summary` | 输入摘要。 |
| `output_summary` | 输出摘要。 |
| `artifacts` | 产物路径。 |
| `error` | 失败详情。 |

## 13. 校验规则

构建后、执行前必须校验：

- `schema_version` 支持。
- `run_id` 符合业务命名规则。
- `status` 属于生命周期枚举。
- `constraints.spec_source` 来自入口元数据，且不能由 LLM 覆盖。
- `constraints.capability` 来自代码枚举或固定流程声明。
- `workflow[*].id` 唯一。
- `workflow[*].skill` 已注册。
- `workflow[*].input` 符合对应 Skill 请求模型。
- `depends_on` 指向存在且先于当前步骤的 step。
- `required` 报表或文件有可执行获取方式。
- `outputs` 至少声明一个最终产物。
- `memory.reuse_policy` 不允许默认复用 pending 记录。

## 14. Rules Boundary

Spec-owned rules 是稳定、可复用、可由用户理解和维护的任务规则。它们应放在 `specs/templates/`、测试 fixture、文档，或受代码支持的 Spec 字段中。

Spec-owned 示例：

- workflow 步骤和顺序。
- 报表 alias 和 required source reports。
- 产品型号、日期范围、筛选条件和输出期望。
- 可选分析 sections 和可复用报表参数。
- 构建来源、运行约束、是否需要用户确认。

Code-owned logic 属于 typed Python modules。

Code-owned 示例：

- Excel 读取、解密、校验和写入。
- FineReport 自动化、下载和文件定位。
- dataframe 转换和 analyzer。
- Skill request/result/error/artifact contracts。
- security、filesystem、logging、runtime trace handling。
- run_id 生成、校验、路径安全和重复处理。
- LLM 输出解析、模型校验和失败修复循环。

不要把频繁变化的业务规则硬编码在 Python 中，除非用户明确要求一次性实验。也不要把底层执行细节写进 Spec。

## 15. 最小示例

```yaml
schema_version: 1
run_id: agent-daily-report-20260623-143015
status: ready
user_goal: "生成 M678 今天的良率日报，包含近一周 CT 良率趋势"

constraints:
  spec_source: agent
  spec_builder: langgraph
  builder_mode: langgraph
  capability: daily-report
  codex_in_execution_chain: false
  codex_is_agent_core: true
  prefer_existing_tools: true
  require_user_confirmation_for_pending_memory: true

inputs:
  report_date: "2026-06-23"
  product_models:
    - M678
  date_range:
    start: "2026-06-17"
    end: "2026-06-23"
  reports:
    - alias: daily_yield
      report_type: daily_yield
      required: true
      filters:
        product_models:
          - M678
        end_date: "2026-06-23"
  local_files: []

workflow:
  - id: download_daily_yield
    skill: report_download
    input:
      report_ref: daily_yield
    depends_on: []
    save_as: daily_yield_file

  - id: analyze_ct_trend
    skill: data_analysis
    depends_on:
      - download_daily_yield
    input:
      question: "分析 M678 近一周日度 CT 良率变化趋势"
      report_refs:
        - daily_yield_file
      metrics:
        - CT良率
      analysis_intent: trend
    save_as: ct_trend_result

  - id: generate_daily_report
    skill: daily_report
    depends_on:
      - analyze_ct_trend
    input:
      sections:
        - ct_trend
      analysis_results:
        - ct_trend_result
    save_as: daily_report_file

outputs:
  daily_report:
    required: true
    format: xlsx
    directory: outputs
    filename_template: "良率日报_{report_date}_{product_models}.xlsx"
  analysis_summary:
    required: true
    format: markdown
  trace:
    required: true
    format: jsonl

memory:
  reuse_policy: confirmed_only
  candidate_policy: record_pending
  allowed_record_ids: []

trace:
  level: step
  include_inputs: true
  include_outputs: true
  include_errors: true
  path: trace.jsonl
```
