# 1. 🌍 角色与项目介绍 (Meta-Context)
- **角色定义**: Senior Backend Architect (遵守 TDD 与 DDD 原则)
- **项目介绍**: 本项目是一个配置驱动的 Excel 良率日报自动化生成工具。它通过读取配置文件（如 YAML）中定义的步骤，自动提取跨多份报表的离散数据（如提拉良率、当月预估良率、风险品等），经过核心处理模块对提取到的数据进行计算（如良率 Gap）与格式化，最终渲染并输出带有样式的标准化 Excel 日报。

# 2. 📂 渐进式披露 (Progressive Disclosure)
- **词汇表 (Glossary)**: 
  - **job_type**: YAML 配置文件中定义任务类型的核心字段，决定 `DataProcessor` 等调度类调用哪个具体的提取或处理逻辑（如 `parse_text_from_cells`、`extract_tila_target`）。
  - **tila_target (提拉目标)**: 从“屏体良率预测”相关报表中按产品型号、月份提取的良率目标值，用于后续计算良率的 Gap。
  - **product_models (产品型号)**: 贯穿整个配置与代码的业务主键，用于从各个异构表中精确匹配或提取某一款产品（如 C51、C516）的数据行。
- **🚫 负面清单 (Negative Constraints)**: 
  - 禁止静态重构已有核心逻辑。
  - 禁止在未同步修改 `config.yaml` 任务序列的情况下直接改动 `DataProcessor` 的核心遍历逻辑（数据驱动与配置强绑定，硬编码提取逻辑会破坏其通用性）。
  - 禁止绕过已有的 `Utils` 工具类（特别是安全转换和路径解析）直接使用原生 API 操作 Excel。
- **细项规则映射**: (留空，待后续需要时扩展)

# 3. 🏗️ 系统架构约定 (Architecture Blueprint)
- **项目结构 (DDD)**: 
  ```text
  d:/wzy/Python/excel-generator-project/
  ├── config/                 # [Infrastructure] 基础配置层
  │   └── config.yaml         # YAML 驱动的各项作业、样式、任务序列定义
  ├── resources/              # [Infrastructure] 资源数据文件层（源表/模板）
  ├── src/excel_generator_project/
  │   ├── app/                # [UI/Presentation] 表示层
  │   │   ├── app.py          # Streamlit UI 入口，承接上传/下载与用户交互
  │   │   └── setup.py        # 环境与应用初始化工具
  │   ├── config.py           # [Infrastructure] 单例配置解析器（基于 pyyaml 加载，将字典转化为常量供全局使用）
  │   ├── core/               # [Domain/Application] 核心业务处理层
  │   │   ├── data_processor.py      # 配置驱动的数据读取计算与组装逻辑
  │   │   ├── exception_processor.py # 异常逻辑数据清洗与处理
  │   │   └── font_processor.py      # 后期样式渲染与 Excel 对象级别的字体控制
  │   ├── infrastructure/     # [Infrastructure] 底层基础设施层
  │   │   └── excel_handler.py# 封装的 Excel 原生库 (openpyxl) 读写单元格基类
  │   ├── services/           # [Application] 应用服务层
  │   │   └── report_generator.py # 聚合写入作业配置与业务模板，将最终数据写回 Excel
  │   └── utils/              # [Shared/Utils] 通用工具层
  │       └── utils.py        # 文件查找、路径安全、百分比计算转换等
  ```

- **基础工程规范 (Core Infrastructure Patterns)**:
  - **依赖管理**: `requirements.txt` 作为显式的包依赖管理，目前未明确见到 `uv` 的配置文件 (`pyproject.toml`)，推测采用传统的 `pip` 或虚拟环境进行管理 [待人类确认]。
  - **配置管理 (Config)**: 位于 `src/excel_generator_project/config.py`，使用普通的 YAML 解析结合字典加载机制，并通过定义大写常量（如 `CONFIG`、`PATHS`、`PROJECT_ROOT` 等）暴露给其他模块作为伪单例被导入调用。尚未在核心代码中看到基于 Pydantic 严格类型约束的 `BaseSettings` 链式调用，主要仍依赖原生 dict 和 `.get()` 进行容错读取。
  - **安全与凭证**: [待人类确认] 项目中暂未扫描到明显的 `.env` 环境变量文件以及 `load_dotenv` 机制，路径等配置多硬编码于 `config.yaml` 中，例如共享网盘路径 `\\10.71.4.18\...`。
  - **日志管理 (Logging)**: [待人类确认] 通过 Python 原生 `logging` 模块进行了广泛的 INFO/WARNING/ERROR 记录，但尚未看到高级的层级或分模块格式化日志的单独配置入口，主要是直接调用的 `logging.info()` 等方法。
  - **数据刷新机制**: 项目采用典型的流式刷新策略——通过 `Streamlit` 的缓存装饰器 (`@st.cache_resource`) 保证基础配置的全局一次加载；并在运行报告生成器时（基于 Subprocess 执行 `content_generator.py`）将输出统一落盘至由 `config.yaml` 指定的 `temp_dir` / `output_dir` 中，前端根据子进程结果进行缓存/快照轮换读取。
  - **文件处理逻辑**: 基于 `openpyxl` 执行 `.xlsx` 提取，并配合正则 `re` 在工作表中匹配核心文本块。底层流转逻辑：先上传或拷贝文件到本地临时/缓存目录，然后打开读取；关于“遇到加密文件先将其转化为 csv，再进行读取”的策略，目前的扫描中尚未在主流程代码（如 `Utils` 或 `ExcelHandler`）内直接观察到此转换代码块 [待人类确认]。

# 4. 🎯 业务需求与边界 (Scope & Boundaries)
- **IN Scope (已实现边界)**:
  - 基于 Streamlit 构建的两步式 UI 界面（上传源表生成数据、再次上传应用样式）。
  - 根据配置文件批量读取不同单元格的内容（步长读取 `parse_text_from_cells`）。
  - 动态从共享盘特定规则命名的文件夹（如按年份和周数 `W50`）中扫描最新的周报并提取排产与当月预估良率。
  - 提拉良率目标的自动化解析以及基于百分比字符串转换成 Float 后的 Gap（预估良率 - 提拉良率）计算逻辑。
  - 风险品模块中复杂正则的解析以及按产品型号构建多段文本替换。
- **OUT of Scope (未实现/纯规划)**:
  - 使用 `uv` 等现代工具或 Pydantic 进行更高强度的依赖/配置约束与校验机制。
  - 复杂的环境变量隔离系统（如区分 Dev/Prod 的共享网盘读取认证）。
  - 自动化解密并将 Excel 转化为 CSV 再读取的具体防爆逻辑模块。

# 5. 🤖 开发规范：多 Agent 协作 (EPCC Flow)
*(此部分为硬性纪律，请原样保留)*
1. **Explore**: 必须先阅读相关文件，读懂上下文后再行动。
2. **Plan**: 必须先输出修改计划，交由人类审核。
3. **Code**:
   - **防御性编程**: 必须包含 Type Hints 和基础异常捕获。
   - **结构化输出**: 明确指出修改了哪个文件的哪几行。
   - **🚨 熔断机制**: 同一个 Bug 连续修复 3 次失败，必须立即停止并要求人类介入。
4. **Commit (TDD)**: 
   - 必须先写测试。
   - **✅ 验收标准**: `pytest tests/`，必须达到 100% PASS 才算完成。

# 6. 💻 系统环境与命令 (System Commands)
- **运行命令**: `python -m streamlit run src/excel_generator_project/app/app.py` 或双击 `start_streamlit.bat`
- **测试命令**: `pytest tests/`