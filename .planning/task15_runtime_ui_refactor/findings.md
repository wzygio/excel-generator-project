# Task15 发现记录

## Task15 初始理解

- 用户认为 Task14 仍然太冗余，尤其是中间“任务流”和右侧“执行摘要”重复显示后端步骤。
- 用户期望前端任务流不再是固定执行链路，而是类似 Codex 的 LLM 实时思考/进展反馈。
- 用户认为“任务结果”侧栏也属于调试信息，不应作为业务结果主呈现；业务结果应在对话框中以表格/正文呈现。
- 用户要求新增历史对话功能。
- 用户指出 M678 月度良率测试失败，返回了一周日度良率，质疑当前 Runtime 泛化能力。
- Task15 明确要求制定项目重构计划，先不要执行。

## UI 初步问题

- 中间主区域和右侧重复展示同一套后端步骤，信息密度高但业务价值低。
- “执行摘要”“任务流”命名暗示确定性 pipeline，不符合 Agent/Codex 风格。
- 右侧“任务结果”与对话中的结果重复，且更像 run metadata 面板。
- 产物名仍是英文 `data_analysis source file` / `data_analysis result text`，不是终端用户语言。

## 待验证

- M678 月度趋势黑箱测试实际返回内容。
- 当前 Runtime 是否使用成熟 Agent 框架。
- `data_analysis` 是否只有日度/周度局部 analyzer，缺少月度趋势泛化。

## 黑箱测试: M678 三个月月度良率

测试输入：

```text
请分析M678最近三个月的月度良率变化趋势；如果有恶化，请给出恶化原因
```

执行方式：通过现有 `/api/agent-runs` 提交 `action=create_and_run`、`runtime=auto`，未修改业务代码。

结果：

- API 返回 `success=true`，`runtime=python`，run id 为 `run-20260615-120059`。
- 返回 skill 为 `data_analysis`，strategy 为 `code`。
- 输出文件 `specs/runs/run-20260615-120059/outputs/data_analysis_result.md` 标题为 `M678 最近一周日度良率变化趋势`。
- 结果数据是 5/26 到 6/1 的 7 天日度良率，不是三个月月度良率。

关键证据：

- `specs/runs/run-20260615-120059/spec.yaml` 的 `user_goal` 保留了“三个月/月度”。
- 但同一 spec 的 `inputs.date_range` 被写成 `2026-06-09 ~ 2026-06-15`。
- 同一 spec 的 workflow input `metrics` 被写成 `日度良率`。
- 同一 spec 的 workflow input `time_range` 也是 `2026-06-09 ~ 2026-06-15`。

判断：失败发生在 Spec 生成与后续 analyzer 选择阶段，不是前端展示问题。

## Runtime 与 Analyzer 归因

- `src/yield_report/agent/runtime_adapter.py` 中 `RuntimeRouter` 的 `auto` 默认先运行 `PythonSkillRuntime`。只有请求显式为 `omp/pi`，或 Python 失败且 spec constraints 为 `python_with_pi_fallback` / `python_with_omp_fallback` 时，才尝试 OMP。
- 本次黑箱测试返回 `runtime=python`，说明 OMP 没有参与。
- `src/yield_report/agent/runtime.py` 是轻量顺序 Skill runtime：注册 skill、按 `spec.workflow` 顺序执行、写 trace、失败停止。它不是 OpenAI Agents SDK，也不是 LangGraph/LangChain，也不具备 ReAct 循环。
- `src/yield_report/agent/omp_runtime.py` 只是 OMP CLI 的一次性 JSON event adapter，并非默认主 runtime，也没有在本次成功路径中生效。
- `src/yield_report/agent/spec_builder.py` 的 `_build_analysis_spec` 固定将分析日期设置为 `report_date - 6 days` 到 `report_date`，并通过 `_infer_metrics` 将“良率”映射为 `日度良率`。
- `src/yield_report/core/analysis_query_parser.py` 的 heuristic fallback 也只识别最近一周，默认 `target_metrics = ["日度良率"]`。
- `src/yield_report/infrastructure/daily_yield_trend_analyzer.py` 的 `analyze(..., days=7)`、结果标题、表头和结论全部写死为“最近一周日度良率”。
- `src/yield_report/application/analysis_orchestrator.py` 对通用“良率 + 趋势”优先走内置日度良率趋势 analyzer，绕过了更通用的代码生成/LLM 直读路径。

结论：C522 用例通过主要依赖项目内已写好的“最近一周日度良率趋势”确定性路径，不是 Agent Runtime 自主推理出的泛化分析。M678 月度用例失败是当前架构能力边界的直接暴露。

## UI 重构计划

### 设计原则

- 参考 ChatGPT/Codex，而不是工业控制台。
- 前端不要展示后端固定执行链路；后端步骤只进入调试视图。
- “任务流”只表达 LLM/Agent 的实时状态，例如 `理解需求`、`查找数据`、`分析中`、`整理回答`，并由运行事件驱动，不固定渲染 workflow。
- 业务结果只在对话流中呈现。表格、结论、产物链接都作为 assistant message 的一部分。
- 右侧从“任务结果”改成“历史记录”，用于切换会话或 run。

### 目标布局

1. 左侧窄栏：历史会话列表、搜索、新建任务。
2. 中间主区：Chat timeline、结果表格、输入框。
3. 右侧可选抽屉：调试信息，仅在用户点击后显示。

### 移除或降级

- 移除中间默认 `任务流` 卡片。
- 移除右侧默认 `执行摘要` 卡片。
- 将当前右侧 `任务结果` 改为 `历史记录`。
- 产物列表不再占据主侧栏，改为 assistant message 下方的附件 chips。
- Memory 默认不作为主面板出现，变成 message action 或 debug tab。

### 历史对话数据模型

建议新增 `ui_session` 概念，不直接把它等同于 `run_id`：

- `conversation_id`: 前端会话 ID。
- `title`: 由第一条用户 goal 或 LLM summary 生成。
- `created_at` / `updated_at`。
- `messages[]`: user / assistant / system status messages。
- `runs[]`: 关联的 TaskSpec run id。
- `latest_status`: idle / running / completed / failed。

存储策略：

- 短期：浏览器 localStorage + 读取 `specs/runs` 列表恢复历史。
- 稳定版：新增 `.agent_workbench/conversations/*.json` 或 SQLite。
- API：`GET /api/conversations`、`GET /api/conversations/:id`、`POST /api/conversations/:id/messages`、`POST /api/agent-runs` 返回 `conversation_id`。

## Runtime 重构计划

### 结论

当前默认 Runtime 不应继续被宣传为具备 Agent 泛化能力。它适合执行已知 TaskSpec workflow，但不适合处理开放式“自然语言目标 -> 观察 -> 选择工具 -> 校验 -> 反思 -> 重试”的 Agent 闭环。

### 推荐路线

推荐采用“两层 Runtime”而不是单纯替换所有 Python skill：

1. **Planner/Agent Runtime 层**：使用 OMP 作为首选外部 Agent Runtime，或用 LangGraph 构建可测试 ReAct loop。
2. **Deterministic Skill 层**：保留现有 Python skill 作为工具，负责可复现的下载、Excel 读取、解密、计算、写文件。

推荐优先级：

| 路线 | 结论 | 原因 |
| --- | --- | --- |
| OMP 主 Runtime | 优先 POC | 本机可调用，已有 adapter，但需从 fallback 改为 first-class runtime，并限制工作目录/工具权限。 |
| LangGraph | 第二选择 | 适合显式状态机、可观测、可测试；开发量中等，但比手写 ReAct 更稳。 |
| OpenAI Agents SDK | 暂不作为当前主线 | 当前后端已改为 DeepSeek/OpenAI-compatible，Agents SDK 生态与模型/provider 兼容性需要额外验证。 |
| 继续自研增强 | 不推荐作为主线 | 容易继续堆规则，无法解决用户质疑的泛化能力和黑箱验收问题。 |

### 目标 ReAct/Agent Loop

一个合格 Runtime 至少需要：

- Observe: 读取用户 goal、现有 spec、文件索引、历史 memory。
- Plan: 生成可解释任务计划，不等同于固定 workflow。
- Act: 调用工具，包括 report_download、data_analysis、daily_report、file/schema inspect。
- Validate: 检查结果是否满足用户 goal，例如“三个月/月度”不得返回“一周/日度”。
- Repair: 不满足时重试或换工具，不能 success。
- Final: 生成业务答案、表格、产物和可选 debug trace。

### 黑箱验收矩阵

必须新增一组端到端黑箱用例，禁止为了单个用例写专门业务代码：

- C522 近一周日度良率趋势。
- M678 最近三个月月度良率趋势。
- M678 最近三个月月度良率，如果数据源缺少月度列，Runtime 必须说明缺口并尝试从月列/周列/日列聚合，而不是返回一周日度。
- 只下载 M626 近两个月月周天报表。
- 生成今天日报。
- 输入模糊型号或缺少时间范围时进入澄清，不直接编造默认范围。

验收规则：

- `user_goal`、TaskSpec、执行计划、最终答案的时间粒度必须一致。
- 最终答案包含自检字段：`requested_grain`、`actual_grain`、`requested_range`、`actual_range`、`data_source`。
- 任意粒度不匹配必须 `success=false` 或 `needs_confirmation`，不能显示“分析完成”。

### 分阶段迁移

P0: 黑箱测试与基线冻结

- 固定当前失败用例为回归测试。
- 将 run artifacts 保存为失败样本。
- 新增 Runtime contract：结果必须回填目标一致性自检。

P1: Spec Builder 改造

- 默认启用 LLM Spec conversion 或 OMP Planner 生成 spec。
- 规则 fallback 只做保守兜底，不能强行把所有良率趋势改成日度/7天。
- Spec 增加 `time_grain`、`requested_range`、`metric_grain`、`analysis_question_type`。

P2: Runtime 主循环

- 将 `RuntimeRouter(auto)` 从 Python-first 改为 Agent-planner-first。
- Python skill 作为工具，而不是最终决策者。
- 失败/不满足目标时允许 Agent 修复 spec 或重选工具。

P3: Tool 能力扩展

- `data_analysis` 拆出通用 `inspect_workbook_schema`、`select_table_range`、`compute_trend`、`render_analysis_answer`。
- 月度/周度/日度不再由单个硬编码 analyzer 决定。
- 旧 `DailyYieldTrendAnalyzer` 改名为 `DailyGrainYieldTrendAnalyzer` 或收窄触发条件。

P4: UI 对齐

- 对话区消费 Agent events，显示实时状态。
- 右侧历史记录支持恢复 conversation/run。
- Debug drawer 展示 TaskSpec、tool calls、validation、raw artifacts。

P5: 验收与切换

- 所有黑箱用例通过后，再把 OMP/LangGraph Runtime 设为默认。
- 保留 `runtime=python` 作为 deterministic fallback 和单元测试通道。

## Task15-2 Memory 结论

当前 Memory 架构存在业务污染风险，但污染点不是“自动写代码”，而是“已确认记忆会参与文件匹配和路径复用，而记录本身包含 target_metrics、analysis_logic、processing_method”。如果未来把这些字段直接用于执行策略，就会把旧需求的日度/周度路径误套到新需求。

当前代码中 Memory 的直接作用：

- `AnalysisMemoryStore.find_candidates()` 只返回 confirmed 记录。
- `AnalysisFileResolver.resolve()` 会优先使用 Memory candidate 的 `local_file_path` 或 `local_file_name` 找文件。
- 当前 Memory 不直接生成 Python 业务代码，也不直接改写 `TaskSpec`。

需要改进：

- Memory 只能作为“已确认事实库”，不作为“策略决策器”。
- Memory record 必须增加 capability/contract 字段，例如 `time_grain`、`metric_grain`、`validity_scope`、`source_schema_fingerprint`。
- 匹配时必须要求目标粒度兼容，不允许把 `daily` 记忆用于 `monthly` 请求。
- pending memory 默认不参与执行。
- confirmed memory 也必须经过 Runtime validator 检查，不能越过目标一致性校验。

关于 OMP Memory：

- 本机 OMP CLI 可用，但当前项目只通过 `OmpJsonRuntime` 一次性调用 OMP，没有接入 OMP 自带的会话/长期 Memory 作为项目数据源。
- OMP 的 session 能保留交互上下文，但不能替代项目内可审计、可确认、可回滚的业务 Memory。
- 不建议现在引入外部 `agentmemory`。本仓库没有可调用的 `agentmemory` CLI/包迹象；即使存在，也会比当前需求更重，且可能把业务事实、文件路径、策略混在一个不可审计记忆层。

结论：保留轻量 JSON Memory，但收窄为“confirmed facts only + scope validated retrieval”。Runtime 的目标一致性检查必须在 Memory 之后执行。

## Task15-2 实施后发现

- 黑箱失败根因已闭环：`SpecBuilder` 不再把所有良率趋势分析写成 `report_date - 6 days` 的日度任务；“三个月/月度”会进入 `inputs.analysis` 与 workflow input。
- `AnalysisQueryParser` 会优先保留用户显式时间粒度；当 LLM 返回日度/周度与用户显式月度冲突时，启发式校正会覆盖粒度、周期和日期范围。
- `DailyYieldTrendAnalyzer` 仍保留文件名兼容，但实现已支持 `monthly`、`weekly`、`daily` 三种时间列模式。
- 当请求 3 个月但源表只有 M05/M06 两个月度列时，Runtime 允许 success，但必须在结果中说明数据限制；这不是粒度不匹配。
- 当实际分析粒度与请求粒度不同，`AnalysisOrchestrator` 会返回失败，不再显示“分析完成”。
- 当前 Memory 不直接决定策略；confirmed 记录如果有 `time_grain`，必须与请求粒度一致才会成为 candidate。
- UI 精简后，后端 workflow 仍可在 Debug drawer 中查看，但默认工作区只呈现对话结果、历史记录和当前产物。

## Task15-3 发现

### M626 / OMP 报错归因

截图中的 `OMP command not found: omp` 不是 OMP 不支持自定义任务，也不是没有 M626 本地数据。实际链路是：

1. `RuntimeRouter(auto)` 仍然 Python-first。
2. Python data_analysis 先尝试使用 confirmed Memory / Resolver 文件候选。
3. 旧 Memory 指向 C522 源表，Resolver 未对 Memory 文件路径做产品型号二次校验，导致 M626 请求错读 C522 文件。
4. Python skill 因找不到 M626 数据失败。
5. spec 允许 `python_with_pi_fallback`，于是进入 OMP fallback。
6. OMP 本机存在，但 Next/Python 子进程环境没有解析到 `C:\Users\V0141351\AppData\Local\omp\omp.exe`，因此抛出 `OMP command not found: omp`。

判断：

- OMP 当前在项目里是一次性 CLI adapter，可接收自定义 prompt 并返回 JSON events；它不是默认主 runtime，也没有成为完整 ReAct loop。
- M626 用例应该优先由 deterministic Python 工具通过本地 M626 文件完成，不应因为 Memory 污染进入 OMP fallback。
- 因此本轮采用“修复本地 deterministic 路径 + 修复 OMP fallback 可用性”的最小可靠方案，而不是立刻替换 runtime 架构。

### 历史会话设计落地

右侧历史不应是 run 列表。ChatGPT/Codex 风格下，用户看到的是 conversation/session：

- 一个 conversation 可以包含多条 user/assistant message。
- 一个 conversation 可以关联多个 runtime `run_id`。
- 点击历史项恢复的是消息上下文、最近 Run 和产物；用户可以在同一会话继续提交。
- `run_id` 仍保留为调试/审计字段，而不是主导航单位。

本轮落地的短期存储：

- `.agent_workbench/conversations/*.json`
- `GET /api/conversations`
- `POST /api/conversations`
- `GET /api/conversations/:id`
- `PUT /api/conversations/:id`

该目录已加入 `.gitignore`，定位为本地工作台状态，不进入版本库。

### 验证结论

- M626 黑箱 API 通过，runtime 为 `python`，未再出现 OMP 报错。
- Chrome UI 中提交 M626 请求、生成历史会话、新对话清空、点击历史恢复均通过。
- 控制台无 error。
