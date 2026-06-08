# 知识归纳与验收流程（Code 模式）

> 目的：每次实现后，把验证结果、架构影响和可复用经验收束清楚，避免临时修复游离在 Harness 之外。

## 1. 完成前检查

按变更风险选择验证层级：

| 变更类型 | 必跑验证 |
|----------|----------|
| 纯文档 / Harness | 检查 diff 与路径引用；不需要跑 pytest |
| Core / parser / selector / business_time | `uv run pytest tests/unit/ -v --tb=short` 或更窄相关单测 |
| Agent / Skill / Spec | `uv run pytest tests/unit/agent tests/unit/skills -v --tb=short` |
| FineReport / 下载 / 文件解析 | 相关 unit 测试；必要时补浏览器或 RPA smoke |
| Streamlit 可见 UI | 后端测试之外，必须做真实浏览器/UI smoke |
| 配置 / 类型 / 依赖 | `uv run pyright`、`uv run ruff check .`，并检查 `pyproject.toml` |

当前仓库没有稳定的 `tests/integration/` 目录；不要把它作为固定必跑项。若新增集成测试，再同步更新本文件和 `.roorules`。

## 2. 架构变更检测

实现后检查是否涉及以下内容：

| 检测项 | 需要同步的文档 |
|--------|----------------|
| Agent Runtime、Router、Trace、Memory 变化 | `ARCHITECTURE.md`、`docs/agent/architecture.md` |
| Skill request/result/error/artifact 契约变化 | `docs/agent/skill_contract.md`、对应 `src/yield_report/skills/*/SKILL.md` |
| Spec 字段、workflow、runs 结构变化 | `docs/agent/spec_contract.md`、`specs/templates/*.yaml` |
| 报表下载、数据分析、日报生成边界变化 | `docs/design/yield_report_domain.md` |
| 配置模型、LLM、日志体系变化 | `docs/design/shared_kernel.md` |
| 开发纪律、红线或命令变化 | `.roorules`、`.roo/rules-*/*.md`、`docs/design/development_framework.md` |

如果只是局部 bugfix 且契约、目录、数据流不变，明确说明“无架构文档需同步”。

## 3. 新解决方案检测

遇到可复用方案时，优先沉淀到合适位置：

| 方案类型 | 沉淀位置 |
|----------|----------|
| 项目内专项经验 | `docs/prompt/skill-*.md` |
| Agent/Skill/Spec 契约经验 | `docs/agent/*.md` |
| 可执行且跨项目复用的流程 | Codex 全局 skill，必要时附脚本和 `agents/openai.yaml` |
| 仅一次性诊断脚本 | 不留在仓库根目录；若必须保留，放 `scripts/` 并说明用途 |

不要因为一次偶发问题就创建新 skill；只有确定性、重复性、值得固化的流程才脚本化或 skill 化。

## 4. 收尾输出

最终回复必须包含：

- 改了哪些 Harness / 代码 / 文档。
- 跑了哪些验证；没跑的说明原因。
- 是否有架构或新方案需要继续沉淀。
- 若有运行产物或忽略文件状态异常，指出但不要擅自清理无关文件。

## 5. 用户决策后的操作

| 用户反馈 | 操作 |
|----------|------|
| 采纳 | 合并到对应正式文档或 skill |
| 拒绝 | 删除临时提案或保持现状 |
| 修改后采纳 | 先按反馈更新，再合并 |

原则：提案和正式文档分开；未经用户许可不把临时计划当作长期架构事实。
