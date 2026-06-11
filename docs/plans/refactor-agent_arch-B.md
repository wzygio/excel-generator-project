# excel-generator-project 智能体架构重构设计与 Codex 执行任务书

> 适用项目：`wzygio/excel-generator-project`  
> 设计目标：把当前“报表下载 / 数据分析 / 日报生成”三段式项目，重构为一个简单、可持续运转、Codex 友好的日报生成 Agent。  
> 推荐落点：把本文件复制到仓库 `docs/prompt/refactor-agent_architecture.md`，然后让 Codex 按“执行任务书”逐步改造。

---



## 2. 当前项目诊断

### 2.1 当前已有的正确基础

当前仓库已经有很多正确方向，不需要推倒重来。

```text
src/yield_report/agent/
├── spec_model.py   # TaskSpec / RunContext / SkillResult
├── router.py       # Spec加载和校验
├── runtime.py      # 轻量 Skill Runtime
├── registry.py     # 三个 Skill 注册
├── memory.py       # Memory facade
└── trace.py        # JSONL TraceWriter

src/yield_report/skills/
├── report_download/
├── data_analysis/
└── daily_report/
```

这说明项目已经从传统横向分层，开始迁移到 Agent-friendly 的 Spec/Skill/Runtime 架构。这个方向应继续坚持。

### 2.2 当前主要问题

#### 问题 1：UI 仍然是三个模块入口，不是 Agent 工作台

当前 UI 仍是：

```text
报表下载 tab
数据分析 tab
日报生成 tab
```

这导致用户必须知道自己要点击哪个模块，而不是只描述目标。

目标 UI 应该是：

```text
用户目标输入框
  -> 生成/展示 TaskSpec
  -> 用户确认或修改
  -> 执行 Spec
  -> 展示步骤 Trace
  -> 展示结果与下载产物
  -> Memory 候选确认/拒绝
```

#### 问题 2：缺少“自然语言 -> TaskSpec”的 Spec Builder

现在 `router.py` 更像 Spec loader/validator，而不是智能路由器。它能读 YAML、校验 workflow，但还不能根据用户自然语言生成可执行 Spec。

需要新增：

```text
src/yield_report/agent/spec_builder.py
```

职责：

1. 接收用户自然语言目标；
2. 读取模板 `specs/templates/daily_report_spec.yaml`；
3. 调用 LLMManager/Codex CLI 生成 JSON/YAML 补丁；
4. 合并成 TaskSpec；
5. 校验 TaskSpec；
6. 缺少关键字段时返回 `needs_confirmation`。

#### 问题 3：Codex CLI 已经被当作 runtime LLM backend，但必须限制使用范围

当前 `LLMManager` 已经通过 `CodexCLIClient` 调用 `codex exec --ephemeral`。这可以保留，但它应该被定位为：

```text
本地单用户模式下的 LLM 后端适配器
```

而不是：

```text
生产级 Agent Orchestrator
```

原因：

- Codex CLI 是命令行工具，不是你产品内部稳定 API。
- 每次 `--ephemeral` 调用没有长期会话状态。
- 运行耗时和失败恢复不可控。
- 如果 Streamlit 部署给多人使用，CLI 登录态、权限、并发都会很麻烦。

所以推荐保留当前 `CodexCLIClient`，但只让它做：

```text
需求解析
Spec 生成
日报文字润色
异常原因解释
Memory 候选摘要
```

不要让它在 UI 后台自由修改文件、执行 shell、重构代码。

#### 问题 4：Runtime 已有，但没有成为 UI 和 CLI 的统一入口

当前 UI 直接调用：

```python
report_download_tool.run(...)
data_analysis_tool.run(...)
daily_report_tool.run(...)
```

目标应该改成：

```python
spec = SpecBuilder.build(user_goal)
results = AgentRuntime.run_spec(spec, context)
```

也就是：

```text
UI 不再理解业务模块
UI 只理解 Spec、Run、Trace、Artifacts
```

#### 问题 5：Trace 路径应收敛到每次 run 的目录

当前模板里 `trace.path: trace.jsonl`，Runtime 如果简单按 workspace 解析，容易写到项目根目录。

推荐规范：

```text
specs/runs/<run_id>/
├── spec.yaml
├── trace.jsonl
├── memory_candidates.json
└── outputs/
    ├── daily_report.xlsx
    ├── daily_report.json
    └── daily_report.md
```

Runtime 应优先把相对路径解析到 `spec_path.parent` 或 `RunContext.output_dir.parent`，而不是项目根目录。

#### 问题 6：`daily_report` 内部调用 `data_analysis`，部分步骤对 Runtime 不透明

当前 `daily_report` 会内部调用 `data_analysis` 生成日报结构化事实。这个设计短期能工作，但从 Agent 可观察性角度，最好逐步改成显式 workflow：

```yaml
workflow:
  - id: prepare_daily_report_facts
    skill: data_analysis
    input:
      analysis_kind: daily_report
    save_as: daily_report_facts

  - id: generate_daily_report
    skill: daily_report
    depends_on:
      - prepare_daily_report_facts
    input:
      analysis_results:
        - daily_report_facts
    save_as: daily_report_file
```

这样用户能在 UI 看到：

```text
1. 数据准备
2. 结构化分析
3. 日报写入
4. 文件产出
```

---

## 3. 修正后的目标架构

### 3.1 总体架构图

```text
┌─────────────────────────────────────────────┐
│ User / Supervisor                            │
│ 自然语言目标、约束、确认、反馈、验收           │
└──────────────────────┬──────────────────────┘
                       │
┌──────────────────────▼──────────────────────┐
│ Streamlit Agent Workbench                    │
│ 单输入框 / Spec预览 / 运行步骤 / 产物下载       │
└──────────────────────┬──────────────────────┘
                       │
┌──────────────────────▼──────────────────────┐
│ Spec Builder                                 │
│ LLM 将自然语言转换为 TaskSpec；代码负责校验     │
└──────────────────────┬──────────────────────┘
                       │
┌──────────────────────▼──────────────────────┐
│ Run Store                                    │
│ specs/runs/<run_id>/spec.yaml / trace / output│
└──────────────────────┬──────────────────────┘
                       │
┌──────────────────────▼──────────────────────┐
│ Agent Runtime                                │
│ 读取 TaskSpec；执行 Skill；写 Trace；保存状态    │
└────────────┬───────────────┬────────────────┘
             │               │
┌────────────▼──────┐ ┌──────▼─────────┐
│ Python Skills      │ │ Agent Memory   │
│ report_download    │ │ confirmed only │
│ data_analysis      │ │ pending review │
│ daily_report       │ └────────────────┘
└────────────┬──────┘
             │
┌────────────▼──────────────────────────────┐
│ Stable Adapters / Existing Implementation │
│ FineReport RPA / Excel / pandas / LLMManager│
└───────────────────────────────────────────┘
```

### 3.2 目标运行链路

```text
用户说：帮我生成 M678 今天良率日报，重点分析 CT 良率趋势和异常。

1. UI 接收自然语言目标。
2. SpecBuilder 生成 specs/runs/<run_id>/spec.yaml。
3. UI 展示 Spec 摘要，若缺日期/产品/报表类型则提示确认。
4. AgentRuntime 读取 Spec。
5. Runtime 调用 data_analysis / daily_report / report_download。
6. 每一步写 trace.jsonl。
7. 生成 Excel、JSON、Markdown。
8. UI 展示步骤、结果、下载按钮。
9. 若产生 Memory 候选，用户点击确认/拒绝。
```

### 3.3 推荐目录结构

```text
excel-generator-project/
├── AGENTS.md                                  # 新增：Codex 默认入口，复制/整理 .roorules
├── .roorules                                  # 保留给 Roo Code，但与 AGENTS.md 同步
├── .agents/
│   └── skills/
│       └── yield-report-daily/
│           └── SKILL.md                       # 新增：Codex 官方 Skill 薄壳
├── app/
│   └── main.py                                # 重构：Agent Workbench
├── docs/
│   ├── agent/
│   │   ├── architecture.md
│   │   ├── spec_contract.md
│   │   ├── skill_contract.md
│   │   └── runbook.md                         # 新增：运行和失败恢复
│   └── prompt/
│       └── refactor-agent_architecture.md      # 本文件建议放这里
├── scripts/
│   ├── create_daily_report_spec.py             # 新增：自然语言 -> spec.yaml
│   ├── run_task_spec.py                        # 新增：执行 spec.yaml
│   └── inspect_run_trace.py                    # 可选：打印 trace 摘要
├── specs/
│   ├── templates/
│   │   └── daily_report_spec.yaml
│   └── runs/                                  # gitignore
│       └── <run_id>/
│           ├── spec.yaml
│           ├── trace.jsonl
│           ├── memory_candidates.json
│           └── outputs/
├── src/
│   ├── shared_kernel/
│   │   └── infrastructure/
│   │       ├── llm_handler.py
│   │       └── codex_cli_client.py
│   └── yield_report/
│       ├── agent/
│       │   ├── spec_model.py
│       │   ├── spec_builder.py                # 新增
│       │   ├── run_store.py                   # 新增
│       │   ├── router.py
│       │   ├── runtime.py
│       │   ├── registry.py
│       │   ├── memory.py
│       │   └── trace.py
│       └── skills/
│           ├── report_download/
│           ├── data_analysis/
│           └── daily_report/
└── tests/
    ├── unit/
    │   ├── agent/
    │   └── skills/
    └── integration/
```

---

## 4. 核心模块设计

## 4.1 `AGENTS.md`

### 目标

让 Codex 一进入项目就知道：

1. 当前项目是什么；
2. 应该先读哪些文件；
3. 运行哪些命令；
4. 哪些红线不能碰；
5. 如何执行一次日报 Agent 任务。

### 执行要求

新增根目录：

```text
AGENTS.md
```

第一版可以直接复制 `.roorules` 内容，再做两处修改：

1. 文件标题从 `.roorules` 改成 `AGENTS.md`。
2. 在快速命令中新增：

```bash
# 生成日报任务 Spec
uv run python scripts/create_daily_report_spec.py --goal "生成 M678 今天良率日报，重点分析 CT 良率趋势"

# 执行指定 Spec
uv run python scripts/run_task_spec.py --spec specs/runs/<run_id>/spec.yaml

# 查看 Trace 摘要
uv run python scripts/inspect_run_trace.py --run specs/runs/<run_id>
```

---

## 4.2 `.agents/skills/yield-report-daily/SKILL.md`

### 目标

让 Codex 能把“生成良率日报”识别为一个仓库内 Skill，而不是盲目搜索代码。

### 建议内容

```markdown
---
name: yield-report-daily
summary: Generate OLED yield daily reports from local/FineReport source Excel files through TaskSpec and Python skills.
description: Use this skill when the user asks to download yield reports, analyze yield data, generate OLED daily yield reports, inspect daily report failures, or update the yield-report Agent workflow.
---

# yield-report-daily

## When to use

Use this skill for tasks involving:

- FineReport yield source download
- CT yield / defect / Gap analysis
- OLED daily yield report generation
- TaskSpec workflow creation or repair
- Debugging `src/yield_report/agent/` or `src/yield_report/skills/`

## Required reading

1. Read `AGENTS.md` first.
2. Read `docs/agent/architecture.md` for the target Agent architecture.
3. Read `docs/agent/spec_contract.md` before editing any `spec.yaml`.
4. Read `docs/agent/skill_contract.md` before editing any Skill.
5. Read `docs/design/yield_report_domain.md` before changing business logic.

## Standard workflow

1. Convert the user goal into a TaskSpec under `specs/runs/<run_id>/spec.yaml`.
2. Validate the Spec.
3. Execute:
   `uv run python scripts/run_task_spec.py --spec specs/runs/<run_id>/spec.yaml`
4. Inspect `trace.jsonl` when a step fails.
5. Fix the smallest failing layer.
6. Re-run focused tests before broader tests.

## Hard rules

- Do not bypass Python Skills for FineReport, Excel IO, or report generation.
- Do not put runtime logs in the repo root.
- Do not write secrets or credentials into Spec, Trace, Memory, or docs.
- Prefer modifying Spec/Skill contracts over adding UI-specific branching.
```

---

## 4.3 `SpecBuilder`

### 文件

```text
src/yield_report/agent/spec_builder.py
```

### 职责

`SpecBuilder` 是本次重构最重要的新模块。它负责把用户自然语言变成 `TaskSpec`。

### 输入

```python
class SpecBuildRequest(BaseModel):
    user_goal: str
    template_name: str = "daily_report"
    run_id: str | None = None
    report_date: str | None = None
    product_models: list[str] = Field(default_factory=list)
    allow_llm: bool = True
```

### 输出

```python
class SpecBuildResult(BaseModel):
    success: bool
    spec: TaskSpec | None = None
    spec_path: Path | None = None
    summary: str = ""
    missing_confirmations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    raw_llm_output: str = ""
```

### 设计原则

1. **LLM 只生成结构化补丁，不直接生成 Python 代码。**
2. **SpecBuilder 必须用 Pydantic 校验 TaskSpec。**
3. **缺关键字段时，不要猜太多，应设置 `status: needs_confirmation`。**
4. **默认使用 `daily_report_spec.yaml` 模板，再由 LLM 填充字段。**
5. **LLM 输出必须是 JSON object，避免 Markdown 包裹。**

### LLM 输出格式建议

```json
{
  "user_goal": "生成 M678 今天良率日报，重点分析 CT 良率趋势",
  "report_date": "2026-06-03",
  "product_models": ["M678"],
  "sections": ["gap", "trend", "known_exception", "new_exception"],
  "needs_confirmation": [],
  "workflow_mode": "daily_report_default"
}
```

### SpecBuilder 伪代码

```python
class SpecBuilder:
    def build(self, request: SpecBuildRequest) -> SpecBuildResult:
        run_id = request.run_id or make_run_id()
        run_dir = RunStore.create_run_dir(run_id)
        template = load_template("specs/templates/daily_report_spec.yaml")

        patch = self._llm_extract_spec_patch(request.user_goal) if request.allow_llm else {}
        spec_dict = merge_template_with_patch(template, patch, request)
        spec_dict["run_id"] = run_id
        spec_dict["trace"]["path"] = "trace.jsonl"

        missing = find_missing_required_fields(spec_dict)
        spec_dict["status"] = "needs_confirmation" if missing else "ready"

        spec = parse_task_spec(spec_dict)
        spec_path = run_dir / "spec.yaml"
        write_yaml(spec_path, spec.model_dump(mode="json"))

        return SpecBuildResult(
            success=True,
            spec=spec,
            spec_path=spec_path,
            missing_confirmations=missing,
        )
```

---

## 4.4 `RunStore`

### 文件

```text
src/yield_report/agent/run_store.py
```

### 职责

集中管理每次 Agent 运行目录，避免 UI、Runtime、Skill 各自拼路径。

### 目录规则

```text
specs/runs/<run_id>/
├── spec.yaml
├── trace.jsonl
├── memory_candidates.json
└── outputs/
```

### 关键接口

```python
class RunStore:
    def create_run(self, run_id: str | None = None) -> RunPaths: ...
    def load_spec(self, spec_path: Path) -> TaskSpec: ...
    def save_spec(self, spec: TaskSpec, path: Path) -> None: ...
    def make_context(self, spec_path: Path, spec: TaskSpec) -> RunContext: ...
    def read_trace(self, run_id: str) -> list[TraceEvent]: ...
    def list_artifacts(self, run_id: str) -> list[ArtifactRef]: ...
```

### `RunContext` 规则

`RunStore.make_context()` 应保证：

```python
context = RunContext(
    run_id=spec.run_id,
    workspace=Path.cwd(),
    spec_path=spec_path,
    output_dir=run_dir / "outputs",
    trace=TraceWriter(run_dir / "trace.jsonl"),
    memory=AgentMemory(),
)
```

---

## 4.5 `AgentRuntime`

当前 `AgentRuntime` 可以保留，但建议做 4 个增强。

### 增强 1：Trace 路径优先相对 run_dir

当前相对路径不要解析到仓库根目录，应解析到：

```text
context.spec_path.parent / trace.path
```

优先级：

```text
1. context.trace 已存在：直接使用
2. spec.trace.path 是绝对路径：使用绝对路径
3. context.spec_path 存在：context.spec_path.parent / spec.trace.path
4. fallback：context.output_dir.parent / spec.trace.path
5. 最后才是 workspace / spec.trace.path
```

### 增强 2：写入 run_summary.json

每次运行结束后写：

```text
specs/runs/<run_id>/run_summary.json
```

内容：

```json
{
  "run_id": "...",
  "status": "completed",
  "started_at": "...",
  "ended_at": "...",
  "steps": [...],
  "artifacts": [...],
  "warnings": [...],
  "error": null
}
```

### 增强 3：失败后给 Codex 可读的 repair hint

当 SkillResult 失败时，`trace.jsonl` 中应包含：

```json
{
  "error": {
    "code": "daily_report.file.missing_required",
    "message": "缺少日报生成必需源文件: spotfire",
    "recoverable": true,
    "repair_hint": "检查 resources/spotfire.xlsx 或在 spec.inputs.local_files 中指定 spotfire 路径"
  }
}
```

### 增强 4：Memory 候选集中落盘

如果任意 SkillResult 返回 `memory_updates`，Runtime 追加写入：

```text
specs/runs/<run_id>/memory_candidates.json
```

UI 从这个文件显示“确认 / 拒绝”。

---

## 4.6 三个业务 Skill 的边界

## 4.6.1 `report_download`

### 保留代码能力

必须继续用现有 Python / RPA：

```text
自然语言或结构化 request
  -> ReportQueryRequest
  -> DataAcquisitionOrchestrator
  -> FinereportClient / LocalFileLoader
  -> resources/*.xlsx
```

### LLM 应该参与的部分

- 从用户目标中提取报表类型、日期、型号。
- 当报表类型不明确时给出澄清问题。
- 失败时根据错误码解释下一步应该确认什么。

### 不应该交给 LLM 的部分

- 操作 FineReport 页面。
- 判断下载文件是否存在。
- 重命名和保存 Excel。

## 4.6.2 `data_analysis`

### 建议拆成两层

```text
data_analysis
├── fact_extractors/        # 确定性事实提取
│   ├── ct_trend.py
│   ├── gap_top_items.py
│   ├── known_exception.py
│   └── new_exception.py
├── llm_interpreter.py      # 用 LLM 把结构化事实解释为业务语言
└── tool.py
```

### LLM 应该参与的部分

- 根据用户问题选择分析 intent。
- 根据 schema 和样例判断字段语义。
- 解释趋势、异常、Gap 的业务含义。
- 生成日报文字草稿。
- 提炼 Memory 候选。

### 代码应该负责的部分

- Excel 解密和读取。
- schema 提取。
- pandas/openpyxl 计算。
- 结果表格和中间数据保存。
- 错误码和 trace。

## 4.6.3 `daily_report`

### 目标

`daily_report` 只负责最终产物生成：

```text
结构化分析事实 / analysis_results
  -> 文字润色
  -> 模板写入
  -> Excel / JSON / Markdown 输出
```

### 建议修正

中期目标是避免它内部隐式调用 `data_analysis`。更推荐 Runtime 显式调用：

```yaml
workflow:
  - id: prepare_daily_report_facts
    skill: data_analysis
    input:
      analysis_kind: daily_report
      sections: [gap, trend, known_exception, new_exception]
    save_as: daily_report_facts

  - id: generate_daily_report
    skill: daily_report
    depends_on: [prepare_daily_report_facts]
    input:
      analysis_results:
        - daily_report_facts
      output_name: daily_report_output.xlsx
    save_as: daily_report_file
```

## 5. Agent Workbench UI 设计

### 5.1 替代当前三 Tab 的主界面

保留旧三 Tab 作为“高级/兼容入口”，但默认首页改成：

```text
Agent 工作台
├── 任务输入
│   └── text_area: 用户自然语言目标
├── Spec 预览
│   ├── 生成 Spec
│   ├── 编辑 Spec
│   └── 确认执行
├── 运行步骤
│   └── trace timeline
├── 结果
│   ├── 分析摘要
│   ├── Excel 下载
│   ├── JSON 下载
│   └── Markdown 下载
└── Memory
    ├── 待确认候选
    ├── 确认
    └── 拒绝
```

### 5.2 UI 状态字段

```python
st.session_state = {
    "agent_goal": "",
    "agent_run_id": "",
    "agent_spec_path": "",
    "agent_spec_text": "",
    "agent_status": "idle|draft|ready|running|completed|failed|needs_confirmation",
    "agent_trace_events": [],
    "agent_result_text": "",
    "agent_artifact_paths": {},
    "agent_memory_candidates": [],
}
```

### 5.3 UI 按钮

```text
[生成 Spec]
[确认并执行]
[只执行已有 Spec]
[刷新 Trace]
[下载日报 Excel]
[确认 Memory]
[拒绝 Memory]
```

### 5.4 用户体验原则

1. 用户默认只看一个输入框和结果。
2. Spec 默认折叠，但必须可展开修改。
3. Trace 默认展示中文摘要，不直接展示 JSON。
4. 高级三 Tab 可放在侧边栏或 expander 中。
5. 报错时优先显示“下一步如何修复”，不要只显示 Python traceback。

---

## 6. Memory 设计

### 6.1 当前阶段不要引入外部 agent-memory 项目

你提到 GitHub 上的 `agent-memory`。当前不建议引入，原因是：

1. 当前项目记忆规模很小。
2. 你的记忆主要是业务规则、字段映射、分析习惯，不需要复杂向量检索。
3. 仓库已经有 JSON-backed `AnalysisMemoryStore` 和 `AgentMemory` facade。
4. 引入外部项目会增加依赖、迁移、调试成本。

### 6.2 当前最小 Memory 模型

建议分五类：

```text
memory/
├── file_locator       # 某类源表通常在哪里
├── field_mapping      # 某业务指标对应哪些字段/sheet
├── analysis_recipe    # 某类问题采用什么分析步骤
├── report_template    # 日报模板写入区域、格式规则
└── user_preference    # 用户确认过的输出习惯
```

### 6.3 状态

```text
pending    # LLM/Skill 提出，未确认
confirmed  # 用户确认，可自动复用
rejected   # 用户拒绝，不再自动使用
archived   # 历史保留，不参与匹配
```

### 6.4 复用规则

硬规则：

```text
只有 confirmed memory 可以自动复用。
pending memory 必须展示给用户确认。
每次复用 memory 必须写入 trace。
```

---

## 7. Context 设计

当前阶段不要做复杂 RAG，只做“文件化上下文 + 渐进读取”。

### 7.1 固定上下文入口

```text
AGENTS.md
ARCHITECTURE.md
docs/agent/architecture.md
docs/agent/spec_contract.md
docs/agent/skill_contract.md
docs/design/yield_report_domain.md
```

### 7.2 业务上下文入口

建议补充：

```text
docs/domain/daily_report_rules.md
```

内容包括：

- 日报 2.1 / 2.2 / 2.3 / 2.4 各章节定义。
- Gap 计算规则。
- CT 良率趋势判断规则。
- 已知异常/新增异常判断规则。
- 每个源表的关键 sheet / 字段。
- 产品型号命名规则。
- 常见错误和人工确认点。

### 7.3 Spec 是运行上下文，不是知识库

不要把大量业务规则塞到每个 `spec.yaml`。Spec 只写本次任务：

```yaml
user_goal
report_date
product_models
reports
local_files
workflow
outputs
memory policy
trace policy
```

业务通用规则放文档或 Memory。

---


## 10. 具体开发任务


## Task B：新增 Codex Skill 薄壳

### 目标

让 Codex 在仓库中自动识别“良率日报生成”能力。

### 改动

新增：

```text
.agents/skills/yield-report-daily/SKILL.md
```

内容参考本文件第 4.2 节。

### 验收

在 Codex CLI 中输入 `/skills` 或用 `$yield-report-daily` 触发，能看到该 Skill。

---

## Task C：新增 `RunStore`

### 目标

统一管理 run 目录、spec、trace、outputs。

### 改动

新增：

```text
src/yield_report/agent/run_store.py
```

建议模型：

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from yield_report.agent.memory import AgentMemory
from yield_report.agent.router import load_task_spec
from yield_report.agent.spec_model import RunContext, TaskSpec
from yield_report.agent.trace import TraceWriter


@dataclass(frozen=True)
class RunPaths:
    run_id: str
    run_dir: Path
    spec_path: Path
    trace_path: Path
    output_dir: Path
    memory_candidates_path: Path


class RunStore:
    def __init__(self, workspace: Path | None = None, runs_root: Path | None = None) -> None:
        self.workspace = (workspace or Path.cwd()).resolve()
        self.runs_root = self.workspace / (runs_root or Path("specs/runs"))

    def create_run(self, run_id: str | None = None) -> RunPaths:
        run_id = run_id or datetime.now().strftime("run-%Y%m%d-%H%M%S")
        run_dir = self.runs_root / run_id
        output_dir = run_dir / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        return RunPaths(
            run_id=run_id,
            run_dir=run_dir,
            spec_path=run_dir / "spec.yaml",
            trace_path=run_dir / "trace.jsonl",
            output_dir=output_dir,
            memory_candidates_path=run_dir / "memory_candidates.json",
        )

    def load_spec(self, spec_path: Path) -> TaskSpec:
        return load_task_spec(spec_path)

    def save_spec(self, spec: TaskSpec, spec_path: Path) -> None:
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(
            yaml.safe_dump(spec.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def make_context(self, spec_path: Path, spec: TaskSpec) -> RunContext:
        run_dir = spec_path.parent
        return RunContext(
            run_id=spec.run_id or run_dir.name,
            workspace=self.workspace,
            spec_path=spec_path,
            output_dir=run_dir / "outputs",
            memory=AgentMemory(),
            trace=TraceWriter(run_dir / "trace.jsonl"),
        )
```

### 测试

新增：

```text
tests/unit/agent/test_run_store.py
```

测试：

- `create_run()` 创建目录；
- `save_spec()` 写入 YAML；
- `load_spec()` 可读回；
- `make_context()` 的 output_dir 和 trace_path 指向 run 目录。

---

## Task D：新增 `SpecBuilder`

### 目标

把自然语言目标变成可执行 TaskSpec。

### 改动

新增：

```text
src/yield_report/agent/spec_builder.py
```

建议先实现两阶段：

### D1：规则模板版

不调用 LLM，先支持最小输入：

```bash
uv run python scripts/create_daily_report_spec.py --goal "生成 M678 今天良率日报"
```

用简单规则提取：

- 产品型号：正则 `[A-Z]\d{3,4}`；
- 日期：今天/昨天/明确日期；
- sections：默认四段。

### D2：LLM 增强版

再通过 `LLMManager.chat(..., response_format={"type": "json_object"})` 提取结构化补丁。

### 测试

新增：

```text
tests/unit/agent/test_spec_builder.py
```

测试：

- 明确产品和日期 -> `status=ready`；
- 缺少产品但允许全产品 -> `status=ready`；
- 缺少必要源表 -> `status=needs_confirmation` 或 warnings；
- LLM 输出非法 JSON 时 fallback 到规则版。

---

## Task E：新增 CLI 脚本

## E1：`scripts/create_daily_report_spec.py`

### 目标

给 Codex 和用户一个稳定命令：自然语言 -> `spec.yaml`。

### 使用方式

```bash
uv run python scripts/create_daily_report_spec.py \
  --goal "生成 M678 今天良率日报，重点分析 CT 良率趋势" \
  --print-path
```

### 输出

```text
specs/runs/run-20260603-153000/spec.yaml
```

## E2：`scripts/run_task_spec.py`

### 目标

执行指定 Spec。

### 使用方式

```bash
uv run python scripts/run_task_spec.py --spec specs/runs/run-20260603-153000/spec.yaml
```

### 行为

1. 读取 Spec；
2. 构造 RunContext；
3. 注册默认 Skill；
4. 执行 Runtime；
5. 打印每一步摘要；
6. 退出码：成功 0，失败 1。

## E3：`scripts/inspect_run_trace.py`

### 目标

快速查看一次运行的步骤状态。

### 使用方式

```bash
uv run python scripts/inspect_run_trace.py --run specs/runs/run-20260603-153000
```

### 输出示例

```text
run_id: run-20260603-153000
1. prepare_daily_report_facts [succeeded] 日报结构化分析完成: 3 个产品
2. generate_daily_report [succeeded] 日报生成完成: 3 个产品
artifacts:
- output excel: specs/runs/.../outputs/daily_report_output.xlsx
```

---

## Task F：增强 Runtime

### 改动

修改：

```text
src/yield_report/agent/runtime.py
```

### 要点

1. Trace 路径相对 run_dir。
2. 每步失败时写 recoverable、details、repair_hint。
3. 收集 artifacts。
4. 写 `run_summary.json`。
5. 写 `memory_candidates.json`。

### 测试

新增或扩展：

```text
tests/unit/agent/test_runtime.py
```

测试：

- 正常 workflow 依赖执行顺序；
- 未注册 skill 报错；
- 失败后停止后续步骤；
- trace 写到 run_dir；
- save_as 能被下游引用；
- memory_updates 会落盘。

---

## Task G：改造 UI 为 Agent Workbench

### 改动

修改：

```text
app/main.py
```

### 推荐方式

不要一次删除旧三 Tab。建议新增第一个 Tab：

```text
Agent 工作台 | 报表下载 | 数据分析 | 日报生成
```

默认用户使用 `Agent 工作台`。

### Agent 工作台逻辑

```python
if generate_spec_clicked:
    result = SpecBuilder().build(SpecBuildRequest(user_goal=goal))
    st.session_state.agent_spec_path = str(result.spec_path)
    st.session_state.agent_spec_text = result.spec_path.read_text(...)

if run_spec_clicked:
    spec = RunStore().load_spec(Path(st.session_state.agent_spec_path))
    context = RunStore().make_context(Path(st.session_state.agent_spec_path), spec)
    runtime = build_default_runtime()
    results = runtime.run_spec(spec, context)
    render_trace_and_artifacts(...)
```

### UI 验收

1. 输入一句话目标。
2. 点击“生成 Spec”。
3. 页面出现 YAML。
4. 点击“确认并执行”。
5. 页面展示步骤。
6. 成功后显示 Excel 下载按钮。
7. 失败后展示错误码和修复建议。

---

## Task H：调整 `daily_report` workflow 透明度

### 短期目标

保留现有内部调用，但把 downstream_results 显示到 UI 和 trace。

### 中期目标

把 `data_analysis` 显式放进 Spec workflow。

推荐模板调整：

```yaml
workflow:
  - id: prepare_daily_report_facts
    skill: data_analysis
    input:
      analysis_kind: daily_report
      report_date: null
      sections:
        - gap
        - trend
        - known_exception
        - new_exception
      source_files: {}
    save_as: daily_report_facts

  - id: generate_daily_report
    skill: daily_report
    depends_on:
      - prepare_daily_report_facts
    input:
      report_date: null
      template_ref: docs/project_files/V3良率日报每日异常填报表.xlsx
      sections:
        - gap
        - trend
        - known_exception
        - new_exception
      analysis_results:
        - daily_report_facts
      output_name: daily_report_output.xlsx
      emit_intermediate_artifacts: true
    save_as: daily_report_file
```

注意：这一步可能需要修改 `daily_report`，让它优先消费 `analysis_results`，如果没有再走旧内部分析路径。

---

## 11. 测试与验收清单

## 11.1 单元测试

```bash
uv run pytest tests/unit/agent -v --tb=short
uv run pytest tests/unit/skills -v --tb=short
```

## 11.2 当前回归测试

```bash
uv run pytest tests/ -v --tb=short
```

## 11.3 质量检查

```bash
uv run ruff check .
uv run pyright
```

## 11.4 CLI 烟测

```bash
uv run python scripts/create_daily_report_spec.py --goal "生成 M678 今天良率日报，重点分析 CT 良率趋势" --print-path
uv run python scripts/run_task_spec.py --spec specs/runs/<run_id>/spec.yaml
uv run python scripts/inspect_run_trace.py --run specs/runs/<run_id>
```

## 11.5 UI 烟测

```bash
uv run streamlit run app/main.py --server.port 8502
```

验收：

- Agent 工作台可生成 Spec。
- 可执行 Spec。
- trace 可见。
- Excel/JSON/Markdown 产物可下载。
- Memory 候选可确认/拒绝。
- 旧三个 Tab 仍可运行。

---

## 12. 风险与回滚

### 风险 1：Codex CLI 在运行时不稳定

缓解：

- `CodexCLIClient` 默认 read-only / ephemeral。
- 所有 LLM 调用有 timeout。
- LLM 失败时 fallback 到规则解析或提示用户确认。
- 不让 UI 触发 Codex 写文件或执行 shell。

### 风险 2：SpecBuilder 生成错误 Spec

缓解：

- Pydantic 校验。
- workflow skill 注册校验。
- 缺字段进入 `needs_confirmation`。
- UI 展示 Spec 供用户确认。

### 风险 3：日报业务规则被 LLM 编造

缓解：

- LLM 不直接读写 Excel。
- 结构化事实由代码提取。
- LLM 只基于 facts 生成文字。
- 关键判断写入 trace 和 artifacts。

### 风险 4：重构影响旧功能

缓解：

- 旧三 Tab 保留一段时间。
- 新 Agent Workbench 作为新增 Tab。
- 现有 `application/core/infrastructure` 不立即删除。
- 保留旧单元测试。

---

## 13. 最小可行版本 MVP

如果时间有限，只做这 6 件事：

```text
1. 新增 AGENTS.md
2. 新增 .agents/skills/yield-report-daily/SKILL.md
3. 新增 RunStore
4. 新增 SpecBuilder 规则版
5. 新增 create_daily_report_spec.py / run_task_spec.py
6. 在 UI 新增 Agent 工作台 Tab
```

MVP 之后，你的用户就可以这样使用：

```text
输入：生成 M678 今天良率日报，重点分析 CT 良率趋势。
点击：生成 Spec。
点击：确认并执行。
下载：日报 Excel。
```

Codex 也可以这样使用：

```text
$yield-report-daily
请为 M678 生成今天的良率日报。如果失败，请根据 trace 修复最小问题并重新运行测试。
```


---

## 15. 最终判断

你原始架构的方向是对的，但应做一次“降维工程化”：

```text
不要做通用 Agent 平台
不要做复杂 ReAct 框架
不要做 MCP/RAG/Sub-agent
不要马上引入 LangChain
不要让 UI 直接把所有事情丢给 Codex CLI
```

本项目最正确的路线是：

```text
AGENTS.md 让 Codex 看懂项目
TaskSpec 让用户目标可执行
Runtime 让流程可追踪
Python Skills 让稳定能力可复用
LLM/Codex 让需求理解和文字生成更灵活
Streamlit Workbench 让用户能确认、执行、下载、反馈
```

这会比当前“三个模块 + 很多代码判断”的架构更适合持续迭代，也比直接引入大型 Agent 框架更稳、更简单。
