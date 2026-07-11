# Skill 契约

## 1. 目标

Skill 是本项目面向 Codex 和 Agent Runtime 暴露的稳定能力入口。每个 Skill 都应做到：

- 输入结构化。
- 输出结构化。
- 内部实现可替换。
- 错误可追踪。
- 产物路径可复用。
- 说明文档能被 Codex 快速读取。

## 2. 目录约定

```text
src/yield_report/skills/<skill_name>/
├── SKILL.md
├── models.py
├── tool.py
└── implementation.py
```

可选目录：

```text
analyzers/
templates/
prompts/
fixtures/
```

## 3. 统一接口

```python
from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class SkillTool(Protocol):
    name: str
    description: str

    def run(self, request: BaseModel, context: RunContext) -> SkillResult:
        ...
```

所有 Skill 的 `tool.py` 应暴露：

```python
TOOL_NAME = "report_download"


def run(request: ReportDownloadRequest, context: RunContext) -> SkillResult:
    ...
```

## 4. 核心模型

### 4.1 RunContext

`RunContext` 记录一次任务运行所需的上下文。

| 字段 | 类型 | 说明 |
|------|------|------|
| `run_id` | `str` | 本次任务 ID。 |
| `workspace` | `Path` | 项目根目录。 |
| `spec_path` | `Path | None` | 当前 Spec 路径。 |
| `output_dir` | `Path` | 本次运行产物目录。 |
| `memory` | `AgentMemory | None` | 可选 memory 入口。 |
| `trace` | `TraceWriter | None` | 可选 trace 写入器。 |
| `config` | `dict[str, Any]` | 运行配置快照。 |

### 4.2 SkillResult

`SkillResult` 是 Skill 的统一返回结构。

| 字段 | 类型 | 说明 |
|------|------|------|
| `skill_name` | `str` | Skill 名称。 |
| `success` | `bool` | 是否执行成功。 |
| `summary` | `str` | 人可读摘要。 |
| `artifacts` | `list[ArtifactRef]` | 文件、图表、JSON 等产物引用。 |
| `data` | `dict[str, Any]` | 下游可复用结构化数据。 |
| `warnings` | `list[str]` | 非阻断问题。 |
| `error` | `SkillError | None` | 失败详情。 |
| `memory_updates` | `list[MemoryCandidate]` | 待确认 memory 记录。 |

### 4.3 ArtifactRef

| 字段 | 类型 | 说明 |
|------|------|------|
| `kind` | `str` | `excel`、`json`、`markdown`、`image`、`log` 等。 |
| `path` | `Path` | 产物路径。 |
| `description` | `str` | 产物说明。 |
| `metadata` | `dict[str, Any]` | 筛选条件、表名、sheet、字段等信息。 |

### 4.4 SkillError

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | `str` | 稳定错误码。 |
| `message` | `str` | 人可读错误信息。 |
| `recoverable` | `bool` | Runtime 或 Codex 是否可尝试修复。 |
| `details` | `dict[str, Any]` | 浏览器截图、文件路径、异常栈摘要等。 |

## 5. Skill 文档约定

每个 `SKILL.md` 应包含：

```markdown
# <skill_name>

## When To Use
说明 Codex 何时调用该 Skill。

## Inputs
列出 request 模型字段、默认值和约束。

## Outputs
列出返回产物、结构化数据和 memory 候选。

## Workflow
列出内部步骤，帮助 Codex 判断失败位置。

## Error Handling
列出常见错误码和可恢复方式。

## Examples
给出 2-3 个自然语言需求到 request 的示例。
```

`SKILL.md` 是给 Codex 读的说明，不应替代 `models.py` 中的强类型契约。

## 6. 三个业务 Skill

### 6.1 report_download

职责：根据报表类型、日期范围、产品型号和筛选条件下载或定位源表。

输入模型建议：

| 字段 | 说明 |
|------|------|
| `report_type` | `daily_yield`、`batch_yield`、`ct_exception`、`target_decomposition`、`gap_template`。 |
| `product_models` | 产品型号列表，未指定时允许为空。 |
| `start_date` | 可选开始日期。 |
| `end_date` | 可选结束日期。 |
| `filters` | 额外筛选条件。 |
| `prefer_decrypted` | 是否优先返回解密文件。 |

输出要求：

- 返回下载或定位到的文件路径。
- 返回报表名称、筛选条件、是否解密。
- 下载文件名应包含关键筛选条件。

### 6.2 data_analysis

职责：根据分析目标读取源表、自动解密、选择分析器并输出结论。

输入模型建议：

| 字段 | 说明 |
|------|------|
| `question` | 用户自然语言分析问题。 |
| `report_refs` | 来自 Spec 或上一步下载结果的报表引用。 |
| `product_models` | 产品型号。 |
| `time_range` | 分析时间范围。 |
| `metrics` | 目标指标，如 CT 良率、不良率、Gap。 |
| `analysis_intent` | 趋势、异常、排序、归因、摘要等。 |
| `confirmed_memory_ids` | 允许自动复用的 memory 记录。 |

输出要求：

- 返回分析文本。
- 返回实际使用文件。
- 返回关键中间数据或表格摘要。
- 返回待确认 memory 候选。

### 6.3 daily_report

Runtime boundary: `daily_report` exposes the Agent Runtime interface and delegates execution to the public `$daily-report-generator` CLI. It omits `--workspace` by default so the public CLI uses its installed skill root. Agent integration paths are Pydantic-backed configuration; explicit request fields are compatibility overrides. The wrapper must not contain report-generation business rules, directly call per-task wrapper skills, or depend on internal generator metadata.

职责：调用公共 CLI，解析其 JSON 结果并返回生成的 Excel artifact。

输入模型建议：

| 字段 | 说明 |
|------|------|
| `report_date` | 日报日期。 |
| `generator_root` | 可选公共 skill 安装路径覆盖。 |
| `generator_workspace` | 可选兼容 workspace 覆盖；默认不传。 |
| `generator_now` | 可选显式确定性运行时刻；不得由 `report_date` 推导。 |
| `output_dir` | 可选 Agent 交付目录覆盖。 |

输出要求：

- 返回日报 Excel 路径。
- 返回公共生成器 workflow、warnings 和原始 JSON 摘要。

## 7. 错误码约定

错误码格式：

```text
<skill_name>.<category>.<reason>
```

示例：

| 错误码 | 含义 |
|--------|------|
| `report_download.input.missing_report_type` | 缺少报表类型且无法推断。 |
| `report_download.remote.finereport_timeout` | FineReport 查询或导出超时。 |
| `data_analysis.file.no_matching_report` | 本地和下载链路都未找到匹配报表。 |
| `data_analysis.execution.generated_code_failed` | 生成代码执行失败。 |
| `daily_report.native_pipeline.failed` | 公共 CLI 调用、JSON 解析或文件产物解析失败。 |

## 8. Memory 约定

Skill 只能自动复用 `confirmed` memory。新的候选记录必须以 `pending` 返回，等待用户或 Codex 明确确认。

Memory 候选应包含：

- 用户需求摘要。
- 文件或报表名称。
- 字段映射。
- 筛选条件。
- 分析逻辑或处理方法。
- 适用范围。

## 9. 测试要求

每个 Skill 至少包含：

- request 模型校验测试。
- `tool.run()` 成功路径测试。
- 关键失败路径测试。
- trace 和 artifact 生成测试。
- 与旧 orchestrator 的兼容测试。
