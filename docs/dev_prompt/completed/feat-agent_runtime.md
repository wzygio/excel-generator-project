# Task1
你好，我正在开发一个智能体项目。但我不知道如何构建一个Memory系统，所以我想引入一个已有框架。
1. 请在github上搜索agent-memroy和mempalace这两个项目。
2. 并告诉我哪个适合作为Agent Runtime的memory？

## Requirements
衡量标准如下：
1. 它应该是针对一个智能体项目的memory框架，而不是优化Codex这种通用智能体。
2. 它应该尽可能的轻量化，适合部署给当前项目。

## Hint
如果你搜索后判断这两个框架都不适合部署给当前项目，请再给出一两个建议、

---

# Task2
为了当前智能体项目稳定运行和未来拓展，我们都必须引入一个专业框架来作为Runtime框架。请您搜索并给出推荐。
## Context
- 最为标准的毫无疑问是LangChain或LangGraph。
- 但我想知道有没有更为轻量级，但同样性能稳定、便于拓展的框架？
- 还是说即便我们使用LangChain或LangGraph，依旧可以直搭建一个较为轻量的框架。

---

# Task3
我们之前编写的用于构建AGENTS.md的Skill需要修改。
1. 请在AGENTS.md中新增两条规则：
    - 每次制定计划完成后，请用户确认，通过后将计划更新至“docs\plans”中。
    - 每次执行代码后，请用户确认，通过后将新架构更新至“ARCHITECTURE.md”
2. 请检查AGENTS.md中是否有随着业务代码改动而需要改动的地方，如果有，将其剥离至下层的Harness文件。AGENTS.md中的架构和规范不应该随业务代码变动而变动。
3. 执行完以上任务后，请将该逻辑同步至编写AGENTS.md的skill中。

# Task3-1
你好，请扫描Agent Runtime，

---

# Task4
Harness的Skill同样需要修改。
1. 请补充以下几项：
    - 可观测性入口（Codex 能力 + Agent 维护）：用于后续指导Codex稳定实现开发目标。
    - 垃圾回收机制（Agent 维护）：用于指导Codex定期清理项目Harness。
    - plan中必须区分“当前执行计划：docs/exec-plans/active/*.md” 和 “历史执行计划：docs/exec-plans/completed/*.md”
2. 执行完上述任务后，请将该逻辑同步至构建Harness的skill中

---

# Task6
当前项目是一个良率监控智能体。使用OMP作为Agent Runtime来执行良率分析等任务。
但OMP是否过重（尽管它已经是我使用的最轻的一个Agent）？我们是否应该将Agent Runtime替换为更加轻量级内核（比如PI和nanobot）？
请你在github上查询一下agent项目并搜索相关资料，最终给出建议。请将结果输出至如下路径：“D:\wzy\Visionox-Docs_Backup\dev-docs\agent_dev”

请您从以下几个角度考虑：
1. agent能力
2. agent复杂度
3. agent记忆能力（这一点非常重要，因为作为一款业务Agent，一旦运行起来之后，我没有时间取手动管理记忆）

---

# Task：Spec机制梳理

1. 请问当前目录中的spec是Agent Runtime生成，还是Codex生成？
2. 我注意到它们的命名规范并不一致。当前的spec构建机制是什么？应当如何管理？
3. 当前AGENTS.md中的“## Rules Boundary”是在划定spec和coding的界限吗？它是否合理？

# Task：Spec机制构建

## Requirements
谢谢。但是需要修改：
1. run_id不能够使用“run-YYYYMMDD-HHMMSS”这种看不出业务功能的命名方式
2. 我们要构建的智能体是强人工交互的Agent。因此，规则构建模式只能够用于固定流程触发（例如UI上的“日报生成”和“异常HL”的按键触发）。其余所有基于对话框执行的任务，哪怕是我在对话框里要求生成日报，spec都必须经由LLM进行构建。
3. LLM生成spec时除了参考Template之外，是否会参考“docs\agent\spec_contract.md”？如果没有，如何约束它生成标准spec？
4. 您的其余关于spec目录管理的建议值得采纳。

## Goal 
请思考并修正当前的spec管理机制，并更新至该文件：“docs\agent\spec_contract.md”