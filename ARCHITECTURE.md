# 良率日报自动生成系统架构

## 项目定位

本项目是面向 OLED 良率日报工作的自动化系统。它把自然语言需求转成可追踪的任务规格，调用本地 Skill 与 FineReport RPA 下载源表，分析 Excel 数据，并生成可下载、可审计的良率报告产物。

本项目不是通用 BI 平台。优先选择显式、可测试、可追踪的报表工作流，而不是宽泛的自动推断。

## 运行主链路

```text
用户需求
  -> TaskSpec
  -> Agent Runtime
  -> Skill Tool
  -> SkillResult
  -> Trace / Memory / Output
```

## 架构原则

| 原则 | 说明 |
|---|---|
| Spec 驱动 | 用户目标先固化为任务规格，运行时消费规格并产出 trace、memory 和 artifact。 |
| Skill 承载稳定能力 | 高频、重复、可测试的报表能力沉淀为 Python Skill，而不是让模型每次自由发挥。 |
| Letta / LangGraph 分工 | Letta 承载需要状态和工具调用的 Agent Runtime；LangGraph 承载 Spec 生成与修复图。 |
| FineReport RPA 边界清晰 | 门户、浏览器、下载和 Excel IO 属于基础设施或 Skill 边界，不进入纯领域判断。 |
| Harness 渐进披露 | 根文档只负责定位和路由，详细业务、设计、开发、测试资料进入 `references`。 |
| CodeGraph 负责深定位 | 根架构只下探到二级路径；具体符号、调用链和文件级追踪交给 CodeGraph。 |

## 项目二级路径地图

| 路径 | 职责 |
|---|---|
| `app/` | 旧应用入口与兼容工具区。 |
| `app/utils/` | 旧入口的辅助工具。 |
| `config/` | 项目配置输入。 |
| `config/products/` | 产品级配置。 |
| `data/` | 本地数据与记忆缓存。 |
| `data/memory/` | Agent 记忆相关数据。 |
| `docs/` | 开发提示、历史文档和待迁移资料。 |
| `docs/dev_prompt/` | 当前开发任务提示。 |
| `docs/generated/` | 历史生成资料；新 Harness 生成资料迁往 references。 |
| `output/` | 运行输出、下载和调试产物；通常不提交。 |
| `output/downloads/` | 下载输出。 |
| `output/logs/` | 日志输出。 |
| `references/` | 当前 Harness 主目录。 |
| `references/design/` | 系统、模块、功能设计引用。 |
| `references/dev_references/` | 开发规范、限制、表结构和模板引用。 |
| `references/test_references/` | 验收、测试、可观测性和调试引用。 |
| `resources/` | 用户源表、模板和 RPA 下载结果。 |
| `resources/decrypted_files/` | 解密后的 Excel 工作文件。 |
| `scripts/` | 可执行脚本和工作台桥接入口。 |
| `specs/` | TaskSpec 模板与运行记录。 |
| `specs/runs/` | 单次任务运行目录。 |
| `specs/templates/` | 可复用任务规格模板。 |
| `src/` | Python 源码。 |
| `src/yield_report/` | 当前良率日报 Agent、Skill、应用、领域和基础设施实现。 |
| `src/excel_generator_project/` | V1 兼容实现。 |
| `tests/` | 自动化测试入口。 |
| `tests/unit/` | 单元和边界测试。 |
| `tests/integration/` | 集成测试。 |
| `ui/` | 前端入口。 |
| `ui/copilotkit-agent/` | CopilotKit Agent Workbench。 |

## 用户可见能力

| 能力 | 说明 |
|---|---|
| 报表下载 | 解析报表类型、日期和产品型号，调用 FineReport RPA 下载源表。 |
| 数据分析 | 基于已下载 Excel 源表，选择代码执行或 LLM 直接分析策略。 |
| 日报生成 | 调用日报生成 Skill，产出最终 Excel 日报和运行 trace。 |
| 异常监控 | 通过固定工作流执行异常监控相关规格。 |

## Agent 边界

| 边界 | 说明 |
|---|---|
| Spec Builder | 从用户目标生成 TaskSpec；复杂修复走 LangGraph Spec 图。 |
| Runtime Router | 根据任务类型选择 Letta Runtime 或受控 Python Skill Runtime。 |
| Client Tools | 只暴露白名单业务能力，未知工具和未知 workflow fail closed。 |
| Skill Registry | 汇总可调用业务 Skill，保持输入输出契约稳定。 |
| Run Store | 保存任务规格、trace、summary、memory candidate 和 artifacts。 |

## Harness 边界

| 文档 | 角色 |
|---|---|
| `AGENTS.md` | 稳定的 Context Router 与 Iteration Router。 |
| `ARCHITECTURE.md` | 二级路径项目地图和架构边界。 |
| `references/` | 业务、设计、开发、测试和反馈引用。 |
| `tests/` | Harness 与代码行为的可执行验证。 |

## 技术栈摘要

| 分类 | 技术 |
|---|---|
| Python | Python 3.11+, Pydantic v2, pandas, openpyxl, xlsxwriter, pywin32 |
| Agent | Letta client, LangGraph, local Skill Runtime |
| LLM | OpenAI SDK 兼容提供商与 Gemini SDK，通过共享 LLM 管理器访问 |
| RPA | Playwright, fr-web-automation |
| UI | CopilotKit, Next.js |
| 工程 | uv, pytest, ruff, pyright |

## Common utilities boundary

Reusable infrastructure comes from the local editable `fr-common-utils` dependency and uses
the canonical `fr_common_utils` namespace. This project currently consumes only the core
logging API, so it declares no `db` or `excel` extra. Project configuration models and policy,
the structured rotating logger, report workflows, and LLM/Codex adapters remain under
`yield_report.shared_kernel`; the top-level `shared_kernel` name is reserved for package
compatibility and is not used by project code.

## 验证入口

| 场景 | 入口 |
|---|---|
| Harness / 文档 | focused Harness tests, diff inspection, referenced-path checks |
| Agent / Skill | unit tests for Agent and Skill boundaries |
| FineReport / 下载 | focused RPA and download tests; browser smoke only when portal flow changes |
| UI | typecheck, build, and real browser smoke when UI behavior changes |

## Daily Report Runtime Boundary

The project `daily_report` Skill is the Python facade exposed to Agent Runtime. It calls only the public `$daily-report-generator` CLI and normally omits `--workspace`, allowing that CLI to use its installed skill root and owned configs/resources. The Agent-side installation path, generator Python executable, and delivery output directory come from validated `agent.daily_report` configuration; an explicit request may provide compatibility overrides. The facade must not contain report-generation business rules, directly call per-task wrapper skills, or depend on internal generator metadata.
