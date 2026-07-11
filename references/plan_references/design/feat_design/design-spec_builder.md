# Spec 生成与管理机制设计

## 1. 结论

Spec 是 Agent Runtime 的需求解析产物，也是 Runtime 执行前的结构化输入。当前机制采用 **LangGraph Spec sub-agent 作为默认 Spec 构建路径**，只有固定业务流程 `anomaly_monitor` 和 `daily_report` 可以在明确声明为固定流程时使用规则构建。

本文件描述 Spec 的生成链路、模块职责和目录管理方式。Spec 字段、校验规则、`run_id` 格式、模板要求和固定流程白名单仍以 [Spec contract](../system_design/agent/spec_contract.md) 为唯一规范来源。

## 2. 设计边界

本设计文档负责回答：

- Spec 由哪些运行时组件生成。
- 默认构建路径和规则构建路径如何分流。
- 构建失败如何进入修复或人工确认。
- `specs/` 目录下哪些内容长期维护，哪些内容是运行产物。

本设计文档不负责定义：

- `TaskSpec` 的字段结构。
- `run_id` 的精确格式和枚举约束。
- Skill 输入输出 schema。
- 模板 YAML 的逐字段要求。

以上内容统一维护在 Agent system design references 和 `specs/templates/` 中。

## 3. 构建链路

```mermaid
flowchart TD
    trigger["Agent Runtime trigger metadata + user goal"] --> request["SpecBuildRequest"]
    request --> builder["SpecBuilder"]
    builder --> gate{"fixed_flow and allowed capability?"}
    gate -->|yes| rule["Rule builder"]
    gate -->|no| graph["LangGraphSpecAgent"]
    graph --> context["Load contract, templates, Skill context"]
    context --> draft["Generate draft"]
    draft --> validate["Parse and validate"]
    validate --> repair{"validation errors and repair budget left?"}
    repair -->|yes| draft
    repair -->|no| finalize["Finalize ready or needs_confirmation"]
    rule --> final_spec["TaskSpec"]
    finalize --> final_spec
    final_spec --> store["RunStore writes specs/runs/<run_id>/spec.yaml"]
    store --> runtime["Agent Runtime executes TaskSpec"]
```

`SpecBuilder` 是对外门面。调用方不直接选择 LLM 或规则细节，而是提交 `SpecBuildRequest`，由 `SpecBuilder` 根据契约判断使用默认的 LangGraph 构建，还是进入固定业务流程的规则构建。

## 4. LangGraph Spec Sub-Agent

`LangGraphSpecAgent` 是默认 Spec 构建器。它的职责是把用户目标、触发元数据、契约文档、模板和 Skill 上下文合成为可校验的 `TaskSpec`。

核心节点：

- `load_context`: 读取 Spec 契约、Skill 契约和可用模板。
- `generate_draft`: 调用 LLM 生成 draft Spec。
- `parse_validate`: 解析 draft，并用统一校验器检查字段、Skill、能力枚举和运行约束。
- `repair`: 将校验错误反馈给 LLM 自动修复，当前最多重试 2 次。
- `finalize`: 校验通过则输出 `ready` Spec；仍失败则输出 `needs_confirmation`，并保留结构化校验问题。

LangGraph 只负责 Spec 构建的状态机，不替代 Runtime 执行 Skill，也不绕过统一 Spec 校验器。LLM 生成内容必须被解析、补齐运行时字段并通过校验后，才能作为可执行 Spec 保存。

## 5. 规则构建路径

规则构建只用于固定业务流程按钮或等价的固定流程调用。当前允许的固定流程只有：

- `anomaly_monitor`
- `daily_report`

固定 `daily_report` 的 `SkillCall.input` 只生成公共 facade 所需的 `report_date`。模板、章节、源表、分析结果、输出文件名和 Mod 参数属于公共 `$daily-report-generator`，不得嵌入项目 Spec。

进入规则构建必须同时满足：

- 请求显式声明为固定业务流程。
- capability 属于固定流程白名单。
- source 与 capability 来自 Runtime 元数据或代码枚举，而不是 Codex、LLM 或用户自然语言自由拼接。

不满足条件时，不允许静默回落到旧规则逻辑。非固定任务统一进入 `LangGraphSpecAgent`；若固定流程声明非法，则返回结构化错误或 `needs_confirmation`。

## 6. Run ID 与触发元数据

`RunIdFactory` 负责生成和校验运行标识。它只消费 Agent Runtime 提供的 source、代码枚举中的 capability 和当前时间。

设计要求：

- Codex 不参与 Agent 执行链路，也不生成 `run_id` 片段。
- LLM 不自由生成 source、capability 或完整 `run_id`。
- 用户自然语言只能表达业务目标，不能直接成为 source 或 capability 的自由文本片段。
- 旧式 `run-*` 运行标识不再作为有效新运行标识。

精确命名格式、合法枚举和校验要求以 Agent system design references 为准。

## 7. 目录管理

`specs/` 目录分为长期维护内容和运行产物：

- `specs/templates/`: 长期维护的模板和固定流程样例，允许人工审阅和版本管理。
- `specs/runs/`: Runtime 运行输出目录，只保存当次运行的 `spec.yaml`、trace、summary 和 artifacts，不作为长期知识库维护。
- 测试 fixture 预留位置：后续需要保留的测试样例应迁移到 `tests/fixtures/specs/`，而不是放在 `specs/runs/`。

旧的 `specs/runs/*` 历史记录视为测试运行产物，可以清理。真实业务知识应进入模板、契约、Skill 文档、代码枚举或 confirmed memory，而不是依赖历史 run 目录沉淀。

## 8. 模块职责

当前实现职责如下：

- `src/yield_report/agent/spec_builder.py`: Spec 构建门面，负责默认路径与固定流程规则构建的分流。
- `src/yield_report/agent/spec_graph/`: LangGraph Spec sub-agent，负责 state、节点、条件边、图装配、可选 checkpointer 和 `LangGraphSpecAgent` facade。
- `src/yield_report/agent/langgraph_spec_agent.py`: 兼容导入层，保留旧路径但不承载实现。
- `src/yield_report/agent/run_id.py`: `RunIdFactory` 和 source/capability 归一化校验。
- `src/yield_report/agent/spec_validation.py`: 统一 Spec 校验入口。
- `src/yield_report/agent/run_store.py`: 创建 run 目录并保存 Spec。
- `src/yield_report/agent/runtime.py`: 消费已生成 Spec，执行 workflow，写入 trace 和产物。

这些模块共同保证：Spec 构建属于 Agent Runtime 内部链路，Codex 只在开发阶段修改代码和文档，不在生产执行链路中生成 Spec 片段。

## 9. 失败与确认

Spec 构建失败不应被吞掉，也不应自动降级为不透明的旧逻辑。

失败处理原则：

- LLM draft 不合法时，进入 LangGraph repair。
- repair 超出次数后，Spec 状态为 `needs_confirmation`。
- 校验问题保留在结构化 `validation_issues` 中，供 UI、日志和后续人工确认使用。
- Runtime 只应执行 `ready` 且通过校验的 Spec。

这让 Spec 构建成为可观测、可修复、可确认的需求解析步骤，而不是一次不可追踪的 prompt 输出。
