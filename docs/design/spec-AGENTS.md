## AGENTS.md 承担什么功能？

你可以把它理解成：

README.md       = 写给人看的项目介绍
AGENTS.md      = 写给 Agent 的项目操作手册
Skill / Docs   = 任务需要时再读取的详细知识

AGENTS.md 的职责主要有 5 个：

|功能 |	说明 |
| ------ | ------ |
|项目定位|	告诉 Agent 这个仓库是干什么的，核心边界是什么|
|目录导航|	告诉 Agent 关键代码、配置、测试、文档在哪里|
|工作约束|	告诉 Agent 哪些文件不能改、哪些行为必须确认|
|执行命令|	告诉 Agent 如何安装、运行、测试、构建、格式化|
|验收标准|	告诉 Agent 改完后如何证明自己没改坏|

AGENTS.md 官网也把它定义为一种面向 coding agents 的开放格式，可以把它理解为 “README for agents”，用于提供上下文、构建步骤、测试命令、代码约定等信息。 GitHub Copilot coding agent 也已经支持根目录和嵌套 AGENTS.md，用于指导 Agent 理解项目、构建、测试和验证修改。

## 专业写法的核心原则
1. 原则一：短，而不是全

AGENTS.md 不应该写成一本架构长文。因为它通常会被自动加载到上下文里，写太长会浪费 token，还会让 Agent 分不清重点。

更好的方式是：

AGENTS.md：只写高频、强约束、必须遵守的规则
docs/：写详细架构说明
skills/：写专项工作流
spec/：写业务规则和可配置规则

尤其对你这种数据分析项目，AGENTS.md 不应该塞满 OLED 良率定义、Excel 字段映射、所有日报规则。它应该告诉 Agent：这些规则在哪里读，什么时候读，怎么验证。

2. 原则二：写“可执行规则”，不要写“愿景”

不好的写法：
```
请写高质量代码。
请注意可维护性。
请充分理解业务。
```

好的写法：
```
- 修改 Python 代码后，必须运行 `pytest tests/`。
- 不允许在 `src/reporting/templates/` 中硬编码业务阈值；阈值必须来自 `spec/*.yaml`。
- 如果修改日报生成链路，先阅读 `docs/pipeline.md` 和 `spec/daily_report.yaml`。
```

专业 AGENTS.md 里的每条规则最好能回答：
- Agent 应该做什么？
- 不应该做什么？
- 去哪找依据？
- 如何验证？

VS Code 的官方建议也类似：项目级指令适合写 coding style、技术栈、架构模式、安全要求、错误处理、文档标准；并建议保持简短、自包含，必要时说明规则背后的原因。

3. 原则三：根目录写通用规则，子目录写局部规则

如果项目复杂，不要把所有规则写在根目录一个文件里。

例如：
```
AGENTS.md
src/backend/AGENTS.md
src/frontend/AGENTS.md
spec/AGENTS.md
tests/AGENTS.md
```
OpenAI Codex 的发现机制支持这种“层级叠加”：从项目根目录一路读到当前工作目录，越靠近当前目录的 AGENTS.md 越具体。 VS Code 也说明，AGENTS.md 适合多 Agent 共享，也适合在 monorepo 或子文件夹中提供局部规则。

例如：

根目录 AGENTS.md：
- 项目整体原则
- 通用测试命令
- 禁止事项

spec/AGENTS.md：
- spec 文件格式
- 修改 spec 后要运行哪些验证
- spec 与代码的边界

src/backend/AGENTS.md：
- API 设计约定
- 数据处理约定
- 错误处理方式

## 什么内容应该写入 AGENTS.md？

我建议专业 AGENTS.md 至少包含下面 8 类内容。

1. Project Overview：项目一句话定位

写清楚项目是什么，不是什么。
```
## Project Overview

This project is an Excel-based OLED manufacturing data analysis assistant.
It ingests Excel reports, applies business specs, performs data analysis, and returns natural-language insights and downloadable reports.

This is not a generic BI system. Prefer explicit, traceable analysis over broad automatic inference.
```
对你的项目，可以写成中文也可以写成英文；如果工具主要是 Codex/Copilot，英文通常更稳。

2. Architecture Map：关键目录地图

Agent 最怕在项目里迷路。你应该直接告诉它哪些目录重要。
```
## Architecture Map

- `src/`: application source code.
- `src/analysis/`: Excel parsing, dataframe transformation, and metric calculation.
- `src/reporting/`: report generation and export logic.
- `spec/`: user-maintained business rules and report definitions.
- `skills/`: agent-facing task instructions and workflows.
- `docs/`: architecture notes and design decisions.
- `tests/`: unit and integration tests.
```
注意：不要把每个文件都解释一遍，只列“Agent 经常需要找的地方”。

3. Task Routing：不同任务先读什么

这是专业 AGENTS.md 很重要的一部分。你要告诉 Agent：遇到什么任务，先看什么文件。
```
## Task Routing

- For report-generation changes, read `spec/daily_report.yaml` and `docs/report_pipeline.md` first.
- For Excel parsing or column mapping changes, read `spec/column_mapping.yaml` first.
- For metric logic changes, read `docs/metrics.md` and the relevant spec file before editing code.
- For UI changes, read `src/frontend/AGENTS.md` if present.
```
这比把所有规则粘进 AGENTS.md 更好。

4. Rules Boundary：哪些内容由 spec 决定，哪些内容由代码决定

你之前一直在问 “用户自定义 spec → skill → code” 的传递机制。这个边界非常适合写进 AGENTS.md。
```
## Rules Boundary

Business rules that may change frequently must live in `spec/`, not in source code.

Examples of spec-owned rules:
- report sections and ordering
- column aliases and field mappings
- thresholds for warning / risk labels
- chart titles and display labels
- filtering conditions for standard reports

Examples of code-owned logic:
- Excel file reading and validation
- dataframe transformation primitives
- chart rendering engine
- API endpoints
- security and permission checks

Do not hard-code business thresholds in Python unless the user explicitly asks for a one-off experiment.
```
这类规则对 Agent 非常有用，因为它能防止 Agent 把业务规则写死在代码里。

5. Commands：安装、运行、测试、格式化命令

AGENTS.md 官网示例也把 setup、dev server、tests 放在最前面，因为 Agent 需要知道怎么验证。 Devin 的文档示例也包括安装、启动、测试、构建、代码风格、测试规则、项目结构等内容。
```
## Commands

- Install dependencies: `pip install -r requirements.txt`
- Run tests: `pytest tests/`
- Run a focused test: `pytest tests/test_daily_report.py -q`
- Format Python: `ruff format src tests`
- Lint Python: `ruff check src tests`
- Start API server: `uvicorn app.main:app --reload`
```
如果有些命令在公司环境跑不了，也要写明：

If external network access is unavailable, do not install new dependencies. Ask before adding dependencies.

6. Coding Conventions：代码风格与设计偏好

不要写太泛，要写对项目有约束力的。
```
## Coding Conventions

- Prefer small pure functions for dataframe transformations.
- Keep business-rule loading separate from calculation logic.
- Avoid hidden global state. Pass specs explicitly into functions.
- Use typed dataclasses or Pydantic models for parsed spec objects.
- Do not introduce new dependencies without explaining why.
```
这和你之前的偏好很一致：数据函数、样式函数、规则配置要分离。


7. Testing / Validation：完成任务前必须验证什么

Agent 交付质量的关键就是“改完必须跑什么”。
```
## Validation

Before finishing:
- Run the smallest relevant test first.
- If report logic changed, run at least one end-to-end sample generation.
- If spec parsing changed, add or update tests for invalid spec cases.
- If tests cannot be run, explain exactly why and list the commands that should be run manually.
```
GitHub Copilot changelog 也提到 AGENTS.md 可指导 Agent 如何 build、test、validate changes。


8. Safety / Don’ts：禁止事项

这部分要写得硬一点。
```
## Safety Rules

- Do not commit or print secrets, API keys, cookies, or internal credentials.
- Do not modify files under `data/raw/` unless explicitly asked.
- Do not delete user-uploaded files.
- Do not rewrite large modules unless the task explicitly requests refactoring.
- Ask before changing public APIs or file formats.
```
对公司数据分析项目，这部分特别重要。

4. 什么不应该写进 AGENTS.md？

专业工程师会避免把 AGENTS.md 写成“万能知识库”。

不建议写入：

|不建议写入|	原因|	替代位置|
| ------ | ------ | ------ |
|大段业务背景|	占上下文，且任务未必需要|	docs/domain.md|
|所有字段定义|	太长且易过期|	spec/column_mapping.yaml|
|详细 PRD|	Agent 每次都加载浪费 token|	docs/prd/|
|长篇架构推理|	不适合 always-on|	docs/architecture.md / ADR|
|临时任务要求|	容易污染长期规则|	当前 prompt|
|密钥、内网地址、账号|	安全风险|	环境变量 / secret manager|
|模糊要求|	无法执行|	改成命令、边界、验收标准|

这里特别提醒：一篇 2026 年的研究论文发现，仓库上下文文件并不总是提升 coding agent 成功率；不必要的要求会让任务更难，并增加推理成本，因此人工写的上下文文件应该只描述最小必要要求。 这和实践经验一致：AGENTS.md 越像“短规则清单”，效果越好；越像“万字知识库”，越容易伤害 Agent 表现。