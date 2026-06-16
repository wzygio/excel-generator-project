# Task15 Runtime 与 UI 重构计划

## 目标

完成 `docs/prompt/refactor-agent_arch.md` 中 Task15 的分析与项目重构计划，先不执行代码改造。重点回答两个问题：

- UI 如何进一步精简为 ChatGPT/Codex 风格，并新增历史对话能力。
- 当前 Agent Runtime 是否真正具备泛化执行能力，还是只对上一轮测试用例做了定向代码路径。

## 约束

- 不为任何测试用例编写业务代码来帮助 Runtime 过测。
- 对 Runtime 测试必须黑箱执行，通过现有 API/UI 输入自然语言 goal。
- 本轮只制定重构计划，不实施 Runtime 框架替换或大规模 UI 重写。
- 保留当前项目已有工作树改动，不回退用户或其他任务的文件。

## 最终目标 Checklist

- [ ] Task15 要求逐条转译为可执行发现。
- [ ] 黑箱测试 “请分析M678最近三个月的月度良率变化趋势；如果有恶化，请给出恶化原因”。
- [ ] 明确现有 Runtime 是自研路由/skill 编排、OpenAI Agents SDK、LangGraph/LangChain，还是其他框架。
- [ ] 判断 C522 用例通过的主要原因：Runtime 泛化能力、已有业务 analyzer、还是针对测试用例的定向代码。
- [ ] 给出 UI 精简方案：去掉固定执行链路/任务流，任务结果改历史记录，结果只在对话中呈现。
- [ ] 给出历史对话功能的数据模型、交互和 API 计划。
- [ ] 给出 Runtime 重构方案，对比 OMP、LangGraph/LangChain、自研增强三条路径。
- [ ] 给出分阶段实施计划与验收测试，明确哪些测试必须黑箱通过。

## 阶段

### 阶段 1: Task15 需求与截图复盘
状态: complete

- 阅读 Task15 完整要求
- 记录截图中的 UI 问题
- 明确“先不要执行”的边界

### 阶段 2: Runtime 黑箱验证
状态: complete

- 使用现有 `/api/agent-runs` 或 UI 输入 M678 月度趋势测试用例
- 记录返回内容、TaskSpec、workflow、产物和错误
- 不修改任何业务代码

### 阶段 3: Runtime 架构归因
状态: complete

- 阅读 `docs/agent/architecture.md`
- 检查 `src/yield_report/agent/` 和 `src/yield_report/skills/data_analysis`
- 判断当前框架和泛化边界

### 阶段 4: UI 精简与历史记录方案
状态: complete

- 设计 ChatGPT/Codex 风格主界面
- 移除前端固定执行链路展示
- 将右侧“任务结果”改为历史记录/会话列表
- 将调试内容收敛到可选开发视图

### 阶段 5: Runtime 重构计划
状态: complete

- 比较 OMP、LangGraph/LangChain、自研增强
- 推荐目标路线
- 制定黑箱验收矩阵和迁移步骤

### 阶段 6: 结论交付
状态: complete

- 汇总发现
- 给出不执行代码的重构计划
- 列出风险、前置问题和下一步建议

## 计划交付摘要

本轮已完成黑箱验证、源码归因、UI 重构方案和 Runtime 重构路线设计。未执行代码改造，符合 Task15 “先不要执行”的边界。

## Task15-2 执行阶段

### 阶段 7: Memory 架构污染审查
状态: complete

- 审查当前 `AnalysisMemoryStore` 和 `AgentMemory`
- 判断 Memory 是否会把旧分析路径污染到新需求
- 明确 OMP / agentmemory 取舍
- 将结论写入完整改造计划

### 阶段 8: Runtime / Spec / Analysis Contract 改造
状态: complete

- 扩展分析请求模型，加入时间粒度与目标一致性字段
- 修复 SpecBuilder，禁止把所有趋势请求降级为 7 天日度
- 收窄内置日度 analyzer 触发条件
- 引入通用月周天趋势 analyzer，支持月/周/日粒度
- 增加结果一致性观测字段，输出 requested/actual grain 与周期数量

### 阶段 9: UI Task15 精简改造
状态: complete

- 移除默认任务流卡片
- 移除右侧执行摘要
- 将右侧任务结果改为历史记录
- Memory/产物/调试信息降级为对话消息附件或 Debug drawer

### 阶段 10: 黑箱与 verification-loop 验证
状态: complete

- 黑箱运行 M678 三个月月度良率趋势
- 运行 Agent / Skill 相关单元测试
- 运行前端 typecheck / build
- 使用 Chrome 进行 UI 冒烟测试
- 按 verification-loop 输出检查结果

## Task15-2 最终目标 Checklist

- [x] Memory 不再参与选择分析粒度或执行策略，只能复用已确认文件/字段映射。
- [x] 未确认 Memory 不参与执行，只作为待确认候选显示。
- [x] SpecBuilder 能把“三个月/月度”保留为月度粒度和约 90 天范围。
- [x] data_analysis 普通路径能处理月/周/日粒度的月周天良率趋势。
- [x] 如果实际结果粒度与用户请求不一致，Runtime/Skill 返回失败或需要确认，不能显示“分析完成”。
- [x] 黑箱测试 M678 三个月月度良率趋势通过，最终答案为月度良率，不是一周日度。
- [x] UI 默认不展示后端固定 workflow/执行摘要。
- [x] 右侧为历史记录，业务结果在对话框内呈现。
- [x] 相关单元测试通过。
- [x] 前端 typecheck/build 通过。
- [x] Chrome 冒烟测试通过。

## Task15-3 执行阶段

### 阶段 11: M626 / OMP 失败归因
状态: complete

- 黑箱复现 “请分析M626近一周的良率变化趋势；如果有恶化，请给出恶化原因”
- 分析 Python runtime 失败点与 OMP fallback 失败点
- 判断是否是 OMP 不具备 ReAct、未命中本地数据，还是命令路径未解析

### 阶段 12: Runtime 可靠性修复
状态: complete

- 修复 OMP 命令解析，支持环境变量和 Windows 本机安装路径
- 修复 Memory candidate 对不同产品型号的误复用
- 修复 Resolver 使用 Memory 文件时缺少产品一致性检查的问题
- 增加对应单元测试，禁止 C522 记忆污染 M626 请求

### 阶段 13: 历史会话功能落地
状态: complete

- 新增 `.agent_workbench/conversations/*.json` 会话存储
- 新增 `GET/POST /api/conversations`
- 新增 `GET/PUT /api/conversations/:id`
- 前端右侧从 run 历史改为 conversation 历史
- 支持新对话、点击历史会话恢复、继续在该会话中提交新任务

### 阶段 14: Task15-3 验证
状态: complete

- 运行后端聚焦测试与 Agent/Skill 测试
- 运行前端 typecheck/build
- 通过真实 API 和 Chrome UI 烟测验证 M626 请求与历史会话恢复

## Task15-3 最终目标 Checklist

- [x] 明确 OMP 支持自定义任务调用：当前项目通过 `OmpJsonRuntime` 一次性 CLI prompt 调用 OMP；不是主 ReAct runtime。
- [x] 明确截图中 `OMP command not found: omp` 的直接原因：Next/Python 子进程 PATH 未解析到本机 OMP 安装。
- [x] 明确 M626 用例的上游根因：Python 路径先失败，因为 confirmed Memory / Resolver 错用了 C522 文件。
- [x] 修复 OMP fallback 的 Windows 命令解析。
- [x] 修复 Memory / Resolver 的产品型号一致性边界。
- [x] M626 黑箱 API 通过，runtime 为 `python`，未再触发 OMP 报错。
- [x] 右侧历史记录改为真实历史会话，可点击恢复并继续。
- [x] `.agent_workbench/` 已加入 `.gitignore`，避免本地会话数据误入版本库。
- [x] verification-loop 要求的相关测试和 Chrome UI 烟测通过。
