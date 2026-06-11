# Agent Runtime 展开重构计划

## 1. 审查结论

Task4 提出的目标是正确的：日报生成应能向下拆解为数据分析，数据分析应能向下拆解为报表下载。

当前 HEAD 的状态：

- `report_download` 已包装旧数据获取流程。
- `data_analysis` 已能消费上游下载产物，但旧文件解析器仍有隐藏式下载能力。
- `daily_report` 仍是稳定接口占位，没有真正消费 `analysis_results`。
- Runtime 原本只线性执行 workflow，不会根据 Skill 反馈展开下游调用。

本轮选择“契约闭环”作为第一步，不复制主工作区未提交的日报生成实现，也不做 daily_report 全量深拆。

## 2. 本轮改造

- 新增共享反馈模型：
  `RequiredSkillCall`、`RequiredAction`、`AnalysisFactRef`、`ArtifactManifest`。
- 新增 `SpecCompiler`：
  把 `inputs.analysis_requirements` 和 `inputs.reports` 展开为 `report_download -> data_analysis -> daily_report` workflow。
- 改造 `AgentRuntime`：
  当 Skill 返回 `required_actions` 时，执行下游 Skill，并使用 `input_updates` 重试被阻塞的原步骤。
- 改造 `daily_report`：
  优先消费 `analysis_results` / `analysis_facts`；缺少 CT 趋势事实时返回 `RequiredAction(data_analysis)`。
- 改造 `data_analysis`：
  没有 `file_path`、`file_name` 或有效 `report_refs` 时，返回 `RequiredAction(report_download)`。
- 改造 `report_download`：
  返回 `ArtifactManifest`，让下游可以识别源表 alias、路径和筛选信息。
- 更新 `daily_report_spec.yaml`：
  用 `analysis_requirements` 表达日报需要的事实，由 SpecCompiler 展开执行顺序。

## 3. 验收标准

- `daily_report` 缺少 CT 趋势事实时，不直接失败为不可恢复错误，而是返回结构化 `required_actions`。
- `data_analysis` 缺少源表引用时，返回结构化 `required_actions` 请求 `report_download`。
- Runtime 能执行 required action 并重试原步骤。
- SpecCompiler 能把声明式日报需求展开为下载、分析、生成三段 workflow。
- 现有 `report_download` 和 `data_analysis` 成功/失败路径测试继续通过。

## 4. 测试命令

```bash
uv run pytest tests/unit/agent tests/unit/skills -v --tb=short
uv run pytest tests/unit/test_analysis_file_resolver.py tests/unit/test_analysis_orchestrator.py tests/unit/skills/test_report_download_skill.py tests/unit/skills/test_data_analysis_skill.py tests/unit/skills/test_daily_report_skill.py -v --tb=short
```

## 5. 后续阶段

- 将旧 `AnalysisFileResolver` 的隐藏式下载逐步改为显式 required action。
- 在 `daily_report` V2 实现接入后，把 Gap、趋势、异常事实统一表达为 `AnalysisFactRef`。
- UI 日报 tab 后续应走 `AgentRuntime`，而不是直接调用 `daily_report_tool.run()`。
- confirmed memory 写入仍必须经过用户确认，Skill 只返回 pending 候选。
