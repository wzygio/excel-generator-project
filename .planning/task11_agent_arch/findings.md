# 发现与决策：Task11 Agent Workbench

## 需求
- Task11 要求先理解并规划，不执行实现。
- 需要覆盖前端 Streamlit 移除、`ui/copilotkit-agent` 架构审查、`oh-my-pi`/`omp` Runtime 可用性、SpecBuilder 完整版、Memory 系统、Adapter 层、前后端接口适配。
- Task12 强调 Pi 是关键元素：需要搜索最新资料并明确 OMP 或基础版 Pi 如何作为 Agent Runtime 被调用，或者明确不可作为 Runtime 的原因，并继续完善计划。

## 研究发现
- `docs/prompt/refactor-agent_arch.md` 的 Task11 明确要求：删除 Streamlit 相关内容；分析 `ui/copilotkit-agent`；评估本地 `oh-my-pi` 是否能通过 CLI 作为 Agent Runtime；优化 Spec Builder、Memory、Adapter；检查前后端接口；本任务只创建开发计划，不执行实现。
- 前端当前是 Next.js + CopilotKit：`ui/copilotkit-agent/package.json` 提供 `dev/build/typecheck`，依赖 `@copilotkit/*`、Next 16、React 19。
- `ui/copilotkit-agent/app/page.tsx` 已经具备 Agent Workbench 外壳：自然语言输入、模块切换、TaskSpec 预览、执行链路、结果、产物下载、Memory 确认/拒绝按钮。
- 但前端 `buildSpecPreview()` 只是本地临时 JSON draft；提交执行仍调用 `/api/yield-skill`，没有真正创建 `specs/runs/<run_id>/spec.yaml`，也没有调用 `scripts/run_task_spec.py` 或后端 RunStore。
- `/api/yield-skill` 通过 Node `spawn(uv run python scripts/copilotkit_skill_bridge.py)` 调 Python bridge；bridge 直接调单个 Skill，产物默认仍到 `output/`，并未进入 `specs/runs/<run_id>/outputs/`。
- `/api/copilotkit` 当前只创建 CopilotKit BuiltInAgent + DeepSeek 兼容模型；它不是项目 TaskSpec Runtime，也没有连接 RunStore/SpecBuilder。
- 后端 `src/yield_report/agent/` 已有 `SpecBuilder`、`RunStore`、`AgentRuntime`、`AgentMemory`、`TraceWriter`、`TaskSpec` 模型和三个 Skill registry。
- 当前 `SpecBuilder` 是规则/MVP 版本：正则识别产品、简单日期解析、固定本地源表和固定 workflow；尚未实现“LLM 转换 + 代码校验”。
- 当前 `RunStore` 已能把 `spec.yaml`、`trace.jsonl`、`outputs/`、`memory_candidates.json`、`run_summary.json` 收敛到 `specs/runs/<run_id>/`。
- 当前 `AgentRuntime` 是自研轻量 Runtime，可执行已注册 Skill、写 trace、写 run_summary 和 memory_candidates。
- 当前 `AgentMemory` 只是 data_analysis 现有 JSON memory store 的 facade，不是跨 Skill 的统一 memory 模型。
- 本机只有 `omp` 命令可用，未发现 `oh-my-pi` 或 `pi` 命令；`omp --version` 返回 `omp/15.13.0`。
- `omp --help` 显示支持非交互 `-p`、`--mode text/json/rpc/rpc-ui`、`--cwd`、`--tools`、skills/rules、`acp` stdio server；理论上可作为外部 Agent Runtime，但项目尚无 OMP/ACP client 或 TaskSpec 到 OMP session 的适配层。
- 本机 `omp config path --json` 返回 `C:\Users\V0141351\.omp\agent`，说明 OMP 有独立用户级配置目录。
- 本机 `omp --mode rpc --no-session --no-tools` 可启动并输出 `{"type":"ready"}`，说明它可以被后端作为 stdio JSONL 子进程 Runtime 托管。
- OMP 的 `acp` 子命令可作为 Agent Client Protocol stdio server：`omp acp`，更适合未来接入支持 ACP 的编辑器/客户端，但当前项目前端和 Python 后端没有 ACP client。
- 基础版 Pi 官方文档显示它是极简 terminal coding harness，核心小，依赖 TypeScript extensions、skills、prompt templates、themes 和 packages 扩展；支持 `pi -p`、`pi --mode json`、`pi --mode rpc`、SDK、`@file` 参数和工具白名单。
- Pi RPC 模式是 JSON over stdin/stdout：后端可以发送 `{"id":"...", "type":"prompt", "message":"..."}`，通过 `response` 和事件流获取执行过程；JSON event stream 模式适合一次性 run 的事件收集。
- Pi/OMP 都没有内建安全沙箱；官方文档明确说工具以进程权限读写文件和执行命令。对本项目而言，Pi Runtime 必须限制 cwd、tools、session-dir、prompt 和可写目录，必要时用容器/VM/OpenShell。
- `ARCHITECTURE.md`、`AGENTS.md`、`docs/observability.md`、`pyproject.toml`、`start_streamlit.bat`、`start_test.bat`、`app/` 和 `src/excel_generator_project/app/` 仍包含 Streamlit 内容；这与 Task11 的“前端系统已经不再使用 Streamlit”不一致。
- 既有设计 `docs/design/design-agent_runtime.md` 提醒：把工程 Agent CLI 直接作为面向用户的数据分析后端有安全、会话、并发、产物归档等风险；Task11 若采用 OMP，应定位为受控 Runtime 适配器，而不是让前端直接把自由输入交给有全项目权限的 CLI。

## 技术决策
| 决策 | 理由 |
|------|------|
| Task11 不进行实现 | 用户要求通过 plan-with-files-zh 创建开发计划，先不要执行 |
| 计划建议保留 Python Skill 和 RunStore，新增 Runtime Adapter | 现有 Skill/Spec/RunStore 已可用，直接删除自研 Runtime 风险大；用 Adapter 让 OMP 可插拔更稳 |
| OMP/Pi 是 Task12 的关键 Runtime 方向 | OMP 已安装且支持 RPC/JSON/ACP；基础版 Pi 文档证明其也能通过 CLI/RPC/SDK 嵌入 |
| OMP 作为主 Agent Runtime 候选，Python Skill Runtime 作为稳定工具执行兜底 | Pi/OMP 能处理复杂业务推理和 coding，但稳定日报 Skill 仍应保留为可调用工具 |
| 前端应从 `/api/yield-skill` 直调 Skill 改为 `/api/agent-runs` Spec run 工作流 | 目标架构需要自然语言 -> SpecBuilder -> RunStore -> Runtime -> artifacts |
| Runtime 集成优先采用 OMP RPC 子进程，后续再考虑 ACP/SDK | 本机已验证 RPC ready；Python 后端接 stdio JSONL 比接 ACP/Node SDK 更小步 |

## 遇到的问题
| 问题 | 解决方案 |
|------|---------|
| 未找到 `oh-my-pi` 或 `pi` 命令 | 以实际可用的 `omp` CLI 作为 oh-my-pi 命令入口评估 |
| 找不到用户目录下 `MEMORY.md` | 不使用外部记忆作为依据，改以仓库文件和 CLI 输出为依据 |

## 资源
- `AGENTS.md`
- `docs/prompt/refactor-agent_arch.md`
- `ARCHITECTURE.md`
- `docs/agent/architecture.md`
- `docs/agent/spec_contract.md`
- `docs/agent/skill_contract.md`
- `ui/copilotkit-agent/`
- `src/yield_report/agent/`

## 视觉/浏览器发现
- 用户给出的目标架构图表达链路：User/Supervisor -> Streamlit/Agent Workbench -> Spec Builder -> Run Store -> Agent Runtime -> Python Skills + Agent Memory -> Stable Adapters / Existing Implementation。

---
*每执行2次查看/浏览器/搜索操作后更新此文件*
