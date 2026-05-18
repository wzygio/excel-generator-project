# 计划：实现 yield_report 数据获取层与全栈脚手架

## 目标
根据更新后的 `docs/design/yield_report_domain.md`，本次开发仅聚焦于“数据获取层”，暂不涉及核心分析和报告输出，但需要搭建从前端UI到后端的完整业务脚手架，以支持后续的 LLM 自然语言交互查询。

## 核心需求分析与技术选型

### 1. 自然语言交互查询 (Natural Language Querying)
*   **需求**: 用户在 UI 输入自然语言（如：“帮我下载今天的V3良率报表”），系统需要通过大模型提取“报表名称”和“筛选条件”等参数，然后执行查询。
*   **技术栈评估 (LangChain vs. 原生 Function Calling)**:
    *   **引入 LangChain 的利弊**: LangChain 提供了丰富的 Tool/Agent 抽象，便于构建复杂的智能体工作流。但它也会引入额外的抽象层，增加学习成本和部署体积。
    *   **原生 Function Calling (推荐)**: 考虑到当前需求主要是从文本中提取结构化参数（报表名、时间、产品型号等）来调用特定 API，这正是 OpenAI/Gemini 原生 Function Calling (或 Structured Output) 最擅长的场景。由于本项目已在 `shared_kernel` 中封装了统一的 `LLMManager`，直接利用 LLM 的结构化输出能力（如 Pydantic BaseModel 作为 schema）即可完美满足参数提取需求，**无需引入 LangChain 等重型框架**，保持架构简洁。
*   **实现方案**:
    1. 定义数据查询参数的 Pydantic 模型（如 `QueryParameters`）。
    2. 在 Application 层（编排器）接收用户的自然语言输入。
    3. 调用 `LLMManager`，并提供预定义的 Prompt 和 Function Schema，让 LLM 返回结构化的查询参数。
    4. 编排器根据参数，调用对应的底层数据获取模块（爬虫或本地文件读取）。

### 2. 爬虫与本地文件加载
*   **需求**: 所有相关账密存储于 `.env`。下载的文件最终要保存在 `resources/` 目录下。
*   **实现**:
    *   基于 `skills/finereport-crawler`，实现一个专用的下载器类。
    *   使用 `python-dotenv` 读取账密（已在项目初始化流程中实现）。
    *   将获取的文件统一保存到 `APP_CONFIG.paths.resources_dir`。

## 涉及文件清单
- `app/main.py` (修改): 搭建新的交互式 UI 界面，接收自然语言输入。
- `src/yield_report/yield_report/application/orchestrator.py` (新增): 实现 `DataAcquisitionOrchestrator`，负责自然语言解析与任务分发。
- `src/yield_report/yield_report/infrastructure/finereport_client.py` (新增): 实现 FineReport 的自动化下载。
- `src/yield_report/yield_report/infrastructure/local_file_loader.py` (新增): 处理本地网络盘文件的拷贝和就绪检查。
- `src/yield_report/yield_report/core/query_parser.py` (新增): 定义用于 LLM 提取参数的 Pydantic 模型和解析逻辑。

## 执行步骤 (仅数据获取层)

### Phase 1: 基础设施建设 (Infrastructure)
1. **实现 `finereport_client.py`**
   - 包含登录逻辑（从 `.env` 读账密）。
   - 包含下载“V3良率及不良率By月周天”和“By批次”报表的具体方法，支持传入日期和产品型号列表等参数。
   - 文件保存至 `resources/` 目录。
2. **实现 `local_file_loader.py`**
   - 实现将网络盘文件（如 CT 异常表、目标拆解表）同步或建立符号链接到本地 `resources/` 的逻辑，或者确认其可用性。
3. **辅助工具**
   - 实现读取 `spotfire.xlsx` 获取产品型号列表的工具函数。

### Phase 2: 自然语言解析核心 (Core - Query Parser)
1. **定义数据结构**
   - 在 `query_parser.py` 中定义 `ReportQueryRequest` (Pydantic BaseModel)，包含诸如 `report_type` (枚举)、`start_date`、`end_date`、`product_models` 等字段。
2. **LLM 参数提取**
   - 编写 Prompt 模板，指导 LLM 如何从自然语言中提取这些字段。
   - 利用 `LLMManager` 执行结构化信息提取。

### Phase 3: 应用层编排 (Application)
1. **实现 `DataAcquisitionOrchestrator`**
   - 暴露 `process_user_query(natural_language_input)` 方法。
   - 流程：接收自然语言 -> 调用 `query_parser` 获取结构化参数 -> 根据 `report_type` 调度 `finereport_client` 或 `local_file_loader` -> 返回执行结果（成功/失败及文件路径）。

### Phase 4: 前端 UI 接入 (UI)
1. **更新 `app/main.py`**
   - 增加一个对话框式的输入区（或类似 ChatGPT 的输入框），允许用户输入“帮我下载今天的报表”。
   - 将用户输入传递给后端的 `DataAcquisitionOrchestrator`。
   - 在界面上展示解析出的参数（以便用户确认）和下载进度。
   - 下载完成后，展示 `resources/` 目录下的可用文件列表。

## 预期产出
- 一个可以接收自然语言指令并自动完成相关数据报表下载/就绪确认的完整端到端模块。
- `resources/` 目录下将出现所需的所有源文件。

## 下一步
如同意此技术选型（不引入 LangChain，使用原生 Function Calling）和开发计划，请切换至 Code 模式开始执行。