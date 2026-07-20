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

三个业务 Skill 都由 Agent Runtime 通过稳定工具契约调用：

```text
Agent Runtime
  -> report_download
  -> data_analysis
  -> daily_report facade
       -> public daily-report-generator CLI
```

`report_download` 和 `data_analysis` 是项目能力；`daily_report` 是公共生成器的 Agent facade。它们不互相 import，也不由本地 `daily_report` 递归展开。公共生成器内部的 Mod0-Mod4 顺序、依赖、源表和工作簿交接由公共 skill 自己管理。

## 4. daily_report 边界原则

`daily_report` 的职责：

- 将 Agent 请求适配为公共 `daily_report_cli.py run` 调用。
- 从 Pydantic 配置读取安装路径、CLI 相对路径和 Agent 交付目录。
- 解析公共 CLI JSON，映射为 `SkillResult` 和 Excel artifact。
- 保留旧请求字段的反序列化兼容，但不解释其中的生成业务含义。

`daily_report` 不应：

- 生成或写入日报工作簿。
- 复制公共生成器的报表名称、日期策略、Mod 参数或依赖顺序。
- 默认强制公共 CLI 使用 Agent repo 作为 workspace。
- 从 `source_files` 魔法键读取 generator 配置。
- 直接写 confirmed memory。

公共生成器拥有完整实现；项目侧只维护上述 facade 和契约测试。
