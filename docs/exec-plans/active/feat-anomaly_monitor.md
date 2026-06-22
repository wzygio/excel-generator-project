# Anomaly Monitor

## Background
当前项目已经具备了以下三个功能：报表下载、数据分析、日报生成。其中，前两个模块为灵活业务模块，日报生成为固定业务流程。
我们增加一项固定业务流程的功能：真实异常识别。即分析当日异常相关数据，判断出哪些为真实异常。

# Reference 

## 参考模板
我已经在另一个项目中搭建了一个参考模板，现在请您分析并将其业务逻辑迁移到当前项目中。
参考模板路径如下：“D:\wzy\Python\agents-projects\packages\anomaly_monitor”

## 详细规则
该部分的详细规则文件位于如下路径：“docs\dev-docs\屏体大数据科-良率监控智能体需求梳理.xlsx”
- sheet页：“值班智能体-需求梳理”
- 它是加密文件，请先尝试解密再读取。
- 目前我的模板文件仅实现了“1.1.1-1.1.3”之间的步骤，并且由于模板是之前编写，所以规则并不完全正确，请以规则文件中的定义为准

## Data Source
1. 数据源路径：“\\10.71.7.15\大数据共享\12.良率监控日报自动化”
- 该项目所需的所有数据都位于该路径下
2. 当日过货表：：“D:\wzy\工作-值班工作\相关文件\resources\spotfire.xlsx”
-当日过货产品：位于第一列

---

# Task1

## Workflow
1. 请你先分析并了解模板项目
2. 请你分析并理解“异常监控”规则
3. 通过.understand-anything和ARCHITECTURE.md快速了解当前项目的结构
4. 根据当前的前端和后端架构，使用planning-with-files制定“异常监控”模块的开发计划
- 模板中能够复用的可以直接迁移，但要契合当前项目架构

## Goal
1. 请调用planning-with-files制定完整的开发计划（包括UI开发），先不要执行

---

# Task1-2
1. 请创建一个新worktree，来执行上面制定的计划
2. 请调用verification-loop来检查，直至所有Checklist全部通过
- 可以通过Playwright MCP来启动本地Chrome完成冒烟测试

---

# Task2
1. 针对固定业务流程，都请提供一个“一键执行”的按钮（类似于当前的“全自动日报生成”），让我可以一键执行

--- 

# Task2-fix

## Problem
一键执行失败。返回结果如下：
```
异常监控缺少当日异常初筛表数据。
缺少 daily_anomaly_initial/initial_rows，无法执行异常识别。

读取源表失败(daily_anomaly_initial): Excel file does not exist: D:\wzy\Python\excel-generator-project-anomaly-monitor\resources\anomaly_monitor\当日异常初筛表.xlsx
读取源表失败(ct_map_ng): Excel file does not exist: D:\wzy\Python\excel-generator-project-anomaly-monitor\resources\anomaly_monitor\CT MAP-NG.xlsx
读取源表失败(ct_map_ratio): Excel file does not exist: D:\wzy\Python\excel-generator-project-anomaly-monitor\resources\anomaly_monitor\CT MAP-RATIO.xlsx
```

## Workflow
1. 请详细分析参考模板：“D:\wzy\Python\agents-projects\packages\anomaly_monitor”（如果有必要可读取agents-projects项目）
2. 确定项目中所使用的数据表来源及构建方式。
- 所有的数据表都是从数据源路径下的原始表中提取出来的。提取逻辑应该已经写在了anomaly_monitor模块中。
3. 确定并复刻真实异常筛选逻辑。
- 异常筛选逻辑应该也写在了anomaly_monitor模块中。

## Goal
1. 检查优化直至可以识别出真实异常。
- 有任何无法解决的问题都可以向我寻求帮助。
2. 请将整套流程构建为方便Agent插拔的Skill。

## Rules
1. 当你发现无法读取加密文件时，请先调用“File Decryption”解密
2. 当你发现无法理解表格结构时，请先调用“Table Schema Detect”进行探查

--- 

# Task3
请将该worktree merge到master branch上“D:\wzy\Python\excel-generator-project-anomaly-monitor”：
1. 请你先扫描并了解该worktree：它新增了一个anomaly_monitor模块，包括后端的skill和前端按键。
2. 当前master branch已经进行了Agent Runtime的重构。因此Agent内核和架构以master branch为主。
3. 如果有conflict，请修改代码进行解决。

## Goal
不断迭代优化直至anomaly_monitor被完美接入，包括以下两点要求：
1. 后端：Agent Runtime流畅调用anomaly_monitor skill
2. 前端：调用Playwright-mcp执行冒烟测试，确保“异常监控”功能可以顺利执行（顺利筛选出真实异常）

---

# Task2-fix-2

## Problem
我查看了当前您的输出结果：“output\anomaly_monitor_smoke\anomaly_monitor_summary.md”。HL项太多了。一般不会超过10项。

## Workflow
1. 请您先查看并分析可能的原因：
  - 是否是因为数据表构建的问题
  - 是否是因为集中性判定存在问题？请大幅收严HL规则，比如Top1 占比收严至50%，Top5 累计收严至80%
  - 是否是因为站点筛选规则的问题：我们只HL“【发生站点】”为“CT”的不良
2. 此外，你必须要考虑已经产出的单元（比如lot或膜位）总数。如果一共就产出了5个，那么Top5占比能够达到100%。所以是否不应该固定取Top1和Top5，而是要取固定比例的单元？

## Goal
1. 请不断迭代优化，然后重新运行skill输出结果，直至筛选出的HL异常缩小至15个以内
