# Codex 可执行重构方案：良率日报自动生成 Agent 架构设计

> 适用项目：`wzygio/excel-generator-project`  
> 适用模块：`src/yield_report/`、`app/`、`docs/agent/`、`specs/`  
> 目标日期：2026-06-03  
> 执行者：Codex / 项目开发者  
> 核心目标：把当前“三个独立 Tab + 直接调用 Skill”的结构，重构为“Spec 驱动的轻量 Agent 工作台”。

---

## 0. 给 Codex 的执行指令

你是本仓库的重构执行 Agent。请严格按本文件执行，不要一次性大改全仓库。

执行前必须阅读：

1. `ARCHITECTURE.md`
2. `docs/agent/architecture.md`
3. `docs/agent/spec_contract.md`
4. `docs/agent/skill_contract.md`
5. `src/yield_report/agent/spec_model.py`
6. `src/yield_report/agent/runtime.py`
7. `src/yield_report/agent/registry.py`
8. `src/yield_report/skills/report_download/`
9. `src/yield_report/skills/data_analysis/`
10. `src/yield_report/skills/daily_report/`
11. `app/main.py`

执行原则：

- 不要删除旧模块。
- 不要破坏现有三个 Skill 的可单独调用能力。
- 不要引入 LangChain、LangGraph、CrewAI 等新框架。
- 不要把 Codex CLI 嵌入 Streamlit UI 作为主执行路径。
- 普通日报生成运行时必须由 Python Runtime 负责。
- Codex 负责开发期重构、失败修复、规则升级和必要代码迭代。
- LLM 负责理解用户需求、生成/修改 Spec、生成分析解释、润色日报文本。
- 代码负责数据获取、文件解析、Excel 读写、确定性计算、路径管理、trace、memory 状态。

每完成一个阶段后，至少运行：

```bash
uv run pytest tests/unit/agent tests/unit/skills -v --tb=short
uv run ruff check .
```

如果阶段涉及 UI，请额外人工烟测：

```bash
uv run streamlit run app/main.py --server.port 8502
```

---

## 1. 最终架构结论

本项目不应该把 Streamlit UI 简化成“给 Codex CLI 输入指令的窗口”，然后让 Codex CLI 在每次用户生成日报时直接接管整个业务运行。

推荐架构是：

```text
用户
  ↓
Streamlit Agent Workbench
  ↓
Spec Draft / Spec Edit / Spec Preview
  ↓
TaskSpec + Rules + Memory
  ↓
AgentRuntime
  ↓
report_download Skill
  ↓
data_analysis Skill
  ↓
daily_report Skill
  ↓
outputs / trace.jsonl / run_summary.md / memory_candidates.json
```

Codex 的定位是独立的开发期/维护期 Agent：

```text
Codex CLI / Codex App / Codex SDK
  ↓
阅读 AGENTS.md、.agents/skills、docs/agent、specs/runs、trace
  ↓
定位失败原因
  ↓
修改 Spec 模板 / Rule YAML / Skill 文档 / Python 代码 / 测试
  ↓
运行测试与提交变更
```

换句话说：

- **日常执行核心**：Python `AgentRuntime`。
- **智能理解核心**：LLM，通过 `LLMManager` 或后续可替换的模型服务。
- **工程迭代核心**：Codex。
- **业务能力入口**：三个 Skill。
- **用户可维护边界**：Spec + Rules + Skill 文档。

---

## 2. 当前项目诊断

当前仓库已经有正确的雏形，但运行链路还没有真正收敛。

### 2.1 已经做对的部分

当前项目已经具备：

```text
src/yield_report/agent/
├── spec_model.py
├── router.py
├── runtime.py
├── memory.py
├── trace.py
└── registry.py

src/yield_report/skills/
├── report_download/
├── data_analysis/
└── daily_report/
```

这说明项目已经从传统横向 DDD 分层，开始转向：

```text
Spec → Runtime → Skill → Result → Trace / Memory / Output
```

这个方向正确。

### 2.2 当前主要问题

#### 问题 A：UI 仍然绕过 Spec 和 Runtime

当前 `app/main.py` 仍然是三个 Tab：

```text
报表下载 Tab     → report_download_tool.run()
数据分析 Tab     → data_analysis_tool.run()
日报生成 Tab     → daily_report_tool.run()
```

它没有把用户需求转换成 `specs/runs/<run_id>/spec.yaml`，也没有通过 `AgentRuntime.run_spec()` 执行完整 workflow。

这会导致：

- 用户无法看到完整任务契约。
- 用户无法用自然语言修正任务流程。
- 每次运行没有统一 run workspace。
- trace 和 memory 无法形成完整闭环。
- 三个模块仍然像三个功能按钮，而不是一个持续运转的 Agent。

#### 问题 B：Router 只是 Spec loader，不是真正的任务路由器

当前 `src/yield_report/agent/router.py` 主要做：

- 读取 YAML；
- Pydantic 校验；
- 检查 workflow step id 和 depends_on。

它还不负责：

- 从自然语言生成 TaskSpec；
- 根据用户修改 patch TaskSpec；
- 根据运行失败修复 TaskSpec；
- 根据历史 Memory 建议 workflow。

这不是错误，但需要补上 `spec_drafter.py` 或类似模块。

#### 问题 C：业务规则仍然大量写死在代码里

例如日报生成和日报分析中存在这类硬编码：

```python
DEFAULT_SECTIONS = ["gap", "trend", "known_exception", "new_exception"]
SOURCE_PATTERNS = {...}
DEFECT_GROUPS = [...]
CONCENTRATION_RULES = {...}
DEFAULT_TEMPLATE = Path(...)
```

这些规则应该迁移到 Rule YAML。

用户应该能够通过修改规则来完成这些微调：

- 增减日报章节；
- 改变源文件匹配模式；
- 修改 Defect Group 解释；
- 修改趋势判断窗口；
- 修改异常匹配窗口；
- 修改文本风格；
- 修改输出文件命名；
- 控制是否启用 LLM 润色。

代码只负责读取、校验、执行这些规则。

#### 问题 D：Data Analysis 的设计方向需要调整为 LLM-first

当前数据分析仍偏向：

```text
需求解析 → 文件定位 → schema → 选择 code / llm_direct → 返回结果
```

对于高度多样化的临时分析需求，优先让 LLM 在受控上下文中分析更合理。

推荐改为：

```text
数据分析请求
  ↓
文件定位 / 解密 / schema / 数据摘要 / 小样本
  ↓
LLM-first 分析
  ↓
必要时才生成 pandas 代码
  ↓
结构化结论 + 证据表 + 可复现摘要
```

不要为每一种临时分析需求都写一个新 analyzer。

#### 问题 E：日报生成的下传与上报机制不够显式

当前 `daily_report` 会内嵌调用 `data_analysis`，`data_analysis` 又可能调用 `report_download`。

这个方向没错，但需要显式化：

```text
向下传递：
Spec.rules / Spec.inputs / Skill request / RunContext.state

向上反馈：
SkillResult.data / artifacts / warnings / error / downstream_results / memory_updates / trace
```

否则后续用户修改规则时，规则无法稳定传递到下游模块。

---

## 3. 修正后的核心架构

### 3.1 双循环架构

本项目应该分为两个循环。

#### 循环 1：业务执行循环

这是用户每天真正使用的链路。

```text
User Goal
  ↓
SpecDrafter 生成或修改 TaskSpec
  ↓
用户确认 Spec
  ↓
AgentRuntime.run_spec()
  ↓
Skill Tool 执行
  ↓
Trace / Artifacts / Memory Candidates
  ↓
用户确认 Memory 或下载日报
```

特点：

- 稳定；
- 可测试；
- 不依赖 Codex 改代码；
- 不允许任意 shell 执行；
- 适合生产使用。

#### 循环 2：工程迭代循环

这是开发者或高级用户用 Codex 维护项目的链路。

```text
用户提出规则/能力变更
  ↓
Codex 阅读 AGENTS.md + Skill 文档 + Spec + Trace
  ↓
判断变更属于 Spec / Rules / Skill Doc / Code
  ↓
修改相应文件
  ↓
运行测试
  ↓
提交或等待人工 review
```

特点：

- Codex 可以改代码；
- 需要 Git diff 和测试；
- 不应该在普通日报生成时自动发生；
- 适合能力升级和失败修复。

---

## 4. Code / LLM / Codex 边界

### 4.1 必须保留为代码的部分

这些流程重复、高频、可测试、出错代价高，必须保留为 Python 代码：

| 类别 | 保留为代码的原因 | 示例 |
|---|---|---|
| 数据获取 | 高频、稳定、依赖账号/内网/RPA | FineReport 下载、网络共享文件定位 |
| 文件处理 | 需要稳定读写和异常处理 | Excel 解密、openpyxl/COM 读取、模板复制 |
| Schema / 摘要 | 需要可控 token 和隐私边界 | sheet 扫描、字段抽取、样本/统计摘要 |
| 确定性计算 | 必须可复现 | Gap 计算、TopN 排序、三日趋势判断 |
| 输出写入 | 必须格式稳定 | Excel 单元格写入、样式、换行 |
| 运行状态 | 必须可恢复 | run_id、trace、artifacts、memory status |
| 安全边界 | 不能靠 prompt | 路径限制、只读/写 output、敏感信息过滤 |
| 测试 | 必须自动回归 | 单测、烟测、fixture |

### 4.2 应交给 LLM 的部分

这些流程高度变化、语言性强、用户表达多样，应该优先交给 LLM：

| 类别 | 交给 LLM 的原因 | 示例 |
|---|---|---|
| 用户需求理解 | 自然语言多样 | “生成昨天 M678 的日报，异常部分写详细点” |
| Spec 生成/修改 | 用户不应手写完整 YAML | 从需求生成 workflow |
| 分析路径选择 | 临时分析需求多样 | 判断趋势、归因、异常、摘要 |
| 解释与报告文本 | 语言表达灵活 | 日报段落、异常说明、谨慎结论 |
| 数据不足说明 | 需要语义判断 | “因缺少 CT 异常表，仅输出已知数据” |
| Memory 候选生成 | 需要概括经验 | 字段映射、用户习惯、分析偏好 |

### 4.3 交给 Codex 的部分

Codex 不应该是普通日报生成的主执行器，而应该是项目维护者：

| 任务 | 是否交给 Codex | 说明 |
|---|---:|---|
| 每天一键生成日报 | 否 | 由 Python Runtime 执行 |
| 从用户需求生成 Spec | 可选 | 优先用普通 LLM；复杂修复可让 Codex 参与 |
| 修改 Rule YAML | 是 | Codex 可根据用户指令修改规则 |
| 修改 Skill 文档 | 是 | Codex 可更新 `SKILL.md` |
| 修复失败代码 | 是 | Codex 根据 trace 和测试修复 |
| 新增稳定 analyzer | 是 | 只有高频需求才沉淀为代码 |
| 重构 UI / Runtime | 是 | 开发期任务 |
| 任意 shell 执行生产任务 | 否 | 普通用户路径不应开放 |

---

## 5. 目标目录结构

请逐步调整为以下结构。

```text
excel-generator-project/
├── AGENTS.md
├── .agents/
│   └── skills/
│       └── yield-report-agent/
│           └── SKILL.md
├── app/
│   └── main.py
├── docs/
│   └── agent/
│       ├── architecture.md
│       ├── spec_contract.md
│       ├── skill_contract.md
│       └── rule_contract.md              # 新增
├── rules/
│   ├── daily_report_rules.yaml           # 新增
│   └── data_analysis_rules.yaml          # 可选新增
├── specs/
│   ├── templates/
│   │   └── daily_report_spec.yaml
│   └── runs/
│       └── <run_id>/
│           ├── spec.yaml
│           ├── trace.jsonl
│           ├── run_summary.md
│           ├── memory_candidates.json
│           └── outputs/
├── src/yield_report/
│   ├── agent/
│   │   ├── spec_model.py
│   │   ├── spec_drafter.py               # 新增
│   │   ├── run_workspace.py              # 新增
│   │   ├── router.py
│   │   ├── runtime.py
│   │   ├── registry.py
│   │   ├── memory.py
│   │   ├── trace.py
│   │   └── cli.py                        # 新增，可选
│   ├── rules/
│   │   ├── __init__.py
│   │   ├── models.py                     # 新增
│   │   └── loader.py                     # 新增
│   ├── skills/
│   │   ├── report_download/
│   │   ├── data_analysis/
│   │   └── daily_report/
│   ├── application/                      # 兼容层，暂保留
│   ├── core/                             # 兼容层，暂保留
│   └── infrastructure/                   # 兼容层，暂保留
└── tests/
    ├── unit/
    │   ├── agent/
    │   ├── rules/
    │   └── skills/
    └── integration/
```

---

## 6. 阶段化重构任务

## Phase 0：让 Codex 真正理解项目

### 目标

新增 Codex 入口文档，避免 Codex 每次从零理解仓库。

### 新增文件：`AGENTS.md`

```markdown
# excel-generator-project Agent Guide

## Project Goal

This repository builds a yield daily report Agent. The user-facing workflow is:

1. Download or locate source reports.
2. Analyze yield data.
3. Generate a final Excel daily report.

## Architecture

The target architecture is Spec-driven and Skill-based:

User Goal -> TaskSpec -> AgentRuntime -> Skill Tool -> SkillResult -> Trace / Memory / Output

## Important Files

- `ARCHITECTURE.md`: current architecture overview.
- `docs/agent/architecture.md`: target Agent architecture.
- `docs/agent/spec_contract.md`: TaskSpec contract.
- `docs/agent/skill_contract.md`: Skill contract.
- `rules/daily_report_rules.yaml`: user-editable daily report rules.
- `specs/templates/daily_report_spec.yaml`: default Spec template.
- `src/yield_report/agent/`: Python runtime, spec, trace, memory.
- `src/yield_report/skills/`: business capability tools.
- `app/main.py`: Streamlit Agent workbench.

## Rules

- Do not remove legacy modules until tests prove the new path is stable.
- Do not introduce LangChain, LangGraph, or CrewAI unless explicitly requested.
- Do not embed Codex CLI as the normal runtime path inside Streamlit.
- Keep stable IO, Excel processing, deterministic calculations, trace, and memory in Python.
- Use LLM for user intent, Spec drafting, text generation, and flexible analysis.
- Use Codex for development-time refactoring, rule updates, and code repair.

## Before Editing

Read:

1. `docs/agent/architecture.md`
2. `docs/agent/spec_contract.md`
3. `docs/agent/skill_contract.md`
4. This `AGENTS.md`

## Validation

Run:

```bash
uv run pytest tests/unit/agent tests/unit/skills -v --tb=short
uv run ruff check .
```

For UI changes:

```bash
uv run streamlit run app/main.py --server.port 8502
```
```

### 新增文件：`.agents/skills/yield-report-agent/SKILL.md`

```markdown
---
name: yield-report-agent
summary: Work on the yield daily report Agent using Spec, Skill, Rule YAML, Runtime, Trace, and Memory contracts.
---

# Yield Report Agent Skill

## When To Use

Use this skill when the user asks to:

- Modify the yield daily report Agent architecture.
- Add or change report generation rules.
- Debug a failed daily report run.
- Update `specs/templates/daily_report_spec.yaml`.
- Update `rules/daily_report_rules.yaml`.
- Refactor `src/yield_report/agent/` or `src/yield_report/skills/`.
- Add tests for the Spec/Skill/Runtime path.

## Required Reading

Before changing code, read:

1. `AGENTS.md`
2. `ARCHITECTURE.md`
3. `docs/agent/architecture.md`
4. `docs/agent/spec_contract.md`
5. `docs/agent/skill_contract.md`
6. `rules/daily_report_rules.yaml` if it exists
7. The relevant Skill directory under `src/yield_report/skills/`

## Architecture Boundary

Runtime path:

User Goal -> Spec -> AgentRuntime -> Skills -> Outputs

Development path:

User Change Request -> Codex -> update Rule YAML / Skill docs / code / tests

Do not make Codex CLI the normal Streamlit runtime.

## Code vs Rules

Move user-editable business rules into YAML when possible:

- sections
- source file patterns
- defect groups
- concentration reasons
- trend windows
- exception windows
- text style rules
- output naming

Keep these in Python:

- file download
- decryption
- schema extraction
- deterministic calculations
- Excel writing
- trace
- memory persistence
- validation

## Validation

After changes run:

```bash
uv run pytest tests/unit/agent tests/unit/skills -v --tb=short
uv run ruff check .
```

If modifying daily report behavior, add or update tests under:

```text
tests/unit/rules/
tests/unit/skills/test_daily_report_skill.py
tests/integration/
```
```

### 验收标准

- `AGENTS.md` 存在。
- `.agents/skills/yield-report-agent/SKILL.md` 存在。
- Codex 能通过这两个文件快速理解项目边界。
- 不影响现有测试。

---

## Phase 1：把日报业务规则从代码迁移到 YAML

### 目标

把用户可能频繁修改、但不应该改 Python 的规则外置。

### 新增文件：`docs/agent/rule_contract.md`

```markdown
# Rule 契约

Rule 是用户可维护的业务规则配置。Rule 不包含 Python 代码，不表达浏览器点击步骤，只表达业务约束、匹配规则、文本规则和计算参数。

## 位置

默认日报规则：

```text
rules/daily_report_rules.yaml
```

运行时 Spec 可通过：

```yaml
rules:
  daily_report: rules/daily_report_rules.yaml
```

引用规则文件。

## 设计原则

- Rule 可由用户或 Codex 修改。
- Rule 必须经过 Pydantic 校验。
- Rule 不能包含任意代码。
- Rule 只能影响已定义边界内的行为。
- 超出 Rule 能力的修改，必须由 Codex 修改 Skill 或 Python 代码。
```

### 新增文件：`rules/daily_report_rules.yaml`

```yaml
schema_version: 1
name: daily_report_rules

sections:
  enabled:
    - gap
    - trend
    - known_exception
    - new_exception
  required:
    - gap
    - trend
    - known_exception
    - new_exception

source_files:
  search_dirs:
    - resources
    - docs/project_files
  aliases:
    spotfire:
      required: true
      patterns:
        - "spotfire*.xlsx"
      default_sheet: "Sheet1"
    daily_yield:
      required: true
      patterns:
        - "V3良率及不良率By月周天*.xlsx"
      default_sheet: "CT"
      downloadable: true
      report_type: daily_yield
    target_decomposition:
      required: false
      patterns:
        - "*良率目标拆解*.xlsx"
      downloadable: true
      report_type: target_decomposition
    gap_template:
      required: false
      patterns:
        - "*Gap分析模板*.xlsx"
        - "日良率Gap分析模板*.xlsx"
      downloadable: true
      report_type: gap_template
    ct_exception:
      required: false
      patterns:
        - "CT良率异常波动管理表*.xlsx"
      default_sheet: "CT异常波动调查"
      downloadable: true
      report_type: ct_exception
    code_mapping:
      required: false
      patterns:
        - "大数据值班当日新增不良HL模板*.xlsx"
      default_sheet: "Code归属表"

product_selection:
  source_alias: spotfire
  match_report_date: true
  allow_product_model_filter: true

trend:
  ct_yield_metric_name: "CT良率"
  mvi_share_metric_name: "CT产出数_MVI产出占比"
  consecutive_days: 3
  decline_rule: strictly_descending
  mvi_increase_rule: strictly_ascending
  insufficient_data_policy: skip_with_warning

exceptions:
  known_exception_window_days: 30
  new_exception_window_days: 1
  match_by_product_model: true
  match_by_top_defect_codes: true

text_generation:
  use_llm_polishing_default: false
  style:
    language: zh-CN
    tone: concise_engineering
    avoid_overclaiming: true
    mention_missing_data: true

output:
  default_template: docs/project_files/V3良率日报每日异常填报表.xlsx
  filename_template: "良率日报_{report_date}.xlsx"
  emit_intermediate_artifacts: true

defect_groups:
  - Array_AD
  - Array_Line
  - Array_Mura
  - Array_Pixel
  - ARRAY_RS查杀
  - ARRAY其他
  - CELL其他
  - OLED_Mura
  - OLED_RS查杀
  - OLED其他
  - OLED_色偏
  - TP_RS查杀
  - TP_Short NG
  - TP其他
  - TP 容值NG
  - 外观不良

concentration_rules:
  Array_AD: "受SCA R品集中过货影响"
  Array_Line: "受ACA R品集中过货影响"
  Array_Mura: "受MVI集中过货影响"
  Array_Pixel: "受MVI集中过货影响"
  ARRAY_RS查杀: "受CUT站点新批次刚刚投入影响"
  ARRAY其他: "受MVI集中过货影响"
  CELL其他: "受MVI集中过货影响"
  OLED_Mura: "受MVI集中过货影响"
  OLED_RS查杀: "受CUT站点新批次刚刚投入影响"
  OLED其他: "受CUT站点新批次刚刚投入影响"
  OLED_色偏: "受MVI集中过货影响"
  TP_RS查杀: "受CUT站点新批次刚刚投入影响"
  TP_Short NG: "受35001站点集中过货影响"
  TP其他: "受MVI集中过货影响"
  TP 容值NG: "受35006站点集中过货影响"
  外观不良: "受APP1站点新批次刚刚投入影响"
```

### 新增包：`src/yield_report/rules/`

#### `src/yield_report/rules/__init__.py`

```python
"""Business rule loading and validation for yield_report."""
```

#### `src/yield_report/rules/models.py`

实现 Pydantic 模型，至少包括：

```python
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class SourceAliasRule(BaseModel):
    required: bool = False
    patterns: list[str] = Field(default_factory=list)
    default_sheet: str | None = None
    downloadable: bool = False
    report_type: str | None = None


class SourceFilesRule(BaseModel):
    search_dirs: list[Path] = Field(default_factory=lambda: [Path("resources")])
    aliases: dict[str, SourceAliasRule] = Field(default_factory=dict)


class SectionsRule(BaseModel):
    enabled: list[str] = Field(default_factory=list)
    required: list[str] = Field(default_factory=list)


class TrendRule(BaseModel):
    ct_yield_metric_name: str = "CT良率"
    mvi_share_metric_name: str = "CT产出数_MVI产出占比"
    consecutive_days: int = 3
    decline_rule: Literal["strictly_descending"] = "strictly_descending"
    mvi_increase_rule: Literal["strictly_ascending"] = "strictly_ascending"
    insufficient_data_policy: str = "skip_with_warning"


class ExceptionsRule(BaseModel):
    known_exception_window_days: int = 30
    new_exception_window_days: int = 1
    match_by_product_model: bool = True
    match_by_top_defect_codes: bool = True


class TextGenerationRule(BaseModel):
    use_llm_polishing_default: bool = False
    style: dict[str, object] = Field(default_factory=dict)


class OutputRule(BaseModel):
    default_template: Path = Path("docs/project_files/V3良率日报每日异常填报表.xlsx")
    filename_template: str = "良率日报_{report_date}.xlsx"
    emit_intermediate_artifacts: bool = True


class DailyReportRules(BaseModel):
    schema_version: int = 1
    name: str = "daily_report_rules"
    sections: SectionsRule = Field(default_factory=SectionsRule)
    source_files: SourceFilesRule = Field(default_factory=SourceFilesRule)
    product_selection: dict[str, object] = Field(default_factory=dict)
    trend: TrendRule = Field(default_factory=TrendRule)
    exceptions: ExceptionsRule = Field(default_factory=ExceptionsRule)
    text_generation: TextGenerationRule = Field(default_factory=TextGenerationRule)
    output: OutputRule = Field(default_factory=OutputRule)
    defect_groups: list[str] = Field(default_factory=list)
    concentration_rules: dict[str, str] = Field(default_factory=dict)
```

#### `src/yield_report/rules/loader.py`

```python
from __future__ import annotations

from pathlib import Path

import yaml

from yield_report.rules.models import DailyReportRules


DEFAULT_DAILY_REPORT_RULES = Path("rules/daily_report_rules.yaml")


class RuleLoadError(Exception):
    """Raised when a rule file cannot be loaded or validated."""


def load_daily_report_rules(
    path: Path | str | None = None,
    *,
    workspace: Path | None = None,
) -> DailyReportRules:
    workspace = workspace or Path.cwd()
    rule_path = Path(path or DEFAULT_DAILY_REPORT_RULES)
    if not rule_path.is_absolute():
        rule_path = workspace / rule_path

    if not rule_path.exists():
        raise RuleLoadError(f"Daily report rule file not found: {rule_path}")

    try:
        raw = yaml.safe_load(rule_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise RuleLoadError(f"Failed to read rule file: {rule_path}") from exc

    if not isinstance(raw, dict):
        raise RuleLoadError("Daily report rule root must be a YAML mapping")

    try:
        return DailyReportRules(**raw)
    except Exception as exc:
        raise RuleLoadError(f"Daily report rule validation failed: {exc}") from exc
```

### 修改点

把 `daily_report/implementation.py` 和 `data_analysis/daily_report_analysis.py` 中的以下常量替换为规则读取：

- `DEFAULT_SECTIONS`
- `SOURCE_PATTERNS`
- `DEFECT_GROUPS`
- `CONCENTRATION_RULES`
- `DEFAULT_TEMPLATE`
- 趋势判断窗口
- 异常匹配窗口

不要一次性删除原常量。可以先保留 fallback，但优先读取 Rule YAML。

### 验收标准

- 修改 `rules/daily_report_rules.yaml` 的 `sections.enabled` 后，日报生成使用新章节列表。
- 修改 `concentration_rules` 后，日报文案中的集中原因随之变化。
- 修改 `output.filename_template` 后，输出文件名随之变化。
- 所有规则修改不需要改 Python。

---

## Phase 2：新增 SpecDrafter，让用户自然语言变成 TaskSpec

### 目标

普通用户不应该手写完整 YAML。系统应根据自然语言生成草稿 Spec，并允许用户二次修改。

### 新增文件：`src/yield_report/agent/spec_drafter.py`

职责：

1. `draft_spec_from_goal(user_goal: str, run_id: str, workspace: Path) -> TaskSpec`
2. `patch_spec_from_feedback(spec: TaskSpec, feedback: str) -> TaskSpec`
3. `render_spec_yaml(spec: TaskSpec) -> str`
4. `save_spec(spec: TaskSpec, path: Path) -> None`

实现建议：

- 使用现有 `shared_kernel.infrastructure.llm_handler.LLMManager`。
- 要求 LLM 只输出 JSON 或 YAML。
- 用 `TaskSpec` Pydantic 模型二次校验。
- 失败时返回可读错误，不直接执行。
- 默认生成日报 workflow：

```yaml
workflow:
  - id: generate_daily_report
    skill: daily_report
    input:
      spec_path: <current_spec_path>
      report_date: <date or null>
      product_models: <models or null>
      output_dir: output
      emit_intermediate_artifacts: true
    save_as: daily_report_file
```

为什么默认只调用 `daily_report`？

因为当前业务链路已经是：

```text
daily_report → data_analysis → report_download
```

如果在 Spec 中同时显式写三步，容易和代码内嵌链路重复。第一版推荐：

- 日报任务：Spec 只调用 `daily_report`。
- 单独下载任务：Spec 调用 `report_download`。
- 单独分析任务：Spec 调用 `data_analysis`。

这样更简单，也符合用户说的“Agent 非常简单”。

### SpecDrafter Prompt 要点

System prompt 应写清楚：

```text
你是良率日报 TaskSpec 生成器。
只生成 TaskSpec，不写 Python 代码。
不要描述浏览器操作。
不要编造文件路径。
如果信息缺失，将字段设为 null 或空列表，并在 constraints/notes 中记录。
日报生成优先调用 daily_report skill，由 daily_report 内部调用 data_analysis 和 report_download。
```

### 验收标准

输入：

```text
生成 M678 今天的良率日报，异常分析写详细一点，输出 Excel 和 Markdown。
```

应生成类似：

```yaml
schema_version: 1
run_id: ui-20260603-xxxxxx
status: draft
user_goal: "生成 M678 今天的良率日报，异常分析写详细一点，输出 Excel 和 Markdown。"
constraints:
  text_style: "异常分析写详细一点"
inputs:
  report_date: null
  product_models:
    - M678
  local_files: []
rules:
  daily_report: rules/daily_report_rules.yaml
workflow:
  - id: generate_daily_report
    skill: daily_report
    input:
      spec_path: specs/runs/ui-20260603-xxxxxx/spec.yaml
      report_date: null
      product_models:
        - M678
      output_dir: specs/runs/ui-20260603-xxxxxx/outputs
      emit_intermediate_artifacts: true
    save_as: daily_report_file
outputs:
  daily_report:
    required: true
    format: xlsx
  analysis_summary:
    required: true
    format: markdown
trace:
  path: specs/runs/ui-20260603-xxxxxx/trace.jsonl
memory:
  reuse_policy: confirmed_only
  candidate_policy: record_pending
```

---

## Phase 3：Run Workspace 标准化

### 目标

每次运行都创建独立目录，避免输出、日志、trace 混在一起。

### 新增文件：`src/yield_report/agent/run_workspace.py`

职责：

```python
create_run_id(prefix: str = "ui") -> str
create_run_workspace(run_id: str, workspace: Path) -> RunWorkspace
write_run_summary(...)
write_memory_candidates(...)
```

建议模型：

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class RunWorkspace:
    run_id: str
    root: Path
    spec_path: Path
    trace_path: Path
    output_dir: Path
    memory_candidates_path: Path
    run_summary_path: Path


def create_run_id(prefix: str = "ui") -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def create_run_workspace(run_id: str, workspace: Path | None = None) -> RunWorkspace:
    workspace = workspace or Path.cwd()
    root = workspace / "specs" / "runs" / run_id
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    return RunWorkspace(
        run_id=run_id,
        root=root,
        spec_path=root / "spec.yaml",
        trace_path=root / "trace.jsonl",
        output_dir=output_dir,
        memory_candidates_path=root / "memory_candidates.json",
        run_summary_path=root / "run_summary.md",
    )
```

### 修改 Runtime

`AgentRuntime.run_spec()` 应：

- 使用 `context.output_dir`；
- 如果 `spec.trace.path` 不是绝对路径，要相对 workspace 解析；
- 每步开始/成功/失败都写 trace；
- 失败时停止并返回已完成结果；
- 将 `memory_updates` 写入 `memory_candidates.json`；
- 生成 `run_summary.md`。

### 验收标准

执行一次 UI 日报生成后，必须出现：

```text
specs/runs/<run_id>/
├── spec.yaml
├── trace.jsonl
├── run_summary.md
├── memory_candidates.json
└── outputs/
    ├── 良率日报_*.xlsx
    ├── 良率日报_*.json
    └── 良率日报_*.md
```

---

## Phase 4：把 Streamlit 重构为 Agent Workbench

### 目标

从三个 Tab 收敛为一个 Agent 工作台。

### 推荐 UI

```text
良率日报 Agent 工作台

[用户需求输入框]

按钮：
- 生成 / 更新 Spec
- 执行当前 Spec
- 下载日报
- 确认 Memory
- 拒绝 Memory

区域：
- Spec 预览 / 可编辑 YAML
- 运行步骤 / trace
- 结果摘要
- 产物下载
- Memory 候选
- 日志

兼容入口：
- 报表下载
- 数据分析
- 日报生成
```

第一版可以保留旧三个 Tab，但默认首页必须是 Agent Workbench。

### 修改 `app/main.py`

新增函数建议：

```python
def _render_agent_workbench() -> None:
    ...

def _draft_or_patch_spec(user_goal: str, current_spec_text: str | None) -> str:
    ...

def _run_current_spec(spec_text: str) -> SkillResult | list[SkillResult]:
    ...

def _format_trace(trace_path: Path) -> str:
    ...

def _render_artifact_downloads(artifacts: list[ArtifactRef]) -> None:
    ...
```

UI 执行链路：

```text
用户输入需求
  ↓
点击“生成 / 更新 Spec”
  ↓
SpecDrafter 生成 specs/runs/<run_id>/spec.yaml
  ↓
页面展示 YAML
  ↓
用户可直接编辑 YAML
  ↓
点击“执行当前 Spec”
  ↓
load_task_spec()
  ↓
build_default_runtime().run_spec()
  ↓
展示 trace、result、artifacts、memory candidates
```

### 验收标准

- 正常路径不再直接调用 `daily_report_tool.run()`。
- 正常路径必须先生成或加载 Spec。
- 用户能看到并编辑 YAML。
- 执行后能看到 trace 和产物。
- 旧 Tab 可以保留，但标记为“兼容入口”。

---

## Phase 5：显式化规则下传与结果上报

### 目标

保证：

```text
Spec → daily_report → data_analysis → report_download
```

中的规则、上下文和结果能稳定传递。

### 下传机制

#### 1. Spec 顶层增加 rules 字段

修改 `TaskSpec`：

```python
rules: dict[str, Any] = Field(default_factory=dict)
```

示例：

```yaml
rules:
  daily_report: rules/daily_report_rules.yaml
```

#### 2. DailyReportRequest 增加 rule_path

修改 `DailyReportRequest`：

```python
rule_path: Path | None = None
rule_overrides: dict[str, Any] = Field(default_factory=dict)
```

解析优先级：

```text
request.rule_path
  > spec.rules.daily_report
  > rules/daily_report_rules.yaml
```

#### 3. DataAnalysisRequest 增加 rules/context 字段

```python
rules: dict[str, Any] = Field(default_factory=dict)
parent_step_id: str | None = None
```

`daily_report` 调用 `data_analysis` 时传入：

- sections；
- source_files；
- product list；
- rule-derived trend config；
- exception config；
- text_generation style。

#### 4. ReportDownloadRequest 保持简单

`report_download` 不需要知道全部规则，只需要明确：

- report_type；
- product_models；
- start_date / end_date；
- filters。

### 上报机制

每个 SkillResult 必须包含：

```text
summary
artifacts
data
warnings
error
memory_updates
```

`daily_report` 的 `data` 必须包含：

```json
{
  "report_date": "...",
  "products": [...],
  "source_files": {...},
  "daily_report_facts": {...},
  "downstream_results": [...],
  "blocked_sections": [...],
  "rules_used": {...}
}
```

`downstream_results` 中记录：

```json
{
  "skill": "data_analysis",
  "step": "daily_report_structured_analysis",
  "success": true,
  "summary": "...",
  "artifacts": [...],
  "warnings": [...],
  "error": null
}
```

### 验收标准

- 修改 `rules/daily_report_rules.yaml` 后，规则能影响 daily_report 和 data_analysis。
- 失败时 `blocked_sections` 能指出哪个产品、哪个章节、缺少什么数据。
- `run_summary.md` 能展示下游调用结果。

---

## Phase 6：Data Analysis 改为 LLM-first 泛化分析

### 目标

让数据分析适应多样化需求，而不是为每一种需求编写 analyzer。

### 推荐策略

保留两类分析路径：

```text
1. structured_daily_report
   - 服务 daily_report
   - 可保留确定性代码
   - 高稳定性、高复现性

2. generic_llm_analysis
   - 服务用户临时分析
   - LLM-first
   - 先构建数据上下文，再由 LLM 分析
```

### 新增/重构组件

建议新增：

```text
src/yield_report/skills/data_analysis/
├── context_builder.py
├── llm_analysis.py
└── python_analysis_sandbox.py    # 可选，只有必要时使用
```

#### `context_builder.py`

职责：

- 定位 Excel 文件；
- 解密；
- 读取 sheet 列表；
- 抽取 schema；
- 抽样行；
- 计算基本统计；
- 在 token budget 内构建数据摘要。

输出：

```python
class DataContext(BaseModel):
    files: list[str]
    sheets: list[SheetSummary]
    candidate_metrics: list[str]
    product_models: list[str]
    date_columns: list[str]
    samples: dict[str, list[dict[str, Any]]]
    statistics: dict[str, Any]
    warnings: list[str]
```

#### `llm_analysis.py`

职责：

- 接收 `question + DataContext + confirmed_memory`；
- 输出结构化分析结果；
- 明确证据来自哪些文件、sheet、字段；
- 不足时说明缺失信息；
- 生成 memory candidate。

输出结构：

```python
class LLMAnalysisOutput(BaseModel):
    answer: str
    evidence: list[dict[str, Any]]
    assumptions: list[str]
    missing_data: list[str]
    confidence: str
    suggested_followups: list[str]
    memory_candidates: list[MemoryCandidate]
```

#### 什么时候生成 pandas 代码？

只有当 LLM 判断需要精确计算且 DataContext 不足时，才使用 Python：

```text
需要代码的场景：
- 大量行聚合；
- 多 sheet join；
- 精确 TopN；
- 复杂过滤；
- 需要复现表格。

不需要代码的场景：
- 解释趋势；
- 小样本判断；
- 异常摘要；
- 规则说明；
- 文本报告。
```

### 验收标准

- 用户提出未预设过的分析问题时，系统可以走 LLM-first 分析。
- 不需要新增 analyzer 也能返回可读结论。
- 回答必须列出使用的数据文件和字段。
- 对无法判断的内容必须明确说明缺失信息。

---

## Phase 7：Memory 最小可用化

### 目标

不要引入复杂外部 memory 项目，先用本项目现有 JSON-backed memory 做最小闭环。

### Memory 状态

```text
pending      候选，不能自动复用
confirmed    已确认，可以自动复用
rejected     已拒绝，不能复用
```

### 建议目录

```text
resources/memory/
├── analysis_memory.json
├── report_rules_memory.json
└── user_preferences.json
```

### 允许记忆的内容

- 文件别名与真实路径模式；
- 字段映射；
- 用户常用产品型号；
- 用户偏好的日报文案风格；
- 已确认的异常解释模板；
- 已确认的分析流程。

### 禁止自动记忆的内容

- FineReport 账号密码；
- 内网地址 token；
- 未经确认的业务结论；
- 某次异常的临时判断；
- 可能误导后续分析的猜测。

### UI 行为

当 `SkillResult.memory_updates` 非空时：

- 显示候选摘要；
- 提供“确认/拒绝”按钮；
- 确认后写入 confirmed；
- 拒绝后写入 rejected；
- trace 记录操作。

### 验收标准

- pending memory 不会自动复用。
- confirmed memory 可在下一次分析中显示“已复用 memory: record_id + reason”。
- 用户能在 UI 确认/拒绝。

---

## Phase 8：Codex 迭代机制

### 目标

实现用户“自然语言维护项目”的合理边界。

用户可以说：

```text
以后日报趋势判断改成看最近 5 天，不要只看 3 天。
```

系统或 Codex 应判断：

- 这属于 Rule 修改；
- 修改 `rules/daily_report_rules.yaml`；
- 不改 Python。

用户也可以说：

```text
新增一个章节，分析蒸镀设备腔体 drift 对良率的影响。
```

系统或 Codex 应判断：

- 当前 Rule 不足以完成；
- 需要新增数据源、字段定义、分析逻辑；
- 可能需要新 Skill 或 data_analysis 子能力；
- 需要 Codex 改代码和测试；
- 普通 UI 不应自动执行代码修改。

### 修改边界判定

| 用户需求 | 修改位置 | 是否需要 Codex 改代码 |
|---|---|---:|
| 改趋势天数 3 → 5 | Rule YAML | 否 |
| 改日报文本风格 | Rule YAML / Spec | 否 |
| 增加/关闭已有章节 | Rule YAML / Spec | 否 |
| 改输出文件名 | Rule YAML / Spec | 否 |
| 改 Defect Group 解释 | Rule YAML | 否 |
| 新增源表类型 | Skill model + implementation + tests | 是 |
| 新增复杂分析算法 | data_analysis 代码或 prompts + tests | 可能 |
| 改 Excel 写入区域 | Rule YAML 可表达则否，否则代码 | 可能 |
| 改 FineReport 页面操作 | RPA adapter 代码 | 是 |
| 新增跨系统 API | MCP/adapter/tool | 是 |

### Codex 工作流

```text
用户提出维护需求
  ↓
Codex 判断修改类别
  ↓
Rule-only：修改 YAML + 跑规则测试
  ↓
Skill-doc：修改 SKILL.md + docs
  ↓
Code：修改 Python + tests
  ↓
运行测试
  ↓
输出 diff 摘要
```

### 验收标准

- Codex 不会为了简单规则变化修改 Python。
- Codex 修改代码时必须补测试。
- Rule-only 修改能由用户自己完成。

---

## Phase 9：测试与验收

### 9.1 单元测试

新增或更新：

```text
tests/unit/rules/test_daily_report_rules.py
tests/unit/agent/test_run_workspace.py
tests/unit/agent/test_spec_drafter.py
tests/unit/agent/test_runtime_run_workspace.py
tests/unit/skills/test_daily_report_skill.py
tests/unit/skills/test_data_analysis_skill.py
tests/unit/skills/test_report_download_skill.py
```

### 9.2 集成测试

新增：

```text
tests/integration/test_daily_report_spec_workflow.py
```

测试目标：

1. 给定本地 fixture 文件；
2. 创建 `TaskSpec`；
3. 执行 `build_default_runtime().run_spec()`；
4. 验证输出 Excel/JSON/Markdown；
5. 验证 trace.jsonl 包含 step started/succeeded；
6. 验证 run_summary.md 存在。

### 9.3 手动烟测

```bash
uv run streamlit run app/main.py --server.port 8502
```

手动输入：

```text
生成今天的良率日报，包含 Gap、趋势、已知异常和新增异常。异常说明写得谨慎一点。
```

期望：

- UI 生成 Spec；
- 用户可以看到 YAML；
- 点击执行后生成 run 目录；
- 输出日报 Excel；
- 可下载 Markdown/JSON；
- 显示 trace；
- 如缺少数据，显示 blocked sections，而不是静默失败。

### 9.4 必跑命令

```bash
uv run pytest tests/unit/agent tests/unit/rules tests/unit/skills -v --tb=short
uv run ruff check .
uv run pyright
```

---

## 10. 第一版最终验收标准

完成本重构后，项目必须满足：

1. **架构入口统一**  
   正常 UI 路径从用户需求生成 Spec，再由 Runtime 执行 Skill。

2. **Codex 定位正确**  
   Codex 用于开发期、维护期、失败修复，不作为普通日报生成的嵌入式主 runtime。

3. **用户可维护规则**  
   用户可以通过 `rules/daily_report_rules.yaml` 调整趋势天数、章节、Defect Group 解释、文本风格、输出命名等。

4. **Skill 边界清晰**  
   `report_download`、`data_analysis`、`daily_report` 仍可独立调用。

5. **下传与上报完善**  
   `daily_report → data_analysis → report_download` 的调用链中，规则、源文件、产品、日期、warnings、artifacts、errors 都能结构化传递。

6. **Trace 完整**  
   每次运行必须产生 `trace.jsonl`。

7. **产物可追踪**  
   每次运行必须记录输出 Excel/JSON/Markdown 的路径。

8. **Memory 安全**  
   只自动复用 confirmed memory；pending memory 必须用户确认。

9. **Data Analysis 更灵活**  
   临时、多样化分析需求优先走 LLM-first，而不是每次开发新 analyzer。

10. **不引入重型框架**  
   第一版不引入 LangChain/LangGraph/CrewAI。

---

## 11. 推荐实施顺序

请按以下顺序执行：

```text
P0 Codex 项目入口文档
  ↓
P1 Rule YAML + rule loader
  ↓
P3 Run Workspace
  ↓
P5 规则下传与结果上报
  ↓
P4 Streamlit Agent Workbench
  ↓
P2 SpecDrafter
  ↓
P6 Data Analysis LLM-first
  ↓
P7 Memory 最小闭环
  ↓
P8 Codex 迭代机制
```

原因：

- 先做 Codex 文档，后续执行更稳定。
- 先把规则外置，立刻提升灵活性。
- 再做 run workspace，方便调试和 trace。
- 再改 UI，否则 UI 会缺少底层支撑。
- SpecDrafter 可晚一点，因为第一版可以先手写或模板生成 Spec。
- Data Analysis LLM-first 是能力升级，放在主流程稳定之后。

---

## 12. 不建议做的事情

### 12.1 不建议把 Codex CLI 直接嵌入 Streamlit 主流程

原因：

- Codex CLI 是强大的开发/执行 Agent，但普通日报生成不应该依赖一个能改代码、跑 shell 的通用 coding agent。
- Streamlit 调 subprocess 管理 Codex CLI 会带来权限、超时、日志、状态恢复、成本和安全问题。
- 普通日报生成流程完全可以由 Python Runtime 稳定完成。

### 12.2 不建议立即引入 LangChain / LangGraph

原因：

- 当前 workflow 很简单。
- 已经有轻量 `AgentRuntime`。
- 引入重型框架会增加学习、调试和迁移成本。
- 未来如果出现复杂条件分支、多 Agent 协作、人类审批图，再考虑 LangGraph 或 OpenAI Agents SDK。

### 12.3 不建议把所有分析都沉淀为代码

原因：

- 用户的数据分析需求高度多样。
- 每种需求都写 analyzer 会造成开发成本爆炸。
- 更合理的策略是：高频固定日报逻辑代码化，临时分析 LLM-first。

### 12.4 不建议让 LLM 直接处理所有原始 Excel

原因：

- token 成本高；
- 容易漏字段；
- 无法稳定复现；
- 可能泄露敏感信息；
- 大文件不可控。

正确做法：

```text
代码构建数据上下文 → LLM 分析上下文 → 必要时由代码精确计算
```

---

## 13. 最小可交付版本定义

如果时间有限，只做下面 5 件事即可形成明显改进：

1. 新增 `AGENTS.md` 和 `.agents/skills/yield-report-agent/SKILL.md`。
2. 新增 `rules/daily_report_rules.yaml` 和 rule loader。
3. 修改 `daily_report` / `daily_report_analysis` 读取 Rule YAML。
4. 新增 run workspace，让每次运行落到 `specs/runs/<run_id>/`。
5. 修改 Streamlit：新增“Agent 工作台”，至少支持加载/编辑/执行 Spec。

这 5 件事完成后，项目就从“功能按钮集合”变成了“可持续运转的 Agent 雏形”。

---

## 14. 最终一句话

本项目真正应该追求的不是“让 Codex 替代所有代码”，而是：

```text
LLM 理解需求
Spec 承载用户意图
Rules 承载用户可维护规则
Runtime 保证稳定执行
Skills 封装业务能力
Trace 保证可追踪
Memory 保证可复用
Codex 保证项目可进化
```

这才是适合 `excel-generator-project` 的轻量、简单、可持续 Agent 架构。
