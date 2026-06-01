# Task2 冒烟测试任务清单

## 目标
- 从 `resources/spotfire.xlsx` 提取当日过货产品。
- 按 `specs/spec-daily_report.md` 验证 2.1 当日 Gap、2.2 连续三天下降、2.3 已知异常、2.4 新增异常。
- 按层级验证 `日报生成 > 数据分析 > 报表下载`，定位失败属于子层能力还是父层交互。

## 子任务
1. 报表下载层
   - 调用 `report_download` 获取或定位 `daily_yield`、`target_decomposition`、`ct_exception`。
   - 记录每个源表的 `success/artifacts/error/warnings`。

2. 数据分析层
   - 读取 `spotfire` 产品列表。
   - 调用 `data_analysis` 的 `analysis_kind=daily_report` 模式。
   - 验证每个产品均返回 `gap/trend/known_exception/new_exception` 四段结构。
   - 若存在 `blocked`，记录缺失源表或缺失产品数据原因。

3. 日报生成层
   - 调用 `daily_report` 生成 Excel/JSON/Markdown。
   - 验证成功结果不得包含 `blocked_sections`。
   - 验证 JSON 每个产品都有四段结构。
   - 验证 Excel 第 4 行起写入产品数据和日报文本。

4. UI 冒烟
   - 启动 Streamlit。
   - 通过 Playwright 点击 `日报生成` -> `一键生成日报`。
   - 验证 UI 展示本次运行结果、产物路径或明确失败原因。

## 判定规则
- 子任务成功、父任务失败：优先修层级交互。
- 子任务失败：优先修对应层级能力。
- 缺必需数据时不得显示“日报生成完成”，不得展示旧 Excel 下载按钮。

## 执行结果（2026-06-01）
- 报表下载层：通过。`daily_yield`、`target_decomposition`、`ct_exception` 均可获取或定位。
- 数据分析层：初次失败，定位为 FineReport/Excel-COM 导出的 `daily_yield` 在 `openpyxl read_only=True` 下保留了错误的 `A1:A1` worksheet dimension，导致 CT Sheet 只读到 1 列，产品 CT 行无法匹配。已修复为读取前重置 worksheet dimension。
- 数据分析复测：通过。8 个产品均返回 `gap/trend/known_exception/new_exception` 四段结构，`blocked_sections=[]`。
- 日报生成层：通过。生成 `output/task2_smoke/task2_daily_report_smoke.xlsx/json/md`，JSON 中 8 个产品均有四段状态，Excel 从第 4 行起写入产品和日报文本。
- UI 冒烟：通过。Streamlit `http://127.0.0.1:8503/` 点击 `日报生成 -> 一键生成日报` 后显示“日报生成完成: 8 个产品”，并展示 Excel/JSON/Markdown 下载按钮。
- UI 产物：`output/daily_report_output.xlsx`、`output/daily_report_output.json`、`output/daily_report_output.md`。

## 回归结果
- `uv run pytest tests/unit/agent tests/unit/skills -q --tb=short`：18 passed。
- `uv run pytest tests/unit/test_file_decryption.py tests/unit/test_analysis_file_resolver.py -q --tb=short`：7 passed。
- `uv run ruff check app/main.py src/yield_report/skills tests/unit/skills`：passed。
