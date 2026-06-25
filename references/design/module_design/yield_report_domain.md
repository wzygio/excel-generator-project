# Yield Report 领域设计

## 1. 领域目标

`yield_report` 是良率日报 V2 主线领域包，负责把“报表下载、数据分析、日报生成”三段流程逐步收拢到清晰的应用架构中。

当前已经落地：

1. **报表下载 / 数据获取**：自然语言解析、FineReport RPA 下载、本地源表加载。
2. **数据分析**：Excel schema 提取、分析策略选择、代码生成执行或 LLM 直接分析。
3. **日报生成入口**：UI 已保留 tab，完整编排待接入。

当前架构正在从 DDD 倾向的横向分层迁移到 Agent-friendly 的纵向 Skill 结构。迁移目标不是取消现有能力，而是把已稳定的下载、分析和日报生成能力包装为 Codex/Runtime 可调用的工具。

| 业务能力 | 目标 Skill | 说明 |
|----------|------------|------|
| 报表下载 / 数据获取 | `report_download` | 根据 Spec 中的报表类型、日期、产品型号和筛选条件下载或定位源表。 |
| 数据分析 | `data_analysis` | 读取优先解密文件，执行趋势、异常、Gap、排序等分析，并返回结构化结论。 |
| 日报生成 | `daily_report` | 根据分析结果和模板生成标准 Excel 日报。 |

统一任务契约和 Skill 工具契约见 Agent system design references。

## 2. 业务流程

```text
报表下载
  -> 数据分析
  -> 日报生成
```

### 2.1 报表下载

目标：用户用自然语言描述要下载的报表和筛选条件，系统解析后自动获取源表。

示例：

```text
我想要查询M678这款产品近两个月的良率，结束日期为2026-05-01
```

解析结果应包含：

- `report_type`: `daily_yield`
- `start_date`: 可选
- `end_date`: `2026-05-01`
- `product_models`: `["M678"]`
- `user_intent`: 用户意图摘要

下载成功后，文件保存到 `resources/`，并在文件名后追加筛选条件，便于智能体快速理解文件内容，例如：

```text
V3良率及不良率By月周天汇总报表_结束日期2026-05-01_产品型号M678.xlsx
```

### 2.2 数据分析

目标：用户对已下载源表提出自然语言分析需求，系统选择合适执行方式：

| 策略 | 适用需求 |
|------|----------|
| `code` | 明确筛选、排序、聚合、趋势计算 |
| `llm_direct` | 原因分析、异常判断、建议、模糊探索 |

执行流程：

```text
定位 Excel 文件
  -> extract_schema()
  -> AnalysisStrategySelector.decide()
  -> CodeGenerator/CodeExecutor 或 LLM direct
  -> AnalysisResult
```

### 2.3 日报生成

目标：把 Gap 分析、异常分析、趋势分析等结果写入标准 Excel 日报。

当前状态：

- UI 已有“日报生成”tab。
- `config/global.yaml` 已定义输出目录和输出文件名。
- 完整 V2 编排器尚未接入，仍需后续实现。
- V1 实现位于 `src/excel_generator_project/`，可作为日报写入和样式处理参考。

## 3. 源表清单

### 3.1 V3良率及不良率By月周天汇总报表

| 属性 | 说明 |
|------|------|
| 报表类型 | `daily_yield` |
| 来源 | FineReport |
| 用途 | 日/月/周维度良率和不良率数据，支撑 Gap 计算和趋势分析 |
| 报表目录 | `目录/良率监控/综合良率` |
| 关键筛选 | `结束日期：`、`产品型号：` |
| 默认日期 | 10:00 前为昨日，10:00 后为今天 |
| 默认产品型号 | 未指定时走全选；也可从 `spotfire.xlsx` 解析后传入 |

### 3.2 V3良率及不良率By批次汇总报表

| 属性 | 说明 |
|------|------|
| 报表类型 | `batch_yield` |
| 来源 | FineReport |
| 用途 | 判断最新批次是否恶化、支撑批次维度分析 |
| 报表目录 | `目录/良率监控/综合良率` |
| 关键筛选 | `开始日期：`、`结束日期：`、`产品型号：` |
| 默认开始日期 | 今天往前 90 天 |
| 默认结束日期 | 10:00 前为昨日，10:00 后为今天 |

### 3.3 CT良率异常波动管理表

| 属性 | 说明 |
|------|------|
| 报表类型 | `ct_exception` |
| 来源 | 网络共享路径 / 本地缓存 |
| 用途 | 当日异常、已知异常、Code 维度异常追踪 |
| 当前加载器 | `LocalFileLoader.ensure_ct_exception_file()` |

### 3.4 良率目标拆解表

| 属性 | 说明 |
|------|------|
| 报表类型 | `target_decomposition` |
| 来源 | `resources/` |
| 用途 | 产品/Group 良率目标获取 |
| 文件名 | `2026年良率目标拆解-1017版V05 - 无公式版.xlsx` |

### 3.5 日良率Gap分析模板

| 属性 | 说明 |
|------|------|
| 报表类型 | `gap_template` |
| 来源 | `resources/` |
| 用途 | Gap 分析规则和模板 |
| 文件名 | `日良率Gap分析模板.xlsx` |

### 3.6 产品型号来源

产品型号可来自：

- 用户自然语言显式指定，如 `M678`。
- `resources/project_files/spotfire.xlsx` 中的产品型号列。
- 未指定时，FineReport 下载层可以执行全选。

## 4. 当前兼容分层与目标 Skill 迁移

现有 `application/core/infrastructure` 仍是当前可运行兼容层。`src/yield_report/agent/` 和 `src/yield_report/skills/` 已新增，并用 Skill Tool 包装现有 orchestrator；后续再逐步迁移实现细节。

目标调用方向：

```text
TaskSpec
  -> Agent Runtime
  -> skills/report_download/tool.py
  -> skills/data_analysis/tool.py
  -> skills/daily_report/tool.py
```

当前分层职责如下。

### 4.1 Application 层（兼容）

路径：`src/yield_report/application/`

| 类/模块 | 职责 |
|---------|------|
| `DataAcquisitionOrchestrator` | 报表下载/数据获取总控；解析自然语言并分发到 FineReport 或本地加载器 |
| `AnalysisOrchestrator` | 数据分析总控；定位文件、提取 schema、选择策略、执行分析 |

应用层负责“编排”，不放具体浏览器操作、Excel 解析细节或 LLM prompt 细节。

### 4.2 Core 层（兼容）

路径：`src/yield_report/core/`

| 类/模块 | 职责 |
|---------|------|
| `ReportQueryRequest` | 报表下载结构化请求模型 |
| `ReportType` | 五类源表枚举 |
| `QueryParser` | 使用 LLM 将自然语言转换为 `ReportQueryRequest` |
| `AnalysisStrategySelector` | 判断数据分析需求走 `code` 还是 `llm_direct` |

Core 层只放领域判断和模型，不直接访问文件系统、浏览器或 FineReport。

### 4.3 Infrastructure 层（兼容）

路径：`src/yield_report/infrastructure/`

| 类/模块 | 职责 |
|---------|------|
| `FinereportClient` | FineReport 下载门面；保持旧接口兼容；负责文件名追加筛选条件 |
| `YieldDownloadService` | 良率报表 RPA 编排：报表导航、参数设置、查询、导出 |
| `YieldPortalAdapter` | FineReport 页面原子操作，继承 `fr_web_automation` 的 `OLEDPortalAdapter` |
| `LocalFileLoader` | 网络/本地源表加载 |
| `product_models.py` | 产品型号读取 |
| `code_generator.py` | Excel schema 提取和 pandas 代码生成 |
| `code_executor.py` | 生成代码执行与结果收集 |

### 4.4 Skill 目标层

| 目标路径 | 迁移来源 | 迁移原则 |
|----------|----------|----------|
| `src/yield_report/skills/report_download/` | `DataAcquisitionOrchestrator`、`FinereportClient`、`LocalFileLoader` | 已包装现有下载行为，提供结构化 request/result。 |
| `src/yield_report/skills/data_analysis/` | `AnalysisOrchestrator`、分析文件解析器、分析器、memory | 已包装 Task1/Task2 数据分析能力，向下游返回可复用结构化数据。 |
| `src/yield_report/skills/daily_report/` | V1 日报写入经验和新 V2 需求 | 已预留稳定 Skill 接口，具体生成逻辑后续接入。 |

## 5. FineReport RPA 设计约束

FineReport 自动化优先复用独立包：

```text
D:\wzy\Python\packages\web_automation
import fr_web_automation
```

项目层只维护良率报表相关信息：

- 报表名称
- 报表目录
- 参数标签
- 日期默认值
- 产品型号业务规则
- 下载文件命名规则

当前关键常量位于 `yield_download_service.py`：

```text
DAILY_YIELD_REPORT_NAME = "V3良率及不良率By月周天汇总报表"
BATCH_YIELD_REPORT_NAME = "V3良率及不良率By批次汇总报表"
YIELD_REPORT_DIRECTORY = "目录/良率监控/综合良率"
LABEL_END_DATE = "结束日期："
LABEL_START_DATE = "开始日期："
LABEL_PRODUCT_MODEL = "产品型号："
```

失败定位：

- RPA 下载失败时会保存截图和 iframe 文本到 `downloads/rpa_debug/`。
- 这些调试文件不属于业务源表，不应作为日报输入。
- 当 `report_type` 无法判断且本地也无法定位源表时，数据获取层只提取一个最关键关键词，并调用 FineReport 门户搜索；搜索框不支持模糊查询，因此不得一次拼接多个关键词。搜索结果向上返回为可恢复失败，等待用户或上层指定具体报表名。

## 6. 文件命名规则

FineReport 原始导出文件名较难表达筛选条件，因此 `FinereportClient` 会在下载后重命名：

| 场景 | 示例 |
|------|------|
| 日报 + 单型号 | `V3良率及不良率By月周天汇总报表_结束日期2026-05-01_产品型号M678.xlsx` |
| 批次 + 多型号 | `V3良率及不良率By批次汇总报表_开始日期2026-03-01_结束日期2026-05-01_产品型号M626+M673.xlsx` |
| 未指定型号 | `..._产品型号全部.xlsx` |

文件名清理规则：

- Windows 非法字符会被替换为 `_`。
- 多型号最多展示前 5 项，超过后追加 `等N项`。
- 后缀长度有限制，避免路径过长。

## 7. 领域分析规划

后续日报生成需要沉淀以下领域能力：

### 7.1 Gap 分析

- 从月周天报表读取日良率/不良率。
- 从目标拆解表读取目标不良率。
- 计算 Group 维度 Top N Gap。
- 判断 Gap 来源是否与批次恶化、集中出货或已知异常相关。

### 7.2 批次分析

- 从批次汇总报表筛选产品和日期范围。
- 根据 `batch_analysis.min_yield_rate` 过滤有效批次。
- 对比最近若干批次，识别恶化趋势。

### 7.3 异常分析

- 从 CT 异常管理表识别当日新增异常。
- 对已知异常按 Group / Code 聚合。
- 输出日报可用的精简文本。

### 7.4 趋势分析

- 判断连续三日或三周良率上升/下降。
- 支撑日报中的趋势说明和风险提示。

## 8. 当前测试覆盖

| 测试 | 覆盖内容 |
|------|----------|
| `test_query_parser.py` | 自然语言解析模型、JSON 清理、日期校验 |
| `test_data_acquisition_orchestrator.py` | 用户语句注入项目入口后路由到对应下载接口 |
| `test_yield_download_service.py` | RPA 服务是否传递产品型号和报表目录 |
| `test_finereport_client.py` | 下载后文件名是否追加筛选条件 |
| `test_analysis_selector.py` | 分析策略选择 |
| `test_code_generator.py` | schema 提取与代码生成辅助 |
| `test_code_executor.py` | 生成代码执行 |

推荐快速验证：

```bash
uv run pytest tests/unit/test_query_parser.py tests/unit/test_data_acquisition_orchestrator.py tests/unit/test_yield_download_service.py tests/unit/test_finereport_client.py -v --tb=short
```

## 9. 待办边界

- 日报生成 V2 编排器尚未接入。
- 数据分析默认文件定位仍需要继续增强，应优先使用 `config/global.yaml` 中的 source file pattern。
- FineReport RPA 依赖内网和真实账号，单元测试应通过 fake service/mock 避免真实浏览器。
- 自动同步脚本已修复为 pull 前 WIP commit，但项目提交前仍应主动 commit 关键成果。
