# 任务计划：Task11 Agent Workbench 架构优化计划

## 目标
理解 `docs/prompt/refactor-agent_arch.md` 中 Task11/Task12 的要求，审查当前前后端是否匹配目标架构，明确 Pi/OMP 作为 Agent Runtime 的调用方式，并产出可确认的开发计划；本阶段不执行 Task13 开发改动。

## 当前阶段
阶段 6：Task13 实现与验证完成

## 各阶段

### 阶段 1：需求与现状发现
- [x] 读取 AGENTS.md 和 Task11 要求
- [x] 检查 `ui/copilotkit-agent` 前端结构
- [x] 检查现有 Agent 后端结构
- [x] 检查本地 `oh-my-pi` / `omp` CLI 可用性
- [x] 将发现记录到 findings.md
- **状态：** complete

### 阶段 2：差距分析
- [x] 对照目标架构图判断前端是否满足 Agent Workbench
- [x] 对照目标架构图判断后端 SpecBuilder / RunStore / Runtime / Memory / Adapter 是否满足
- [x] 识别必须改、可延后、不能动的边界
- **状态：** complete

### 阶段 3：开发计划输出
- [x] 列出准备修改或删除的文件
- [x] 按阶段拆分 Task12 可执行开发任务
- [x] 列出每阶段 focused tests
- [x] 列出风险和待用户确认问题
- **状态：** complete

### 阶段 4：交付确认
- [ ] 向用户交付 Task11 分析和计划
- [ ] 等待用户确认后再进入实现
- **状态：** in_progress

### 阶段 5：Task12 Pi/OMP Runtime 调研与计划完善
- [x] 搜索 OMP 和基础版 Pi 最新资料
- [x] 检查本机 `omp` 的 CLI/RPC/ACP 能力
- [x] 明确 OMP/Pi 作为 Runtime 的可调用方式
- [x] 将 Pi Runtime 集成方案补入计划
- **状态：** complete

### 阶段 6：Task13 实现与验证
- [x] 清理活跃 Streamlit 入口、依赖和启动脚本
- [x] 新增 SpecValidator、RuntimeRouter、OMP/Pi JSON Runtime adapter
- [x] 将 CopilotKit Workbench 主路径接入 `/api/agent-runs`
- [x] 让 SpecBuilder 支持 LLM 转换 + 代码校验，并为自由趋势分析生成 data_analysis-only TaskSpec
- [x] 将 data_analysis 输出 markdown 写入 `specs/runs/<run_id>/outputs/`
- [x] 完成 C522 近一周良率趋势的 CLI、bridge、Workbench 浏览器冒烟验证
- **状态：** complete

## 当前结构摘要

### 前端
- `ui/copilotkit-agent/` 是最新前端，技术栈为 Next.js + CopilotKit + React。
- `ui/copilotkit-agent/app/page.tsx` 负责 Agent Workbench 外壳：输入、模块切换、Spec 预览、执行链路、结果、Memory 反馈、产物下载。
- `ui/copilotkit-agent/app/api/copilotkit/route.ts` 负责 CopilotKit BuiltInAgent + DeepSeek 模型。
- `ui/copilotkit-agent/app/api/yield-skill/route.ts` 负责 Node -> Python bridge。
- `ui/copilotkit-agent/app/api/artifact/route.ts` 负责下载 artifact。

### 后端
- `src/yield_report/agent/spec_model.py` 定义 TaskSpec / SkillCall / SkillResult / RunContext。
- `src/yield_report/agent/spec_builder.py` 是规则版 SpecBuilder MVP。
- `src/yield_report/agent/run_store.py` 管理 `specs/runs/<run_id>/`。
- `src/yield_report/agent/runtime.py` 是自研轻量 Runtime。
- `src/yield_report/agent/memory.py` 是 data_analysis memory facade。
- `src/yield_report/agent/registry.py` 注册 `report_download`、`data_analysis`、`daily_report` 三个 Skill。
- `scripts/create_daily_report_spec.py` 和 `scripts/run_task_spec.py` 已存在。
- `scripts/copilotkit_skill_bridge.py` 仍直调单个 Skill，未走 SpecBuilder / RunStore / Runtime。

## 差距判断

| 架构节点 | 当前状态 | 是否满足目标 | 主要差距 |
|----------|----------|--------------|----------|
| User / Supervisor | 前端支持自然语言输入和 Memory 确认/拒绝 | 部分满足 | 缺少 Spec 确认和 run 级状态反馈 |
| Agent Workbench | CopilotKit UI 已有工作台外壳 | 部分满足 | 执行仍是三模块直调 Skill，不是 Spec run |
| Spec Builder | 已有规则版 `SpecBuilder` | 部分满足 | 缺少 LLM 转换、代码校验、可解释校验错误 |
| Run Store | 已有 `RunStore` | 基本满足 | 前端 bridge 未使用它 |
| Agent Runtime | 已有自研 `AgentRuntime`，本地 `omp` 可用 | 部分满足 | 未适配 OMP/ACP，未定义 Runtime Adapter |
| Python Skills | 三个 Skill 已保留 | 基本满足 | bridge 绕过 Spec workflow，日报链路仍需更完整闭环 |
| Agent Memory | `AgentMemory` facade 已有 | 部分满足 | 仅 data_analysis，缺少跨 Skill schema、review、trace 记录 |
| Stable Adapters | 旧 application/core/infrastructure 可复用 | 部分满足 | adapters 目录尚未成为明确外部系统边界 |

## Task12 结论：Pi/OMP 可作为 Runtime

### 可调用方式
| 方式 | OMP 当前可用性 | 适合度 | 推荐用途 |
|------|----------------|--------|----------|
| `omp -p "..."` | 可用 | 中 | 一次性复杂分析或 coding fallback，最易实现但流式和状态弱 |
| `omp --mode json "..."` | 可用 | 中高 | 一次性运行并收集 JSONL 事件，适合写入 `trace.jsonl` |
| `omp --mode rpc --no-session --no-tools` | 已验证输出 `{"type":"ready"}` | 高 | 后端托管长生命周期 agent 子进程，发送 prompt、监听事件 |
| `omp acp` | 可用 | 中 | 面向 ACP client；当前项目没有 ACP client，暂列后续 |
| Pi SDK | 基础版 Pi 官方支持 | 中 | 需要 Node/TS 后端深集成时考虑；当前 Python 后端先不引入 |

### 推荐落地模型

```text
CopilotKit UI
  -> /api/agent-runs
  -> Python bridge
  -> SpecBuilder: LLM/规则生成 TaskSpec + SpecValidator
  -> RunStore: specs/runs/<run_id>/
  -> RuntimeRouter
       ├─ OmpRpcRuntime: 复杂业务推理、需要 coding/fix/自由分析时
       └─ PythonSkillRuntime: 稳定 Skill 执行与兜底
  -> trace / run_summary / outputs / memory_candidates
```

### Runtime 选择策略
| 场景 | Runtime |
|------|---------|
| 固定日报生成、已知 workflow、只需执行 Skill | PythonSkillRuntime |
| 用户提出复杂自由分析、现有 Skill 输入不足、需要动态 coding | OmpRpcRuntime |
| SpecBuilder LLM 转换失败或校验失败，需要 Agent 修复 Spec | OmpRpcRuntime |
| OMP 未配置模型、超时、输出不可解析 | PythonSkillRuntime 或 `needs_confirmation` |

### 安全边界
- OMP/Pi 没有内置沙箱，不能直接把终端用户自由输入交给全权限 agent。
- 后端调用 OMP 时必须使用 run-scoped prompt，明确只能读写 `specs/runs/<run_id>/` 和必要的只读源表路径。
- 初版 OMP Runtime 建议使用 `--no-session`、专用 `--session-dir specs/runs/<run_id>/pi-session`、受限 `--tools read,grep,find,bash` 或按阶段扩展。
- 对需要写文件的任务，先要求 OMP 写到 `specs/runs/<run_id>/outputs/`，再由 Python 校验 artifact manifest。

## 准备修改或删除的文件

### 前端与接口
| 文件 | 动作 | 目的 |
|------|------|------|
| `ui/copilotkit-agent/app/page.tsx` | 修改 | 从本地 draft Spec 改为后端返回的真实 Spec/Run 状态 |
| `ui/copilotkit-agent/app/api/yield-skill/route.ts` | 替换或降级为兼容入口 | 新主入口应走 Spec run，而不是单 Skill |
| `ui/copilotkit-agent/app/api/agent-runs/route.ts` | 新增 | 创建 spec、启动 run、返回 run summary |
| `ui/copilotkit-agent/app/api/agent-runs/[runId]/route.ts` | 新增 | 查询 run 状态、trace、artifacts、memory candidates |
| `ui/copilotkit-agent/app/api/artifact/route.ts` | 修改 | 优先只允许下载 `specs/runs/<run_id>/outputs/` 内产物 |
| `ui/copilotkit-agent/README.md` | 修改 | 更新运行、接口和验证说明 |

### Streamlit 清理
| 文件 | 动作 | 目的 |
|------|------|------|
| `app/main.py` | 删除 | 移除旧 Streamlit 三 Tab UI |
| `app/utils/*` / `app/__init__.py` | 删除或迁移仍被复用的工具 | 移除 Streamlit 专用启动、日志、热重载 |
| `start_streamlit.bat` / `start_test.bat` / `run_hidden.vbs` | 删除 | 移除 Streamlit 启动脚本 |
| `pyproject.toml` / `uv.lock` | 修改 | 移除 `streamlit` 依赖和 hatch package 中的 `app` |
| `ARCHITECTURE.md` / `AGENTS.md` / `docs/observability.md` | 修改 | 将 UI、命令、验证从 Streamlit 更新为 CopilotKit |
| `src/excel_generator_project/app/*` | 待确认 | V1 legacy Streamlit 内容；默认先从文档和构建入口脱钩，不主动删除兼容历史 |

### 后端 Agent
| 文件 | 动作 | 目的 |
|------|------|------|
| `src/yield_report/agent/runtime.py` | 修改 | 抽象 Runtime 接口，保留 PythonSkillRuntime |
| `src/yield_report/agent/omp_runtime.py` | 新增 | 封装 `omp` CLI / ACP 调用，输出结构化结果 |
| `src/yield_report/agent/runtime_adapter.py` | 新增 | 根据配置选择 python skill runtime 或 OMP runtime |
| `src/yield_report/agent/spec_builder.py` | 修改 | 增加 LLM 转换 + code validation full path |
| `src/yield_report/agent/spec_validation.py` | 新增 | 校验 schema、workflow、skill、depends_on、outputs、memory policy |
| `src/yield_report/agent/memory.py` | 扩展 | 从 data_analysis facade 扩展为跨 Skill memory facade |
| `src/yield_report/agent/memory_store.py` | 新增 | confirmed/pending/rejected 记录存储和查询 |
| `src/yield_report/adapters/*` | 新增或逐步迁移 | 明确 FineReport / Excel / LLM / AgentRuntime 适配边界 |
| `scripts/create_daily_report_spec.py` | 修改 | 支持 LLM/规则模式、打印校验错误、返回 run path |
| `scripts/run_task_spec.py` | 修改 | 支持 `--runtime python|omp|auto` 和 run summary 输出 |
| `scripts/copilotkit_skill_bridge.py` | 修改或替换 | 改为 agent run bridge，兼容旧单 Skill action |

### 测试
| 文件 | 动作 | 目的 |
|------|------|------|
| `tests/unit/agent/test_spec_builder.py` | 扩展 | LLM JSON -> TaskSpec、fallback、校验错误 |
| `tests/unit/agent/test_spec_validation.py` | 新增 | 独立验证 Spec 校验规则 |
| `tests/unit/agent/test_runtime.py` | 扩展 | Runtime adapter 与 run-scoped artifacts |
| `tests/unit/agent/test_omp_runtime.py` | 新增 | mock `subprocess.run` 验证 OMP CLI 调用和错误处理 |
| `tests/unit/agent/test_memory.py` | 新增或扩展 | pending/confirmed/rejected 跨 Skill memory |
| `tests/unit/test_copilotkit_agent_bridge.py` | 新增 | Node/Python bridge payload contract，可用 Python 侧桥接测试替代 |
| `ui/copilotkit-agent` typecheck/build | 运行 | 验证前端接口变更 |

## Task12 建议开发阶段

### A. Streamlit 清理和文档对齐
1. 删除活跃 Streamlit 入口和启动脚本。
2. 从依赖和构建配置移除 `streamlit`、`app` package。
3. 更新 `ARCHITECTURE.md`、`AGENTS.md`、`docs/observability.md` 的 UI 命令和测试说明。
4. Focused tests：`uv run ruff check pyproject.toml` 不适用；实际运行 `uv sync --locked` 或 `uv lock` 视依赖策略确认后执行，外加 `npm run typecheck`。

### B. 前端改为真实 Agent Workbench
1. 新增 `agent-runs` API route：自然语言目标 -> 调后端创建 spec -> 返回 `run_id/spec/status`。
2. 页面 Spec 预览改用后端返回的 `spec.yaml` JSON/YAML，不再本地伪造。
3. 页面运行步骤读取 `run_summary.json` / `trace.jsonl`，产物下载从 run outputs 来。
4. Focused tests：`npm run typecheck`、`npm run build`。

### C. SpecBuilder full path
1. 增加 LLM prompt，将自然语言转成 TaskSpec draft。
2. 用 `TaskSpec` Pydantic + `SpecValidator` 做代码级校验。
3. LLM 输出不可信：只接受 JSON/YAML 数据，不执行模型生成的代码。
4. 失败时返回 validation issues，允许前端展示 `needs_confirmation`。
5. Focused tests：`uv run pytest tests/unit/agent/test_spec_builder.py tests/unit/agent/test_spec_validation.py -v --tb=short`。

### D. Runtime Adapter + OMP 评估落地
1. 定义 runtime protocol：`run(spec, context) -> RuntimeRunResult`。
2. 保留现有 Python Skill Runtime 作为稳定工具执行器。
3. 新增 `OmpRpcRuntime`：首选 `omp --mode rpc --no-session --cwd <workspace>`，通过 stdin/stdout JSONL 发送 prompt 和收集事件。
4. 新增 `OmpJsonRuntime` 或 one-shot helper：用于简单 fallback，调用 `omp --mode json -p` 收集 JSONL。
5. OMP prompt 只允许读取指定 `spec.yaml`、写入 run 目录、调用白名单脚本，不给前端自由 shell 权限。
6. 当 OMP 无结构化输出、未登录、超时或产物校验失败时，标记 `needs_confirmation` 或 fallback 到 PythonSkillRuntime。
7. Focused tests：mock subprocess 的 `tests/unit/agent/test_omp_runtime.py`，加 `tests/unit/agent/test_runtime.py`。

### E. Memory 完整闭环
1. 定义统一 memory record：scope、skill、kind、summary、evidence、status、created_from_run、confirmed_by、timestamps。
2. pending candidate 写入 `specs/runs/<run_id>/memory_candidates.json`。
3. confirmed memory 写入持久 store，仅 confirmed 允许自动复用。
4. 前端确认/拒绝 action 走 run-scoped memory endpoint，并写 trace。
5. Focused tests：`uv run pytest tests/unit/agent/test_memory.py tests/unit/skills/test_data_analysis_skill.py -v --tb=short`。

### F. Adapter 层收敛
1. 先新增薄 adapter facade，不搬空旧 `application/core/infrastructure`。
2. FineReport adapter 包装 RPA/download；Excel adapter 包装解密、schema、读写；LLM adapter 包装 `llm_manager`；Agent runtime adapter 包装 Python/OMP。
3. Skill 内部逐步依赖 adapter facade，保持旧 public entrypoints 可用。
4. Focused tests：`uv run pytest tests/unit/skills tests/unit/agent -v --tb=short`，必要时补现有 orchestrator 回归测试。

### G. 前后端接口联调和烟测
1. 创建 spec：前端输入 -> `specs/runs/<run_id>/spec.yaml`。
2. 执行 run：`trace.jsonl`、`run_summary.json`、`outputs/` 都在同一 run 目录。
3. 完成数据分析任务闭环：至少 `data_analysis` 能通过 Workbench 完成并返回 summary/artifact/memory candidate。
4. Focused tests：Python agent/skill tests + `npm run build`；Task12 最后再做 Playwright UI smoke。

## 验收标准
- Streamlit 活跃入口、启动脚本、依赖和文档命令清理完成。
- `ui/copilotkit-agent` 是唯一前端入口。
- 前端创建真实 `specs/runs/<run_id>/spec.yaml`，不再只显示伪 Spec。
- `scripts/run_task_spec.py --spec ...` 和前端 API 使用同一 RunStore 目录规范。
- `omp` 集成有可测试 adapter；不能稳定使用时有明确 fallback。
- 三个 Python Skill 保留，旧 `application/core/infrastructure` 不删除。
- `data_analysis` 至少能从 Workbench 完成一次 run，并产生 trace/summary/artifacts/memory candidates。

## 风险
- OMP CLI 的 JSON/RPC 输出和工具权限需要进一步 spike，不能假设它天然适配 Web 后端。
- OMP 如果以工程 Agent 身份运行，权限边界过大；必须限制 cwd、tools、prompt 和输入文件。
- 删除 Streamlit 可能牵涉 V1 legacy 包和 hatch build package，需要先确认是否只删除活跃 UI。
- `uv.lock` 更新会比较大，需单独检查 diff。
- CopilotKit route 当前直接读取 `.env` 中 DeepSeek key；接口调整时不能打印或泄漏 secrets。

## 关键问题
1. `oh-my-pi` 是否能通过本地 CLI 稳定读入 TaskSpec 并执行 Python Skill？
2. 前端是否已经围绕 Agent Workbench 工作流组织，还是仍保留工具式/演示式接口？
3. Memory 是否要在 Task12 落地完整系统，还是先实现 confirmed-only + pending-review 的最小闭环？

## 已做决策
| 决策 | 理由 |
|------|------|
| Task11 只做分析和计划，不修改产品代码 | `docs/prompt/refactor-agent_arch.md` 明确 Task11 目标是理解、制定计划、先不要执行 |
| 使用 `.planning/task11_agent_arch/` 隔离规划文件 | 避免覆盖仓库根目录或已有计划文件 |

## 遇到的错误
| 错误 | 尝试次数 | 解决方案 |
|------|---------|---------|
| 暂无 | 0 | 暂无 |

## 备注
- 后续实现前需用户确认计划。
- 规划文件是工作记忆，不代表已开始产品代码改动。
