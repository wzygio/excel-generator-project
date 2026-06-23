# Task：把业务工具包装为 Letta client tools

## Step0：重构必要性分析和计划拟订
1. 请查看该文件：“D:\wzy\Visionox-Docs_Backup\dev-docs\agent_dev\agent-letta.md”，其中的“10. 可插拔业务工具”。
2. 请问按照它的建议，当前项目中对应的部分是否已经转化为了Letta client tools？spec builder不在此列，我用LangGraph将SpecBuilder相关功能重构为了一个单独的智能体。
3. 如果没有，你的分析和建议是什么？
    - 如果你也任务需要将必要的工具类程序转化Letta client tools。请给出计划。
    - 如果你认为不需要，请给出理由。

## Step1：执行计划

### Answer
1. 固定业务流程（anomaly_monitor和daily_report）应同时兼容UI触发和letta调用两种模式。
2. run_task_spec直接改为强制 Letta
3. 其余同意。

### Workflow
1. 请基于上述信息修正开发计划。包括一份完整的checklist。
2. 请先测试letta cloud是否确实能够连通并使用。如果不能，直接中断，不再执行后续步骤。
3. 按照计划执行开发。
4. 调用Playwright-MCP完成烟测。测试用例位于：“D:\wzy\Python\excel-generator-project\docs\prompt\test-template.md”

### Goal
请不断迭代优化，两个测试用例在烟测中通过"Acceptance Standards"。

