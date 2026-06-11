## 14. 给 Codex 的完整执行 Prompt

把下面这段直接发给 Codex：

```text
你现在在 excel-generator-project 仓库中工作。

目标：按照 docs/prompt/refactor-agent_architecture.md，把项目从三 Tab 工具式 UI，重构为 Spec 驱动的良率日报 Agent Workbench。

请严格遵守：
1. 先读 AGENTS.md；如果不存在，读取 .roorules，并新增 AGENTS.md。
2. 读取 ARCHITECTURE.md、docs/agent/architecture.md、docs/agent/spec_contract.md、docs/agent/skill_contract.md、docs/design/yield_report_domain.md。
3. 不要推倒重来，不要删除旧 application/core/infrastructure。
4. 保留 report_download、data_analysis、daily_report 三个 Python Skill。
5. 不引入 LangChain/LangGraph。
6. 新增 .agents/skills/yield-report-daily/SKILL.md。
7. 新增 RunStore、SpecBuilder、create_daily_report_spec.py、run_task_spec.py。
8. 修改 Runtime，使 trace/output/memory_candidates 收敛到 specs/runs/<run_id>/。
9. 只修改后端，暂时不要修改前端。
10. 每个阶段补最小测试，并运行相关测试。

请按小步提交思路工作：
- 先列出你读到的当前结构和准备修改的文件。
- 再实现 Task A-F。
- 每完成一个阶段运行 focused tests。
- 不断调试直到可以支持数据分析任务的完成。
- 给出变更摘要、测试结果和未完成风险。
```