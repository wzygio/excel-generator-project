# 1. 🌍 角色与项目介绍 (Meta-Context)

- **角色定义**: Senior Backend Architect（遵守 TDD 与 DDD 原则）
- **项目介绍**: 本项目是一个基于 LLM 的**良率日报自动生成系统**。系统通过读取工厂提供的多份 Excel 源表数据（良率汇总、批次报表、异常管理表、目标拆解表等），结合 DeepSeek/Gemini 大模型进行智能分析，自动生成标准化的 Excel 日报。项目分为**两代架构**：第一代（`excel_generator_project`）为传统扁平式架构，已实现完整的数据抽取 → 报告生成 → 样式处理流水线；第二代（`yield_report`）基于 DDD 重构，引入 Pydantic V2 配置体系和 LLM 分析能力，目前 Shared Kernel 已就绪，Core 层分析模块待实现。

# 2. 🧭 AGENTS.md — 总路由 (Progressive Disclosure)

## 2.1 文档映射表

| 文档（约定路径） | 用途 | 何时阅读 |
|------------------|------|----------|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | 系统架构蓝图（技术栈、DDD结构、数据流、缓存、容灾） | 首次进入项目 / 需要理解整体架构时 |
| [`docs/design/shared_kernel.md`](docs/design/shared_kernel.md) | Shared Kernel 设计（配置、LLM、日志） | 需要修改配置体系或 LLM 调用逻辑时 |
| [`docs/design/yield_report_domain.md`](docs/design/yield_report_domain.md) | 良率报告领域设计（Gap分析、异常分析、趋势分析） | 需要修改良率分析逻辑时 |
| [`docs/design/development_framework.md`](docs/design/development_framework.md) | 开发框架约定（EPCC Flow、TDD纪律、红线） | 开始编码前 / 需要了解开发规范时 |
| [`docs/design/business_boundary.md`](docs/design/business_boundary.md) | 业务边界（IN Scope / OUT of Scope） | 需要新增功能 / 判断需求范围时 |
| [`skills/README.md`](skills/README.md) | 技能库索引（专项解决方案） | 遇到已知技术问题时 |

## 2.2 全局红线纪律

| 编号 | 红线 | 说明 |
|------|------|------|
| R01 | 禁止修改 `global.yaml` 结构 | 配置结构由 Pydantic V2 [`AppConfig`](src/yield_report/shared_kernel/config_model.py:133) 校验 |
| R02 | Shared Kernel 使用单例模式 | [`ConfigLoader`](src/yield_report/shared_kernel/config.py:96) 和 [`LLMManager`](src/yield_report/shared_kernel/infrastructure/llm_handler.py:64) 均为单例 |
| R03 | Core 层严禁直接依赖 Infrastructure | Core 层通过接口依赖倒置，禁止直接 import  IO 库 |
| R04 | 测试必须 100% PASS 才能提交 | 运行 `uv run pytest tests/ -v --tb=short` |
| R05 | LLM 调用必须使用 LLMManager | 统一通过 [`llm_manager.chat()`](src/yield_report/shared_kernel/infrastructure/llm_handler.py:157) 调用 |
| R06 | 新增依赖必须经过评估 | 禁止随意添加第三方库 |
| R07 | 类型标注强制 | 所有函数/方法必须包含完整类型标注 |
| R08 | 禁止修改 `.roorules` 自身结构 | 文档映射表和红线纪律结构固定 |

## 2.3 快速命令

```bash
# 启动 Streamlit UI
uv run streamlit run app/main.py --server.port 8502

# 运行全部测试
uv run pytest tests/ -v --tb=short

# 类型检查
uv run pyright

# Lint 检查
uv run ruff check .

# 格式化
uv run ruff format .

# 安装依赖
uv sync
```

# 3. 🏗️ 系统架构 (Architecture Blueprint)

## 3.1 技术栈

| 组件 | 技术选型 |
|------|----------|
| Web 框架 | Streamlit ≥ 1.28.0 |
| 配置模型 | Pydantic V2 (Pydantic BaseModel, Field, field_validator) |
| 配置加载 | PyYAML + python-dotenv (链式加载: 默认值 → global.yaml → 产品级 YAML → .env) |
| LLM API - DeepSeek | OpenAI SDK (`openai≥1.0.0`) — 兼容 DeepSeek API |
| LLM API - Gemini | google-genai (`google-genai≥1.0.0`) |
| LLM 重试 | tenacity (指数退避, 最多3次重试) |
| 数据处理 | Pandas ≥ 2.0.0 |
| Excel 读写 | openpyxl ≥ 3.1.0 (读取/写入) |
| Excel 富文本 | xlsxwriter (富文本样式注入) |
| 数据缓存 | PyArrow/Parquet ≥ 10.0.0 (Excel 数据快照) |
| 包管理 | uv |
| 构建工具 | Hatchling |
| 测试框架 | Pytest ≥ 7.0.0, pytest-cov, pytest-asyncio |
| Lint | Ruff ≥ 0.1.0 |
| 类型检查 | Pyright |
| HTTP | Requests ≥ 2.33.1 |
| HTML 解析 | BeautifulSoup4 ≥ 4.14.3 |

## 3.2 项目结构 (DDD)

```
yield-report-generator/
├── .roorules                      # AGENTS.md 总路由
├── ARCHITECTURE.md                # 系统架构蓝图（本文档）
├── pyproject.toml                 # 项目元信息与依赖声明
├── config/                        # 配置层
│   ├── global.yaml                # 全局配置（Pydantic V2 校验）
│   ├── config.yaml                # 旧版详细业务配置（一代架构使用）
│   └── products/                  # 产品级配置（可覆盖全局）
├── app/                           # Streamlit 前端 (UI Layer)
│   ├── main.py                    # 主入口：页面布局、文件上传、分析触发
│   └── utils/
│       ├── app_setup.py           # 应用初始化（.env → 日志 → 配置）
│       ├── logger_setup.py        # 企业级日志架构（领域×级别二维隔离）
│       └── reloader.py            # 模块热重载
├── src/
│   └── yield_report/              # 第二代 DDD 架构 ★
│       ├── shared_kernel/         # Shared Kernel 层
│       │   ├── config_model.py    # Pydantic V2 配置模型
│       │   ├── config.py          # ConfigLoader 单例工厂
│       │   └── infrastructure/
│       │       └── llm_handler.py # LLMManager 单例（DeepSeek/Gemini）
│       └── yield_report/          # 良率报告领域 Domain
│           ├── application/       # 应用服务层（编排器 - 待实现）
│           ├── core/              # 核心领域层（分析算法 - 待实现）
│           └── infrastructure/    # 基础设施层（IO - 待实现）
│   └── excel_generator_project/   # 第一代扁平架构（已实现）
│       ├── config.py              # 旧版配置加载（YAML → dict）
│       ├── content_generator.py   # 阶段一：内容生成流程
│       ├── style_generator.py     # 阶段二：样式处理流程
│       ├── core/                  # 处理器层
│       │   ├── data_processor.py  # 数据处理（配置驱动）
│       │   ├── exception_processor.py  # 异常数据提取与格式化
│       │   └── font_processor.py  # 富文本样式注入（XML操作）
│       ├── infrastructure/
│       │   └── excel_handler.py   # Excel 读写封装
│       ├── services/
│       │   └── report_generator.py # 报告生成（写入Excel）
│       └── utils/
│           └── utils.py           # 通用工具类
├── tests/                         # 测试目录
│   ├── conftest.py                # Fixtures（临时配置、LLM Mock）
│   ├── unit/
│   │   └── test_config_loader.py  # ConfigLoader 单元测试
│   └── integration/               # 集成测试（待补充）
└── resources/                     # 资源文件（Excel源表、模板）
```

## 3.3 领域模块划分

| 领域 | 对应目录 | 职责 | 状态 |
|------|----------|------|------|
| `shared_kernel` | `src/yield_report/shared_kernel/` | 配置管理、LLM调用、日志体系 | ✅ 已完成 |
| `yield_report` | `src/yield_report/yield_report/` | 良率报告核心业务（Gap分析、异常分析、趋势分析） | 🔧 Core层待实现 |
| `excel_generator` | `src/excel_generator_project/` | 第一代：Excel数据抽取 → 报告生成 → 样式处理 | ✅ 已实现（V1） |

## 3.4 数据流架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        数据源层 (Source)                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │ V3良率汇总表  │ │ 批次汇总报表  │ │ CT异常管理表  │    ...     │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘             │
└─────────┼─────────────────┼─────────────────┼───────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      缓存层 (Cache)                              │
│  ┌──────────────────────────────────────────────┐               │
│  │  Parquet 文件快照 (data/temp/*.parquet)       │               │
│  │  缓存策略: 当 Excel mtime > Parquet mtime 时刷新 │             │
│  └──────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                   业务处理层 (Business)                           │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  V1: DataProcessor / ExceptionProcessor / FontProcessor│     │
│  │  V2: [待实现] Gap分析 / 异常分析 / 趋势分析 (LLM)     │       │
│  └──────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    输出层 (Output)                               │
│  ┌──────────────────────────────────────────────┐               │
│  │  标准 Excel 日报 (output/V3屏体良率日报*.xlsx) │              │
│  │  包含: 当日Gap解释 / 当日异常 / 已知异常       │              │
│  └──────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

### V1 数据流（已实现）

1. **ExceptionProcessor**: 从网络路径读取上一版日报的异常记录 → 文本清洗（段落移动/清理） → 从 CT 异常管理表提取当日异常 → 正则解析异常字段 → 格式化报告段落 → 按厂别合并到历史记录
2. **DataProcessor**: 从日报模板按步长读取单元格 → 正则提取数据（良率变化/BP目标/提拉目标/风险品等） → 计算衍生数据（Gap值） → 准备模板填充数据
3. **ReportGenerator**: 复制模板 → 按配置写入异常模块和摘要报告 → 保存
4. **FontProcessor**: 解压 ZIP → 读取 XML → 通过 xlsxwriter 创建富文本供体 → 注入 sharedStrings.xml → 更新 worksheet.xml → 重新打包

### V2 数据流（规划中）

1. **Streamlit UI**: 用户上传 5 份源表 → 保存到 session_state
2. **Data Extraction**: 读取 Excel 源表 → 提取结构化数据
3. **LLM Analysis**: 调用 LLMManager.chat() 执行 Gap 分析 / 异常分析 / 趋势分析
4. **Report Generation**: 将分析结果填充到 Excel 模板 → 输出最终日报

## 3.5 缓存体系

| 层级 | 策略 | 实现位置 |
|------|------|----------|
| **L1: Parquet 文件快照** | Excel 源表 → Parquet 格式缓存。当 Excel 修改时间晚于 Parquet 时自动刷新 | [`ExceptionProcessor._get_data_as_dataframe()`](src/excel_generator_project/core/exception_processor.py:291) |
| **L2: Streamlit 缓存装饰器** | [`@st.cache_resource`](app/main.py:63) 缓存 AppConfig 初始化结果，仅执行一次 | [`app/main.py:63`](app/main.py:63) |
| **L3: 本地文件副本** | 网络路径文件自动复制到本地 resources/ 目录，避免重复网络 IO | [`Utils.get_local_copy()`](src/excel_generator_project/utils/utils.py:274) |
| **增量刷新** | 目前无增量刷新机制，全量读取后缓存 | — |

## 3.6 容灾与降级策略

| 场景 | 策略 | 实现 |
|------|------|------|
| Excel 文件不存在 | 返回空字典，记录 WARNING 日志 | [`_load_yaml_file()`](src/yield_report/shared_kernel/config.py:49) |
| LLM API 调用失败 | 指数退避重试（最多3次），超时 60s | [`LLMManager._build_retry_decorator()`](src/yield_report/shared_kernel/infrastructure/llm_handler.py:143) |
| API Key 未配置 | 抛出 `LLMConfigurationError`，UI 显示"未配置"状态 | [`LLMManager._get_deepseek_client()`](src/yield_report/shared_kernel/infrastructure/llm_handler.py:92) |
| 模板缺失占位符 | 使用 `SafeDict` 自动填充 `／` 代替缺失值 | [`Utils.format_string()`](src/excel_generator_project/utils/utils.py:588) |
| 异常记录缺失 | 使用 `default_empty_exception_module` 默认模板 | [`ExceptionProcessor._execute_extract_previous_exceptions()`](src/excel_generator_project/core/exception_processor.py:66) |
| 网络文件锁定 (~$) | 自动解析锁定文件名为真实文件名 | [`Utils.resolve_lock_file()`](src/excel_generator_project/utils/utils.py:253) |
| 数据转换失败 | 返回 None 而非抛出异常 | [`Utils.safe_convert_percent_to_float()`](src/excel_generator_project/utils/utils.py:713) |

## 3.7 配置体系

### 加载链（由低到高优先级）

```
默认值 (Pydantic BaseModel Field default)
   ↓
global.yaml (全局基础配置)
   ↓
config/products/*.yaml (产品级覆盖配置)
   ↓
.env 环境变量 (最高优先级)
```

### 配置结构

```
AppConfig (根模型)
├── app_name: str                  # 应用名称
├── version: str                   # 版本号
├── debug: bool                    # 调试模式
├── paths: PathsConfig             # 路径配置
│   ├── base_dir, resources_dir, temp_dir
│   ├── log_dir, output_dir
│   ├── template_file, temp_file, output_file
├── llm: LlmConfig                 # 大模型配置
│   ├── provider: "deepseek" | "gemini"
│   ├── deepseek: LlmProviderConfig
│   └── gemini: LlmProviderConfig
├── logging: LoggingConfig         # 日志配置
│   ├── level, domain_rotation, max_days
├── report: ReportConfig           # 报告生成配置
│   ├── sections, gap_analysis, batch_analysis, trend_analysis
└── products: list[ProductConfig]  # 产品级配置列表
```

**V1 旧配置**（`config/config.yaml`）：为一代架构服务，包含完整的任务定义（数据提取规则、异常处理流程、报告生成配置、样式定义等），采用纯字典方式加载，无类型校验。

**V2 新配置**（`config/global.yaml` + Pydantic V2）：为二代架构服务，强类型校验，支持链式访问。

## 3.8 词汇表 (Glossary)

| 术语 | 说明 |
|------|------|
| CT (Cell Test) | 模组制程中的"Cell Test"站点，指对已完成Cell制程的产品进行电学性能测试 |
| Gap 分析 | 当日实际良率与目标良率之间的差距分析 |
| BP (Base Plan) | 基础良率目标 |
| 提拉目标 | 通过工艺改善后设定的更高良率目标（Pull-up Target） |
| 排产良率 | 生产排程中使用的预估良率 |
| 良率预估 | 基于当前数据和趋势模型对月度最终良率的预测 |
| ARRAY | 阵列厂（Array Fab） |
| OLED | 有机发光二极管厂（OLED Fab） |
| TP (Touch Panel) | 触控面板厂 |
| 当日异常 | 当天新发现的CT异常事件 |
| 已知异常 | 历史已记录且仍在影响良率的CT异常 |
| 风险品 | 当前良率不达标、需要特别管控的产品型号 |
| 释放计划 | 风险品从"风险管控"状态转出的时间/条件计划 |

# 4. 📐 领域设计 (Domain Design)

## 4.1 Shared Kernel（共享内核）✅ 已完成

- **对应目录**: [`src/yield_report/shared_kernel/`](src/yield_report/shared_kernel/)

### 配置管理
- **Pydantic V2 配置模型**: [`config_model.py`](src/yield_report/shared_kernel/config_model.py) 定义了完整的 `AppConfig` 根模型，涵盖路径、LLM、日志、报告、产品五个维度
- **ConfigLoader 单例**: [`config.py`](src/yield_report/shared_kernel/config.py) 实现了 `ConfigLoader` 单例模式，支持链式配置加载（默认值 → global.yaml → 产品级 YAML → .env），提供 `get()` 懒加载和 `reload()` 强制刷新
- **深度合并算法**: `_deep_merge()` 支持递归字典合并，产品级配置可覆盖全局配置

### LLM 调用
- **LLMManager 单例**: [`llm_handler.py`](src/yield_report/shared_kernel/infrastructure/llm_handler.py) 封装了 DeepSeek（OpenAI SDK）和 Gemini（google-genai SDK）的统一调用接口
- **关键方法**: `chat()` — 非流式调用；`chat_stream()` — 流式调用（仅 DeepSeek）
- **重试机制**: 基于 tenacity 的指数退避重试（最多3次），仅对 `LLMProviderError`、`ConnectionError`、`TimeoutError` 重试
- **线程安全**: 每次调用独立创建客户端，天然支持多线程

### 日志架构
- **领域日志系统**: [`logger_setup.py`](app/utils/logger_setup.py) 实现了"用途 × 领域"二维隔离策略
- **三级文件**: 每个领域生成三个文件：`{domain}.log`（全量流水）、`{domain}.error.log`（高优报警）、`{domain}.trace.log`（调试追踪）
- **按天轮转**: `TimedRotatingFileHandler` 按午夜零点轮转，保留 30 天

## 4.2 yield_report 领域（良率报告）🔧 待实现

- **对应目录**: [`src/yield_report/yield_report/`](src/yield_report/yield_report/)

### 应用层 (Application Service Layer)
- **对应目录**: [`application/`](src/yield_report/yield_report/application/)
- **职责**: 协调上传、提取、分析、生成的完整编排流程
- **待实现**: `ReportOrchestrator` — 全流程编排器

### 核心层 (Core Domain Layer) 
- **对应目录**: [`core/`](src/yield_report/yield_report/core/)
- **职责**: 大模型重度参与的分析逻辑
- **待实现模块**:
  - `gap_analysis.py`: 日良率 Gap 分析 + 批次恶化判断
  - `exception_analysis.py`: CT 异常解析（新增异常 + 已知异常）
  - `trend_analysis.py`: 连续三日/三周趋势分析
- **约束**: Core 层严禁直接依赖 Infrastructure 层（禁止直接 import openpyxl 等 IO 库）

### 基础设施层 (Infrastructure Layer)
- **对应目录**: [`infrastructure/`](src/yield_report/yield_report/infrastructure/)
- **待实现**:
  - `ExcelReader`: 源表数据读取
  - `ExcelWriter`: 报告写入
  - `PromptLoader`: Prompt 模板管理
  - `SnapshotCache`: Parquet 快照缓存

## 4.3 excel_generator 领域（一代架构）✅ 已实现

- **对应目录**: [`src/excel_generator_project/`](src/excel_generator_project/)

### 应用服务
- **内容生成流程** (`content_generator.py`): 编排 ExceptionProcessor → DataProcessor → ReportGenerator 的完整流水线
- **样式处理流程** (`style_generator.py`): 对已生成的报告进行 FontProcessor 富文本样式注入

### 核心处理器
- **DataProcessor**: 配置驱动的 Excel 数据提取引擎。支持 `parse_text_from_cells`、`extract_tila_target`、`extract_monthly_yield_estimate`、`extract_risk_items`、`prepare_summary_data` 等任务类型
- **ExceptionProcessor**: CT 异常管理表专用处理器。支持从历史日报提取基线 → 匹配当日异常 → 按厂别合并
- **FontProcessor**: 直接操作 xlsx ZIP 内部 XML，通过 xlsxwriter 创建富文本供体，注入 sharedStrings.xml

### 基础设施
- **ExcelHandler**: openpyxl 封装，支持模板加载、单元格读写、工作表切换、文件保存

# 5. 🔧 技能库 (Skills)

## 5.1 技能索引

[未实现 — `skills/` 目录尚未创建]

## 5.2 解决方案摘要

[待补充]

# 6. 💻 系统环境与命令 (System Commands)

### 运行命令
| 用途 | 命令 | 说明 |
|------|------|------|
| 启动 V2 Streamlit UI | `uv run streamlit run app/main.py --server.port 8502` | 新架构前端 |
| 启动 V1 Streamlit UI | `python -m streamlit run src/excel_generator_project/app/app.py --server.port 8502` | 旧架构前端 |

### 测试命令
| 用途 | 命令 |
|------|------|
| 全部测试 | `uv run pytest tests/ -v --tb=short` |
| 单元测试 | `uv run pytest tests/unit/ -v --tb=short` |
| 集成测试 | `uv run pytest tests/integration/ -v --tb=short` |
| 带覆盖率 | `uv run pytest tests/ -v --tb=short --cov=src` |

### 代码质量
| 用途 | 命令 |
|------|------|
| 类型检查 | `uv run pyright` |
| Lint 检查 | `uv run ruff check .` |
| 格式化 | `uv run ruff format .` |

### 依赖安装
| 用途 | 命令 |
|------|------|
| 安装全部依赖 | `uv sync` |
| 添加生产依赖 | `uv add <package-name>` |
| 添加开发依赖 | `uv add --dev <package-name>` |
