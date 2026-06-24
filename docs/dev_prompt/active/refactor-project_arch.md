# Task-项目重构为Agent架构
我需要将当前yield_report模块的TDD架构全面转向一个标准的Agent架构。并且由于我们已经引入了LangGraph，这种转型也便于后续拓展。

## Workflow
1. 请您搜索相关资料，然后拟订一个企业级的标准Agent架构作为转型目标。
    - 参考文档：“D:\wzy\Visionox-Docs_Backup\dev-docs\agent_dev\agent-LangGraph.md”
    - 参考章节：“## 4. 一个典型 LangGraph 项目结构”
2. 请分析当前程序，评估重构工作包括哪些，比如除了移动程序之外，是否需要修改引用、接口，甚至于重写程序。
3. 最终拟订一份执行计划。包括一份最终目标的Checklist。
4. 执行计划进行重构。

## Goal
请不断迭代优化，直至Checklist全部达成。