# 良率日报自动生成系统架构

## 1. 项目定位

本项目是一个面向良率日报工作的自动化系统，当前主线分为三个用户可见模块：

1. **报表下载**：解析自然语言需求，调用 FineReport RPA 下载源表到 `resources/`。
2. **数据分析**：基于已下载 Excel 源表，提取 schema，选择代码执行或 LLM 直接分析策略。
3. **日报生成**：面向最终 Excel 日报输出，当前 UI 已保留入口，完整 V2 编排仍待接入。

2026-06-01 的 Agent 架构重构决策：项目不再以 DDD 横向分层作为第一入口，而是以 **Spec 驱动 + Skill 工具 + Codex Agent 核心** 作为目标架构。当前已新增 `src/yield_report/agent/` 和 `src/yield_report/skills/`，旧 `application/core/infrastructure` 作为兼容实现继续保留，并由 Skill 包装调用。

仓库内同时保留两代实现：

| 代际 | 路径 | 状态 |
|------|------|------|
| V2 主线 | `ui/copilotkit-agent/`, `src/shared_kernel/`, `src/yield_report/` | 当前开发主线 |
| V1 兼容 | `src/excel_generator_project/` | 旧版 Excel 日报生成流水线，作为兼容和参考存在 |
| Agent 主线 | `src/yield_report/agent/`, `src/yield_report/skills/`, `docs/agent/`, `specs/templates/` | Codex/Agent 友好的目标结构 |

## 2. Agent 目标架构

目标运行链路：

```text
用户需求
  -> TaskSpec / spec.yaml
  -> Agent Runtime
  -> Skill Tool
  -> SkillResult
  -> Trace / Memory / Output
```

核心原则：

| 原则 | 说明 |
|------|------|
| Codex 作为 Agent 核心 | Codex 负责理解用户需求、维护 Spec、调用本地工具、在失败时修正流程。 |
| Python Skill 承载稳定能力 | 高频、重复、可测试流程必须沉淀为 Python 工具，而不是让 LLM 每次自由发挥。 |
| Spec 作为任务契约 | 用户修改流程时优先修改 `spec.yaml`，而不是改 UI 或 orchestrator 代码。 |
| Trace 与 Memory 可追踪 | 每次运行应记录步骤、产物、错误和已确认的复用经验。 |
| 渐进迁移 | 先新增 `agent/` 与 `skills/` 外壳，不立即删除旧分层模块。 |

目标文档：

| 文档 | 说明 |
|------|------|
| `docs/agent/architecture.md` | Agent/Skill/Spec 目标架构与迁移策略 |
| `docs/agent/skill_contract.md` | Skill 输入输出、错误、产物、memory 契约 |
| `docs/agent/spec_contract.md` | Spec 文件字段、workflow、outputs、trace、memory 契约 |
| `specs/templates/daily_report_spec.yaml` | 日报任务 Spec 模板 |

目标目录：

```text
src/yield_report/
├── agent/                # Spec、LangGraph Spec Graph、Runtime、Memory、Trace
│   └── spec_graph/       # State、Nodes、Edges、Graph、Checkpointer、Agent facade
├── skills/               # report_download、data_analysis、daily_report
├── adapters/             # Task2 后续迁移：FineReport、Excel、LLM 适配器
├── shared/               # Task2 后续迁移：yield_report 内部共享工具
├── application/          # 当前兼容层
├── core/                 # 当前兼容层
└── infrastructure/       # 当前兼容层
```

## 3. 技术栈

| 组件 | 技术选型 |
|------|----------|
| UI | CopilotKit / Next.js |
| 配置模型 | Pydantic V2 |
| 配置加载 | PyYAML + python-dotenv |
| LLM | DeepSeek(OpenAI SDK 兼容) / Gemini(google-genai) |
| LLM 管理 | `shared_kernel.infrastructure.llm_handler.LLMManager` |
| FineReport 自动化 | `fr_web_automation` + Playwright RPA |
| 数据处理 | pandas |
| Excel 读写 | openpyxl / xlsxwriter / pywin32(COM fallback) |
| 包管理 | uv |
| 测试 | pytest |
| 质量工具 | ruff / pyright |
| 任务契约 | YAML Spec |
| Agent 核心 | Codex（外部编排），Python 项目提供可调用工具 |

## 4. 当前目录结构

```text
yield-report-generator/
├── ui/
│   └── copilotkit-agent/               # CopilotKit Agent Workbench
│       ├── app/page.tsx
│       └── app/api/agent-runs/route.ts
├── config/
│   └── global.yaml                     # Pydantic V2 配置输入
├── docs/
│   └── agent/                          # Agent/Skill/Spec 目标架构与契约
├── specs/
│   └── templates/
│       └── daily_report_spec.yaml      # 日报任务 Spec 模板
├── src/
│   ├── shared_kernel/
│   │   ├── config.py                   # ConfigLoader
│   │   ├── config_model.py             # AppConfig 等配置模型
│   │   └── infrastructure/
│   │       └── llm_handler.py          # LLMManager 单例
│   ├── yield_report/
│   │   ├── agent/                      # Codex/Runtime 调用契约与轻量运行时
│   │   ├── skills/                     # 三个业务 Skill 入口
│   │   ├── application/
│   │   │   ├── orchestrator.py         # 报表下载/数据获取编排
│   │   │   └── analysis_orchestrator.py # 数据分析编排
│   │   ├── core/
│   │   │   ├── query_parser.py         # 自然语言 -> ReportQueryRequest
│   │   │   └── analysis_selector.py    # code / llm_direct 策略选择
│   │   └── infrastructure/
│   │       ├── finereport_client.py    # FineReport 下载客户端门面
│   │       ├── yield_download_service.py # 良率报表 RPA 编排
│   │       ├── yield_portal_adapter.py # 良率报表页面原子操作
│   │       ├── local_file_loader.py    # 本地/网络源表加载
│   │       ├── product_models.py       # spotfire 产品型号读取
│   │       ├── code_generator.py       # Excel schema + pandas 代码生成
│   │       └── code_executor.py        # 代码执行沙箱
│   └── excel_generator_project/        # V1 兼容实现
├── tests/
│   └── unit/                           # 当前核心单元测试
├── resources/                          # 源表、模板、RPA 下载结果
└── output/                             # 日报输出
```

## 5. UI 架构

`ui/copilotkit-agent` 是当前唯一前端入口。它使用 CopilotKit / Next.js 提供 Agent Workbench：

```text
用户输入
  -> SpecBuilder 创建 specs/runs/<run_id>/spec.yaml
  -> 运行步骤
  -> 结果、Memory 候选与产物下载
```

前端通过 `/api/agent-runs` 调用 `scripts/agent_workbench_bridge.py`，后端统一走 RunStore、RuntimeRouter、Python Skills 与 Pi/OMP Runtime。

## 6. 当前分层职责

### 6.1 Shared Kernel

`src/shared_kernel/` 提供跨领域基础能力：

- `config_model.py`：`AppConfig`、`PathsConfig`、`LlmConfig` 等 Pydantic V2 模型。
- `config.py`：配置加载，合并默认值、`config/global.yaml`、产品级 YAML 和 `.env`。
- `infrastructure/llm_handler.py`：`LLMManager` 单例，统一 DeepSeek / Gemini 调用与重试。

约束：业务模块不得直接创建 OpenAI/Gemini 客户端，必须通过 `llm_manager.chat()`。

### 6.2 Yield Report / Core

`src/yield_report/core/` 放纯领域判断：

- `query_parser.py`：将用户自然语言解析为 `ReportQueryRequest`，包含报表类型、日期、产品型号、用户意图和不确定信息。
- `analysis_selector.py`：判断分析需求应走 `code` 路径还是 `llm_direct` 路径。

约束：Core 层不直接读写文件、不操作浏览器、不依赖 FineReport RPA。

### 6.3 Yield Report / Application

`src/yield_report/application/` 是编排层：

- `DataAcquisitionOrchestrator`
  - 调用 `QueryParser`
  - 根据 `ReportType` 分发到 FineReport 下载或本地文件加载
  - 返回 `UserQueryResult` 与 `AcquisitionResult`
  - 对 FineReport 连接、下载、产品型号提取和非预期异常做结构化失败返回
- `AnalysisOrchestrator`
  - 定位 Excel 文件
  - 提取 schema
  - 调用 `AnalysisStrategySelector`
  - 选择代码生成执行或 LLM 直接分析

### 6.4 Yield Report / Infrastructure

`src/yield_report/infrastructure/` 放 IO、浏览器、Excel 和执行环境：

- `FinereportClient`：对外保持 `download_daily_yield_report()` / `download_batch_yield_report()` 接口，内部使用 RPA；下载成功后会将筛选条件追加到文件名，例如：
  `V3良率及不良率By月周天汇总报表_结束日期2026-05-01_产品型号M678.xlsx`
- `YieldDownloadService`：项目层 FineReport RPA 编排，定义报表名、目录、标签、日期和产品型号筛选。
- `YieldPortalAdapter`：继承 `fr_web_automation` 的 `OLEDPortalAdapter`，封装良率报表页面原子操作。
- `LocalFileLoader`：保证 CT 异常表、目标拆解表、Gap 模板等本地/网络文件可用。
- `product_models.py`：从 `resources/project_files/spotfire.xlsx` 读取产品型号。
- `code_generator.py` / `code_executor.py`：为数据分析提供 schema 提取、代码生成和执行能力。

## 7. 报表下载数据流

```text
用户输入
  -> ui/copilotkit-agent
  -> DataAcquisitionOrchestrator.process_user_query()
  -> QueryParser.parse()
  -> 根据 ReportType 分发
  -> FinereportClient
  -> YieldDownloadService
  -> YieldPortalAdapter / fr_web_automation
  -> FineReport 查询、导出
  -> resources/*.xlsx
  -> 文件名追加筛选条件
  -> UserQueryResult 返回 UI
```

FineReport 相关配置来自 `.env`：

```text
FINEREPORT_HOST
FINEREPORT_USERNAME
FINEREPORT_PASSWORD
FINEREPORT_ENTRY_UUID
```

内网访问要求：

- `FinereportClient` 会将 FineReport host 加入 `NO_PROXY`，避免代理影响内网连接。
- DeepSeek/OpenAI SDK 在 SOCKS 代理环境下需要 `socksio` 依赖。

## 8. 数据分析数据流

```text
用户输入
  -> ui/copilotkit-agent
  -> AnalysisOrchestrator.analyze()
  -> 定位 resources/ 下 Excel 文件
  -> extract_schema()
  -> AnalysisStrategySelector.decide()
  -> code 路径: CodeGenerator -> CodeExecutor
  -> llm_direct 路径: LLMManager.chat()
  -> AnalysisResult 返回 UI
```

策略含义：

| 策略 | 使用场景 | 说明 |
|------|----------|------|
| `code` | 筛选、聚合、排序、趋势等明确数据操作 | 先生成 pandas 代码，再执行 |
| `llm_direct` | 原因分析、异常判断、建议等需要推理的请求 | 直接把 schema/数据摘要交给 LLM 分析 |

## 9. 源表与文件约定

| 文件 | 来源 | 当前用途 |
|------|------|----------|
| V3良率及不良率By月周天汇总报表 | FineReport | Gap / 日周月良率分析 |
| V3良率及不良率By批次汇总报表 | FineReport | 批次恶化判断 |
| CT良率异常波动管理表 | 网络共享路径 / 本地缓存 | 异常分析 |
| 2026年良率目标拆解-1017版V05 - 无公式版.xlsx | `resources/` | 目标良率 |
| 日良率Gap分析模板.xlsx | `resources/` | Gap 分析规则和模板 |
| spotfire.xlsx | `resources/project_files/` | 产品型号来源 |

## 10. 测试与验证

当前关键测试：

```bash
uv run pytest tests/unit/test_query_parser.py -v --tb=short
uv run pytest tests/unit/test_data_acquisition_orchestrator.py -v --tb=short
uv run pytest tests/unit/test_yield_download_service.py -v --tb=short
uv run pytest tests/unit/test_finereport_client.py -v --tb=short
uv run pytest tests/unit/test_analysis_selector.py tests/unit/test_code_generator.py tests/unit/test_code_executor.py -v --tb=short
```

Agent 架构迁移后的新增测试目录：

```text
tests/unit/agent/
tests/unit/skills/
tests/integration/
```

常用质量检查：

```bash
uv run ruff check .
uv run pyright
```

UI 验证：

```bash
cd ui/copilotkit-agent
npm run typecheck
npm run build
npm run dev
```

## 11. 已知边界

- CopilotKit Workbench 已接入 Spec run，日报生成 Skill 仍依赖当前 V2 源表与模板能力。
- RuntimeRouter 已接入 Python Skill Runtime 与 Pi/OMP Runtime adapter；生产使用 Pi/OMP 时仍需模型配置和权限边界。
- FineReport RPA 依赖内网、Chrome、`.env` 账号和 `fr_web_automation` 包。
- `resources/` 中下载文件可能包含筛选条件后缀；后续分析模块应按 `config/global.yaml` 的 pattern 或业务描述匹配，而不是依赖完全固定文件名。
- 自动同步脚本必须在 pull 前保护本地改动，并且日志不得写入仓库工作区。
