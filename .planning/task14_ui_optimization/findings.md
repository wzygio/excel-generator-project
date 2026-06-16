# Task14 UI 优化发现

## 需求理解

- 当前 UI 暴露了过多开发态信息：Pipeline、TaskSpec、执行链路、策略判定、Memory 等与业务用户的主任务关系较弱。
- task14 要求强化对话框、任务流、任务结果呈现。
- 报表下载和数据分析属于灵活业务模块，应在 UI 上整合为一个 Agent 输入入口。
- 日报生成属于固定业务流程，应作为明确快捷入口保留。
- 风格目标接近 ChatGPT Web 或 Codex，但仍应保持工业良率工作台的专业、克制和高可读性。

## Skill 约束

- `design-taste-frontend` 明确指出该 skill 不主要面向 dashboard，因此本次只采用其反模板化、布局节制、按钮对比、响应式和 copy 自审规则。
- `visionox-dashboard-ui` 与本项目更匹配：制造业、良率、质量分析、报表门户、操作型工作台。视觉策略应优先走密集、清晰、可扫描的工业分析语言。

## 现有截图观察

- 中间红框区域占据大量空间，展示 TaskSpec、执行链路、FineReport 管道、Excel 分析管道，造成业务主路径被稀释。
- 右侧结果区较有价值，但视觉上与 Memory、日报预览混杂，需要更清楚地突出“结果摘要、产物、下一步”。
- 侧边栏模块切换仍保留传统三模块感，不够像智能体统一入口。
- CopilotKit 浮窗存在，但主页面本身也需要成为一等 chatbox，而不是依赖右下角浮窗。

## 目标 Chatbox

- 顶部为简短上下文和状态，不做大 hero。
- 主区域是对话式输入与运行卡片：
  - 用户输入自然语言目标
  - Agent 生成任务计划摘要
  - UI 展示执行阶段：理解需求、选择能力、执行、整理结果
  - 默认只显示业务可读摘要
- 调试视图以 tabs/details 形式折叠：
  - Spec
  - Trace / routing
  - Memory
  - Raw result

## 前端架构审查

- `ui/copilotkit-agent/app/page.tsx` 当前将三模块按钮、TaskSpec、执行链路、管道卡片、结果、Memory、日志都放在首屏，导致任务主线被稀释。
- `/api/agent-runs` 接口接收 `goal`、`runtime:auto` 和 `options`，由 `scripts/agent_workbench_bridge.py` 创建 spec 并交给 `RuntimeRouter` 执行，适合做统一 Agent 输入。
- `/api/yield-skill` 仍可保留给 CopilotKit tool 或旧 skill 直接调用，但 task14 主界面优先使用 `/api/agent-runs`。
- `CopilotSidebar` 可保留，但不应默认打开抢占页面主 chatbox。

## 实现结果

- 主界面已从三模块调试面板改为 Agent Workbench：左侧任务入口，中间对话与输入，右侧结果和产物。
- 报表下载与数据分析在 UI 上合并为“智能任务”，统一提交到 `/api/agent-runs`，由 `runtime:auto` 和后端 `RuntimeRouter` 决定 skill。
- 日报生成作为固定流程入口保留在侧栏与 prompt chip 中。
- TaskSpec、Trace、Memory、Raw JSON、Logs 保留在折叠调试区，默认不打扰业务主路径。
- 数据分析结果优先使用后端 `data.result_text`，前端轻量渲染 Markdown 标题、列表与表格。
- 真实烟测中，prompt “请分析C522近一周的良率变化趋势；如果有恶化，请给出恶化原因” 成功路由到 `data_analysis`，生成趋势结论、2 个产物和 Memory 待确认项。
