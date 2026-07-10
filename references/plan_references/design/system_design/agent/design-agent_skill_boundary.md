# Agent Skill 边界设计

## 1. 结论

本项目采用 **Codex 作为 Agent 核心，Python Skill 作为稳定能力入口** 的架构。Skill 不是把业务规则全部写成自然语言，也不是让 LLM 每次自由发挥；Skill 的定位是：

- 让 Codex 知道什么时候调用某个能力。
- 定义结构化输入、输出、错误和产物。
- 说明失败后如何恢复、如何扩展。
- 作为用户和 Codex 修改流程的说明书。

代码的定位是承载稳定、频繁、可测试、可复现的业务实现。尤其是日报准确性相关逻辑，必须沉淀为代码或配置，而不是只放在 prompt 或 `SKILL.md` 中。

## 2. Skill 与代码的边界

应沉淀为代码的能力：

- 结果必须稳定、可单测、可复现的计算逻辑。
- 高频执行且对速度、成本敏感的流程。
- 文件匹配、解密、Sheet/列定位、字段校验、Excel 写入等 IO 细节。
- Gap 公式、TopN 排序、趋势判断、异常匹配、Code 到 Group/Factory 映射等业务规则。
- confirmed memory 的读取约束和写入保护。

应写入 Skill 文档和 Spec 的能力：

- 用户可自然语言维护的流程目标、章节、输入和输出约束。
- Codex 何时调用 Skill、输入字段含义、失败恢复方式。
- Skill 可扩展点、示例需求、常见错误码。
- pending memory 候选的确认口径。

应交给 Codex/LLM 的能力：

- 用户需求澄清和 `spec.yaml` 修改。
- 结构化事实到日报段落的润色。
- 数据不足时生成谨慎说明。
- 多条异常记录的摘要合并。
- 生成待确认 memory 候选，不能直接写入 confirmed memory。

判断规则：

- 错一次会影响日报准确性的，优先代码。
- 用户经常会改流程但不改算法的，优先 Spec。
- Codex 需要理解调用方式的，写入 Skill。
- 需要推理、表达或人工确认的，交给 Codex/LLM 生成候选。
- 重复出现三次以上的 prompt 逻辑，应迁移为代码或配置。

## 3. 三个 Skill 的协作边界

三个业务 Skill 的关系是：

```text
daily_report > data_analysis > report_download
```

这里的“大于”不是 Python import 方向，而是业务拆解方向。上层 Skill 不直接调用下层 Skill；上层只声明自己缺少什么，下层返回自己产出了什么，由 `AgentRuntime` / `SpecCompiler` 展开调用。

目标闭环：

```text
daily_report 缺分析事实
  -> RequiredAction(data_analysis)
  -> data_analysis 缺源表
  -> RequiredAction(report_download)
  -> report_download 返回 ArtifactManifest
  -> data_analysis 返回 AnalysisFactRef
  -> daily_report 消费 AnalysisFactRef
```

这种设计让每个 Skill 保持独立可调用，同时完整日报任务可以像递归拆解一样有条理地完成。

## 4. daily_report 边界原则

`daily_report` 的职责：

- 判断生成日报需要哪些分析事实。
- 消费 `analysis_results` / `analysis_facts`。
- 写出最终 Excel、JSON、Markdown 产物。
- 在缺少事实时返回 `RequiredAction`，让 Runtime 展开 `data_analysis`。

`daily_report` 不应：

- 直接 import 并调用 `data_analysis`。
- 直接隐藏式下载源表。
- 把核心 Gap/趋势/异常计算只写进自然语言 prompt。
- 直接写 confirmed memory。

当前 HEAD 中 `daily_report` 仍是占位实现。本轮先建立契约闭环，不做日报算法全量深拆。
