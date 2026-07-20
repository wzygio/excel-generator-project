# Letta Runtime 功能完善与能力矩阵

生成日期：2026-06-22

参考文档：

- `D:\wzy\Visionox-Docs_Backup\dev-docs\agent_dev\letta_agent_runtime_migration_guide_2026-06-22.md`
- Letta Memory Blocks: https://docs.letta.com/guides/core-concepts/memory/memory-blocks/
- Letta Archival Memory: https://docs.letta.com/guides/core-concepts/memory/archival-memory/
- Letta Client Tools: https://docs.letta.com/guides/core-concepts/tools/client-tools/
- Letta Compaction: https://docs.letta.com/guides/core-concepts/messages/compaction/
- Letta Conversations: https://docs.letta.com/guides/core-concepts/messages/conversations/
- Letta Long-running Executions: https://docs.letta.com/guides/core-concepts/messages/long-running-executions/
- Letta Folders API: https://docs.letta.com/api/resources/folders
- Letta Run Trace API: https://docs.letta.com/api/resources/runs/subresources/trace/

## 结论

使用 Letta Cloud 后，Agent 的持久化消息、memory blocks、archival memory、conversations、compaction、streaming/background run 等底层能力由云端提供，但项目 Runtime 仍然需要配置管理和适配逻辑。

原因是 Letta Cloud 不会自动知道本项目的 TaskSpec、Python Skills、Excel/内网/RPA 边界、artifact 路径、run_id 映射、memory 写入策略和本地 trace 规范。Cloud 提供状态型 Agent 服务；项目 Runtime 负责把业务 Agent 契约接到这些 Letta 原语上。

本轮已基于 Letta 机制补齐可安全落地的能力：memory blocks 同步、archival memory 写入、per-run conversation、compaction settings、streaming/background 参数、client tool loop、run_summary 映射和 Cloud smoke 验证。`权限与审计`按本次任务要求未纳入评估。

## 能力矩阵

| 能力项 | Letta Cloud 是否自带原语 | 当前 Runtime 状态 | 本轮处理 |
|---|---:|---|---|
| 长期 Memory | 是：memory blocks、archival memory、persistent messages | 已具备 | 创建/同步 `persona`、`runtime_policy`、`domain_contract`、`current_task`、`memory_digest`；将 `SkillResult.memory_updates` 写入 passages |
| Tool / Skill Registry | 是：server tools、client tools、MCP tools | 已具备当前业务最小集 | 继续使用 Letta client tools 暴露本地 `report_download`、`data_analysis`、`daily_report` |
| ReAct / Tool-call Loop | 是：messages + approval request + tool return | 已具备 | 保留 client-side tool loop，增加 `max_steps` 传参，继续限制 `max_tool_rounds` |
| Context Compression / Compaction | 是：`compaction_settings` | 已具备 | Agent 创建与更新时显式配置 `mode=sliding_window`、`clip_chars=50000`、自定义 prompt |
| Session 管理 | 是：Agent、conversation、run、step | 已具备 | 每个 TaskSpec run 建立/复用 conversation，并在 run_summary 中记录 `letta_conversation_id`、`letta_run_id` |
| 用户 / 任务状态 | 部分自带：memory blocks、identities、metadata、tags | 任务状态已具备；用户身份状态暂不启用 | `current_task` block 每次运行刷新；未写入共享 `human` block，避免多用户偏好混写 |
| 文件和数据库工具 | 是：folders/files/passages；也支持 client tools | 本地敏感文件路径已具备；Cloud 文件上传未默认启用 | Excel、FineReport、内网/本地文件仍通过 client tools 留在本地执行；未把企业文件上传 Letta Cloud |
| API / 服务化能力 | 是：Python SDK、REST、streaming、background runs | 已具备基础服务化参数 | Runtime 配置新增 `streaming`、`stream_tokens`、`background_runs`；默认 `streaming=true`、`background_runs=false` |
| 可插拔业务工具 | 是：client tools / server tools / MCP | 已具备当前白名单工具；动态 registry 待后续重构 | 本轮不新增自研 registry，仅使用现有 Letta client tools 机制 |
| Adapter 接口 | 由项目实现，Letta 提供 API | 已具备核心接口 | `build/load agent`、`build/load conversation`、`sync_memory_blocks`、`send TaskSpec`、`handle tools`、`write trace/run_summary` 已接线 |

## 本轮代码改动

- `src/yield_report/agent/letta_runtime.py`
  - 新增 Letta memory blocks 初始创建与缓存 Agent 的 blocks 同步。
  - 新增 per-run conversation 创建与本地 cache。
  - 新增 Letta compaction settings 创建/更新。
  - 新增 archival memory 写入，将 `memory_updates` 保存到 `client.agents.passages.create(...)`。
  - 新增 streaming/background/max_steps 请求参数，并兼容 stream response。
  - run summary 新增 `letta_conversation_id`、`letta_run_id`、`letta_archival_memory_count`。
- `src/yield_report/agent/runtime_adapter.py`
  - 将全局 Letta 配置透传到 `LettaRuntimeConfig`。
- `src/shared_kernel/config_model.py`
  - 新增 Letta memory、conversation、compaction、streaming/background 配置字段。
- `config/global.yaml`
  - 新增上述 Letta Runtime 默认配置。
- `tests/unit/agent/test_letta_runtime.py`
  - 增加 Agent 创建 blocks、缓存 Agent blocks 同步、conversation mapping、archival memory、streaming/max_steps 的测试覆盖。
- `tests/unit/test_config_loader.py`
  - 增加 Letta Runtime 配置模型字段验证。

## 当前配置

```yaml
agent:
  letta:
    model: "my-glm-key/glm-5.1"
    embedding: "my-glm-key/text-embedding-3-large"
    sync_memory_blocks: true
    archive_memory_candidates: true
    use_conversations: true
    compaction_mode: "sliding_window"
    compaction_clip_chars: 50000
    streaming: true
    stream_tokens: false
    background_runs: false
```

## 未默认启用项

1. `human` block / identities：需要项目先明确用户身份模型。当前最多三人使用，但如果共享同一个 Agent，将用户偏好写入共享 block 有混写风险。
2. Letta folders/files：Cloud 支持，但本项目涉及企业 Excel、内网路径、加密文件和 RPA 会话，默认不上传到 Cloud。安全做法仍是 client tools 本地读取，Letta 只接收摘要和 artifact reference。
3. background run 恢复：参数已可配置，默认关闭。真正的断线恢复还需要 UI/workbench 保存 `run_id`、`seq_id` 并接 `client.runs.stream(...)`。
4. 动态业务工具 registry：当前已有三个白名单 client tools，足够覆盖现有 yield workflow。后续若 Skill 数量继续增长，再把 `PROJECT_CLIENT_TOOLS` 改成从项目 Skill registry 生成。

## 验证记录

- `uv run pytest tests/unit/agent/test_letta_runtime.py tests/unit/test_config_loader.py::TestAppConfigModel::test_agent_letta_config -v --tb=short`
  - 结果：19 passed
- `uv run ruff check src/yield_report/agent/letta_runtime.py src/yield_report/agent/runtime_adapter.py src/shared_kernel/config_model.py tests/unit/agent/test_letta_runtime.py tests/unit/test_config_loader.py`
  - 结果：All checks passed
- `uv run pyright src/yield_report/agent/letta_runtime.py src/yield_report/agent/runtime_adapter.py src/shared_kernel/config_model.py tests/unit/agent/test_letta_runtime.py tests/unit/test_config_loader.py`
  - 结果：0 errors, 0 warnings
- `uv run pytest tests/unit/agent tests/unit/skills tests/unit/test_config_loader.py::TestAppConfigModel::test_agent_letta_config -v --tb=short`
  - 结果：73 passed
- Letta Cloud smoke：
  - 结果：`status=ok`
  - 已确认真实 Cloud Agent 可同步 `persona`、`runtime_policy`、`domain_contract`、`current_task`、`memory_digest`
  - 已确认 conversation 可创建/缓存
  - 已确认 `current_task` 包含本次 smoke run_id

## 建议

当前 Runtime 已具备迁移指南中除 `权限与审计`以外、且适合本项目现阶段启用的 Letta 能力。下一步不建议继续加自研记忆系统；应先让业务流量通过 Letta Runtime 跑真实 TaskSpec，再观察 memory candidates、tool failures 和 run_summary 的质量。

如果后续要继续增强，优先顺序建议为：

1. UI/workbench 接入 streaming event 与 background run resume。
2. 将 `PROJECT_CLIENT_TOOLS` 改为从 Skill registry 生成，但仍保持白名单和参数 schema 校验。
3. 在明确用户身份模型后，再引入 `human` block 或 Letta identities。
4. 仅在有脱敏知识库或明确上传授权时，启用 Letta folders/files。
