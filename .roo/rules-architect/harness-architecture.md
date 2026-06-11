# Harness 架构指南（Architect 模式）

> 目的：让 Architect 模式在本项目中按 `.roorules` 渐进式披露工作，输出可交给 Code 模式执行的计划和设计更新。

## 1. 当前 Harness 结构

```text
excel-generator-project/
├── .roorules                              # Harness 总路由
├── .roo/
│   ├── rules-architect/harness-architecture.md
│   └── rules-code/knowledge-summarization.md
├── ARCHITECTURE.md                        # 系统架构总览
├── CONTEXT.md                             # Agent 领域语言
├── docs/
│   ├── agent/                             # Agent / Skill / Spec 契约
│   ├── design/                            # 领域设计、边界、开发纪律
│   ├── plans/                             # 长期计划和计划索引
│   ├── exec-plans/
│   │   ├── active/                        # 当前执行计划
│   │   └── completed/                     # 历史执行计划
│   ├── generated/                         # 可重建审计、Harness 清理记录
│   ├── observability.md                   # trace / log / smoke / diagnostics 入口
│   └── prompt/                            # 专项 prompt / skill 经验
├── specs/
│   ├── templates/daily_report_spec.yaml   # Spec 模板
│   └── runs/                              # 运行态 Spec / trace / outputs（忽略）
├── src/
│   ├── shared_kernel/                     # 配置、LLM、共享基础能力
│   ├── yield_report/
│   │   ├── agent/                         # TaskSpec、Router、Runtime、Trace、Memory
│   │   ├── skills/                        # report_download / data_analysis / daily_report
│   │   ├── application/                   # 兼容编排层
│   │   ├── core/                          # 纯解析、策略、业务时间等判断
│   │   └── infrastructure/                # FineReport、Excel、文件、代码执行、日志
│   └── excel_generator_project/           # V1 兼容实现
└── tests/
    └── unit/                              # 当前测试主目录，含 agent/skills 子目录
```

## 2. Architect 前置阅读

按任务范围渐进加载，不要一次性读全仓库：

1. 必读：`.roorules`、`ARCHITECTURE.md`、`CONTEXT.md`。
2. Agent / Skill / Spec 相关：读 `docs/agent/architecture.md`、`skill_contract.md`、`spec_contract.md`。
3. 领域或设计相关：从 `docs/design/index.md` 进入，不在根入口硬编码业务文件。
4. 计划相关：先读 `docs/plans/index.md`，当前执行计划进入 `docs/exec-plans/active/`。
5. 可观测性或验证相关：读 `docs/observability.md`。
6. FineReport / RPA 相关：读 `docs/prompt/skill-fr_rpa.md`，并优先复用 `fr_web_automation`。

## 3. 规划输出规则

| 输出类型 | 目标位置 | 说明 |
|----------|----------|------|
| 长期计划 | `docs/plans/<name>.md` | 产品、架构或阶段性长期计划 |
| 当前执行计划 | `docs/exec-plans/active/<name>.md` | 用户确认后的当前实现计划 |
| 历史执行计划 | `docs/exec-plans/completed/<name>.md` | 完成、验证并由用户接受后的执行计划 |
| 架构变更 | `ARCHITECTURE.md` 与对应 `docs/design/*.md` | 仅在用户要求或实施后确认需要同步时更新 |
| Agent 契约变更 | `docs/agent/*.md` | 修改 Runtime、Skill、Spec 契约时同步 |
| Spec 模板变更 | `specs/templates/*.yaml` | 只沉淀可复用模板，不提交 `specs/runs/` |
| Prompt / 经验沉淀 | `docs/prompt/*.md` | 专项流程、RPA经验、工具经验 |
| Harness 清理记录 | `docs/generated/harness-garbage-collection.md` | 记录过期入口、完成计划迁移、失效引用和待清理项 |

计划文档最少包含：目标、当前状态、实施步骤、涉及接口/数据流、验证方式、风险与回滚。

制定非平凡计划后，先请用户确认；确认通过后再写入或更新 `docs/plans/` 或 `docs/exec-plans/active/`。

## 4. 架构判断红线

- 区分 **Task Chain** 与 **Rule Iteration Mechanism**：`daily_report > data_analysis > report_download` 是运行顺序，不等于用户可自由改规则。
- Spec 只表达用户目标、输入、约束和 workflow；不要把浏览器点击、Excel 逐格操作或任意 Python 代码写进 Spec。
- Skill 必须有稳定 request/result/error/artifact 契约；不要把 `SKILL.md` 当成唯一实现。
- Core 层保持纯判断，不直接依赖 FineReport、Excel、Playwright、文件 IO。
- 配置变更必须先改 Pydantic V2 模型，再改 `config/global.yaml`。
- 新增依赖必须写入 `pyproject.toml`，并说明为什么不能复用现有依赖。
- 运行产物进入 `.gitignore` 覆盖目录：`output/`、`downloads/`、`specs/runs/`、`resources/decrypted_files/`。

## 5. 与 Code 模式协作

Architect 模式负责 Explore 和 Plan；Code 模式负责实现、测试、知识归纳。

```text
Explore -> Plan -> Code -> Commit
```

交付给 Code 模式的计划必须决策完整：明确要改的行为、接口、数据流、失败处理、测试命令和不应修改的边界。
