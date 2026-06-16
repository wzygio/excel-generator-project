# Task15 进度

## 2026-06-15

- 创建 Task15 planning 文件。
- 已读取 `docs/prompt/refactor-agent_arch.md` 中 Task15。
- 已读取 `design-taste-frontend`、`visionox-dashboard-ui` 和 `planning-with-files-zh` 技能说明。
- 已确认本轮边界：先做黑箱验证、架构归因和重构计划，不执行 Runtime/UI 改造。
- 已完成 M678 三个月月度良率黑箱测试，run id: `run-20260615-120059`。
- 已确认黑箱结果错误：TaskSpec 将“三个月/月度”降级成最近 7 天日度良率。
- 已检查 `runtime_adapter.py`、`runtime.py`、`omp_runtime.py`、`spec_builder.py`、`analysis_orchestrator.py` 和 `daily_yield_trend_analyzer.py`。
- 初步结论：当前默认 Runtime 是自研顺序 Skill runtime；OMP adapter 存在但不是默认成功路径；没有 ReAct 循环。
- 已确认 `omp` CLI 可调用，版本输出为 `omp v15.13.0`，本机 `Get-Command` 来源为 `C:\Users\V0141351\AppData\Local\omp\omp.exe`。
- 已完成 UI 精简方案：移除默认任务流/执行摘要，右侧改历史记录，业务结果只在对话中展示。
- 已完成 Runtime 重构方案：推荐 OMP 主 Runtime POC，保留 Python skill 作为 deterministic tools；LangGraph 作为第二路线。
- 已完成 Task15 计划交付，未执行代码改造。
- 开始 Task15-2 执行阶段。
- 已记录 Memory 架构结论：当前 Memory 有潜在污染风险，应收窄为 confirmed facts only，不引入重型 agentmemory。
- 已完成 Task15-2 改造：分析请求/Spec/Skill 增加 `time_grain` 与 `requested_periods`，Memory 增加粒度兼容匹配，Resolver 会规范化 `decrypted_files` 内非标准 xlsx。
- 已将内置良率趋势分析器扩展为月/周/日通用粒度，并增加实际粒度与请求粒度不一致时失败的 guard。
- 已完成 UI 精简：默认不再显示“任务流”“执行摘要”“任务结果”侧栏，右侧改为“历史记录/当前产物”，业务结果在对话消息内呈现。
- 最新黑箱通过：`run-20260615-125259`，输入为 M678 最近三个月月度良率趋势，Spec 为 `monthly/3`，输出为 M05/M06 月度良率与恶化原因线索。
- 验证通过：37 条聚焦后端单测、41 条 Agent/Skill 契约测试、touched-file Ruff、前端 `npm run typecheck`、`npm run build`、Chrome DOM 冒烟。
- 项目级 `uv run ruff check .` 仍失败于既有脚本/旧模块风格问题；`uv run pyright` 当前环境缺少 `pyright` 可执行文件。
- 开始并完成 Task15-3。
- 已复现 M626 截图问题：Python runtime 先因文件匹配错用 C522 源表失败，随后 fallback 到 OMP；Next 子进程 PATH 找不到 `omp`，返回 `OMP command not found: omp`。
- 已确认本机 OMP 存在，路径为 `C:\Users\V0141351\AppData\Local\omp\omp.exe`；修复 `OmpJsonRuntime` 后可通过默认 Windows 安装路径解析到 OMP。
- 已修复 `AnalysisMemoryStore`：confirmed 记忆如果产品型号不相交，直接不作为候选。
- 已修复 `AnalysisFileResolver`：使用 Memory candidate 的文件路径/文件名前，会再次检查文件名中的产品型号是否与请求一致。
- 已新增前端会话存储与 API：`.agent_workbench/conversations/*.json`、`/api/conversations`、`/api/conversations/:id`。
- 已将右侧历史记录改为历史会话列表，支持“新对话”、点击历史会话恢复消息与产物、继续追问。
- 已将 `.agent_workbench/` 加入 `.gitignore`。
- M626 API 黑箱通过：`run-20260615-134545`，runtime=`python`，源文件为 M626，输出包含 7 天良率、下降 -0.67 pct 和恶化原因线索。
- Chrome UI 烟测通过：UI 提交 M626 生成 `run-20260615-134749`，右侧出现 1 个历史会话；点击“新对话”后上下文清空，再点击历史会话可恢复 Run、消息与 2 个产物；控制台无 error。
- 验证通过：44 条聚焦后端单测、43 条 Agent/Skill 契约测试、touched-file Ruff、前端 `npm run typecheck`、`npm run build`。
