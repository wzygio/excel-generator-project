# Spec 契约

## 1. 目标

Spec 是用户需求与 Agent 执行之间的任务契约。它既要让用户能用自然语言修改流程，也要让 Codex 和 Python 工具能稳定执行。

Spec 不应包含 Python 代码，也不应直接写死浏览器操作步骤。它描述的是“要完成什么”和“需要哪些约束”，具体执行由 Skill 完成。

## 2. 文件位置

模板：

```text
specs/templates/daily_report_spec.yaml
```

每次运行：

```text
specs/runs/<run_id>/spec.yaml
```

`specs/runs/` 是运行态目录，默认不进入 git；需要沉淀为长期模板的内容应复制回 `specs/templates/` 或文档。

建议运行目录结构：

```text
specs/runs/<run_id>/
├── spec.yaml
├── trace.jsonl
├── memory_candidates.json
└── outputs/
```

## 3. 生命周期

| 状态 | 含义 |
|------|------|
| `draft` | 由用户需求初步生成，尚未确认。 |
| `ready` | 已可执行。 |
| `running` | Runtime 正在执行。 |
| `needs_confirmation` | 存在需要用户确认的下载、memory 或写表决策。 |
| `completed` | 执行完成。 |
| `failed` | 执行失败，trace 中应有错误详情。 |

## 4. 顶层字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `schema_version` | 是 | 当前为 `1`。 |
| `run_id` | 否 | 运行 ID；模板中可为空。 |
| `status` | 是 | 生命周期状态。 |
| `created_at` | 否 | ISO 8601 时间。 |
| `updated_at` | 否 | ISO 8601 时间。 |
| `user_goal` | 是 | 用户原始目标或整理后的目标。 |
| `constraints` | 否 | 全局约束，如禁止联网、仅使用本地文件。 |
| `inputs` | 是 | 报表、日期、产品、文件等输入要求。 |
| `workflow` | 是 | Skill 调用序列。 |
| `outputs` | 是 | 期望产物。 |
| `memory` | 否 | memory 复用与写入策略。 |
| `trace` | 否 | trace 输出配置。 |

## 5. inputs

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

## 6. workflow

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
- `skill` 必须对应 `src/yield_report/skills/<skill>/`。
- `depends_on` 表示运行顺序依赖。
- `save_as` 表示把结果写入 RunContext，供后续步骤引用。
- `input` 可以引用 `inputs` 中的 alias 或上游 `save_as`。

## 7. outputs

```yaml
outputs:
  daily_report:
    required: true
    format: xlsx
    directory: output
    filename_template: "良率日报_{report_date}_{product_models}.xlsx"
  analysis_summary:
    required: true
    format: markdown
  trace:
    required: true
    format: jsonl
```

## 8. memory

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

## 9. trace

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

## 10. 校验规则

Runtime 执行前必须校验：

- `schema_version` 支持。
- `workflow[*].id` 唯一。
- `workflow[*].skill` 已注册。
- `depends_on` 指向存在的步骤。
- `required` 报表或文件有可执行获取方式。
- `outputs` 至少声明一个最终产物。
- `memory.reuse_policy` 不允许默认复用 pending 记录。

## 11. 最小示例

```yaml
schema_version: 1
run_id: null
status: draft
user_goal: "生成 M678 今天的良率日报，包含近一周 CT 良率趋势"

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
  local_files: []

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

outputs:
  daily_report:
    required: true
    format: xlsx
    directory: output
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
