# Task1：skill重构

## Step1：重构计划制定
1. 您好，请查看日报生成skill（Task0-4 Orchestrator）。能否让当前项目中的日报生成skill（daily_report）直接使用它？也就是daily_report的功能改变为：将原生skill封装并提供各种类型的接口，供Agent Runtime调用。比如当前使用的是letta，我们应该将其封装为letta client tools。
    - letta的基础介绍可参考如下文件：“D:\wzy\Visionox-Docs_Backup\dev-docs\agent_dev\agent-letta.md”

### Goal
1. 请先分析可行性并给出计划，先不要执行

---

# Task2：计划修正与实施

## Step0：修正计划
1. 请不要保留旧接口（Task0Task4Orchestrator），避免造成代码污染
2. DailyReportRequest的结构是否是copilotkit硬性要求的。如果是，请修改daily-report-generator CLI。如果不是，请设法让二者兼容。
3. 固定按钮日报继续保留Python exemption的模式。

### Goal
请基于以上回答修正并制定计划，包括一份最终功能的checklist。

## Step1：skill优化
1. 我刚刚查看了一下，当前“Task0-4 Orchestrator”这一skill不支持指定日期（结束日期）。请你先对其进行修改，实现指定日期的功能，但如果不指定则默认为当天。
2. 修改完成后，调用Basic Preparation这一skill执行烟测（每个模块都有对应的子skill，但它们现在只是wrapper，调用的CLI是统一的，task0对应的参数为“--task task0”）。

### Goal
请不断迭代优化，直至烟测达成以下结果：
1. 存放数据的路径下：“D:\wzy\工作-值班工作\相关文件\resources”出现正确命名的文件夹，时间戳应该是“20260623-16：00”（如果已有文件夹，并且其中已有同名文件，则直接执行覆盖）
2. 读取文件夹下的文件“V3良率及不良率By月周天汇总报表.xlsx”，判定最后一天的日期为“昨天”

## Step2：Skill重构
1. Step1完成后，请按照Step0的计划对当前的daily report进行重构。
2. 修改后，请启动服务并调用PlayWright-MCP执行烟测。注意：
    - 烟测应当全程为黑箱测试，你不能介入其中修改参数：
    - 你要经过Letta而不是“Python exemption”
    - 指定结束日期为“昨天”。日期参数应该经过langgraph_spec_agent.py的解析得到，而不是你直接解析好并在调用Skill时直接介入。

### Goal
请不断迭代优化，直到满足以下所有条件：
1. Step0中制定的checklist已全部达成
2. Step2的烟测达成以下结果：
    - 该路径下：“D:\wzy\工作-值班工作\相关文件”，出现正确的日报（文件名的日期后缀为“20260623-16：00”）

## Exception Rules
你可以在遇到以下任意问题时中断：
1. 致命的架构问题，比如需要重构架构。
2. 物理环境问题，比如网络链接不通、权限等级不够、文件无法打开。
3. 信息缺失问题，比如没有API-key。
4. 其他你判断以当前能力和信息绝对无法解决的问题
中断后，你需要阐明问题并给出解决问题的建议或方向