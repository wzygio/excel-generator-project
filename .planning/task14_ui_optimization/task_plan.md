# Task14 UI 优化计划

## 目标
将当前良率日报 Agent 工作台从“开发者调试面板优先”调整为“Agent 对话与任务结果优先”。最终界面应接近 ChatGPT/Codex Web 的工作台形态：用户在主 chatbox 输入自然语言需求，Agent Runtime 判断调用报表下载或数据分析等灵活 skill；右侧展示任务状态、结果和产物；Spec、Pipeline、Memory、判定理由等内部信息折叠到调试视图中。

## 设计读取
Reading this as: 工业良率 Agent Workbench for 良率工程师、工艺工程师和日报使用者, with 中高信息密度, using the Visionox industrial analytics language with a ChatGPT/Codex-like conversation shell.

## 阶段

### 阶段 1: 前端架构审查
状态: complete

- 阅读 `ui/copilotkit-agent/app/page.tsx`
- 阅读 `globals.css`、`layout.tsx`
- 明确现有 API 入口和当前状态模型
- 记录冗余信息与需要保留的调试内容

### 阶段 2: 目标 Chatbox 方案
状态: complete

- 主输入区整合报表下载与数据分析
- 快捷意图保留为 chips 或模式选择
- 日报生成保留为固定流程快捷入口
- 运行后显示任务流摘要、当前状态、结果和下载产物
- Debug 内容移入折叠区域或独立 tab

### 阶段 3: UI 实现
状态: complete

- 重构页面布局为左侧会话/中间主工作区/右侧结果栏
- 将 Pipeline、TaskSpec、执行链路、Memory 等调试信息降级到 Debug drawer
- 优化按钮、输入框、状态、空态、加载态和结果呈现
- 保持现有 API 与业务功能可用

### 阶段 4: 验证
状态: complete

- 运行 `npm run typecheck`
- 运行 `npm run build`
- 使用 Playwright 本地 Chrome 访问 `http://localhost:3000`
- 测试 chatbox 输入“请分析C522近一周的良率变化趋势；如果有恶化，请给出恶化原因”
- 检查页面无明显重叠、溢出、空白错位和控制台错误

结果: `npm run typecheck` 通过；`npm run build` 通过，保留既有 Turbopack NFT trace 警告；本地 Chrome 完成桌面与移动烟测，chatbox 成功触发 `/api/agent-runs` 并由 Runtime 路由到 `data_analysis`。

## 验收标准

- 首屏重点是 chatbox、任务状态与结果，而不是 Spec/Pipeline
- 灵活模块在 UI 上合并为“智能任务”，由后端 runtime/API 判断 skill
- 日报生成作为固定流程入口清晰保留
- 调试信息仍可查看，但默认不干扰业务使用
- 桌面与移动宽度下文本不溢出，按钮不换行到不可读状态
- 类型检查、构建、浏览器烟测通过
