# Background
你好，我是一家OLED显示屏制造公司的员工。
我的岗位是工艺整合部的大数据工程师。
我在开发一个能够自动分析良率数据、识别真实异常、编写日报的智能体。

# Goal
目前，我们需要为我们的Agent选择一个成熟的框架作为Runtime。

---

# Task0

## Background
1. 我计划将当前的Agent Runtime由OMP迁移为letta。我的初步调研文档位于如下路径：“D:\wzy\Visionox-Docs_Backup\dev-docs\agent_dev\letta_agent_runtime_migration_guide_2026-06-22.md”。
2. 但是当前该文档对于Letta的功能与其对应的机制（或使用方式）介绍的并不全面，并掺杂了部分计划相关的内容。因此我们需要重写该文件。

## Workflow
1. 请你从以下几个角度，查询并记录Letta的功能与其对应的机制（或使用方式）：
```
1. 长期 memory
2. tool / skill registry
3. ReAct 或 tool-call loop
4. context compression / compaction
5. session 管理
6. 用户/任务状态管理
7. 文件和数据库工具
8. 权限与审计
9. API 或服务化能力
10. 可插拔业务工具
```
2. 删除计划相关的内容。

## Goal
更新后的文件应该可以让Coding Agent（例如Codex）清晰地知道如何基于Letta构建Agent Runtime，同时对于人也具备良好的可读性。

---

# Task1
你好，经过思考。我决定采纳你的建议，放弃OMP。但是我们依旧需要使用一个现成的Agent来作为Agent Runtime。

## Workflow
1. 请你搜索并评估Letta这个Agent，评估其是否比OMP更适合作为Agent Runtime？\
2. 如果是，请详细了解其所有的使用方法，为将当前项目的Agent Runtime迁移成Letta做准备。
3. 请将详细的教程文档输出至如下路径：“D:\wzy\Visionox-Docs_Backup\dev-docs\agent_dev”。

## Goal
请不断搜索，直到满足以下所有条件或没有有效的资料：
1. 你认为对于letta的了解已经可以覆盖当前已实现的功能（最为核心的功能是skill调用、React循环和Memory机制）
2. 了解其详细的调用方式（具体代码），从而可以让其作为Agent Runtime接入当前项目

---

# Task1-fix
1. 你需要的这些配置是否是因为你使用的是Letta Cloud？请问我们不能将Letta部署到本地吗。请从以下角度评估：
    - 它对于硬件的要求有多高
    - 当前PC的能力是否可以部署letta（我们的Agent最多不会超过三个人同时使用）
2. 依据第一步的结果执行以下操作，并将结果输出至“docs\generated”：
    - 如果不可以，我去申请Letta Cloud账户，请告诉我相关教程
    - 如果可以，请进行部署，并告诉我如何提供给你这些配置（最好设置为无密码）
3. 如果选择本地部署，请继续检查以下两个问题：
    - letta-client 版本和 Letta Server 版本是否兼容：因为Letta 这类项目迭代快，client/server 版本不匹配可能导致 API 字段不兼容
    - 创建 Agent 时是否显式配置 model 和 embedding：我目前只有常规LLM的key，并没有embedding model的key。如果你需要后者，请告知我

---

# Task2：Agent Runtime功能完善
谢谢。接下来请查看这个文档：“D:\wzy\Visionox-Docs_Backup\dev-docs\agent_dev\letta_agent_runtime_migration_guide_2026-06-22.md”
其中是Agent Runtime必备的十几项功能和letta对应的机制用法。但目前我们使用了Letta Cloud，请问我们还需要自己进行配置管理吗，云端Agent是否自带这些功能了？

## Workflow
1. 请逐一判断当前的Agent Runtime是否具备了这些功能（不包括“权限与审计”），包括云端Agent已经自带的。
2. 如果没有，请判断能否进行完善补充（本轮补充仅基于Letta，暂时不要自行构建机制）
3. 如果可以，请进行补充。

## Goal
不断完善，直至我们的Runtime已经具备了清单中所有可以基于Letta实现的功能