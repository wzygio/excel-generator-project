# 计划：Harness Builder Skill

## 目标

构建一条 Codex 全局 skill，用于在新项目中创建轻量 Harness 骨架，并在已有项目中审计/修复 Harness 路由、知识系统、计划系统和验证入口。

## 当前判断

- `agents-md-generator` 已能生成 `AGENTS.md` / `.roorules`，但范围只覆盖 Agent 入口文件。
- 新需求需要更高一层：围绕 AGENTS、ARCHITECTURE、docs/design、docs/plans、docs/references、docs/generated 和机械约束建立项目 Harness。
- 该 skill 只构建“自行维护”和“Agent 维护”的项目文件；Codex 已有能力只通过命令、质量标准和反馈入口暴露，不重复实现。

## 实施步骤

1. 新建全局 skill：`C:\Users\V0141351\.codex\skills\harness-builder`。
2. 编写 `SKILL.md`：定义创建模式、修复模式、蓝图判断和验证要求。
3. 编写脚本 `scripts\build_harness.py`：
   - 扫描 manifest、入口文件、docs、tests、specs、已有 AGENTS/.roorules。
   - 默认输出 Harness audit 和建议，不写文件。
   - `--mode create` 创建缺失的轻量骨架。
   - `--mode repair` 补齐缺失索引和路由，不覆盖已有内容，除非显式 `--overwrite`。
4. 提供模板：
   - `assets\AGENTS.template.md`
   - `assets\ARCHITECTURE.template.md`
   - `assets\design-index.template.md`
   - `assets\plans-index.template.md`
5. 运行 skill 校验：
   - `quick_validate.py`
   - 脚本 dry-run 当前项目。
6. 新建临时 worktree，在其中应用 `harness-builder` 到当前项目。
7. 比较当前 Harness 与生成结果，说明优化原因和保留边界。

## 验证

- Skill 结构通过系统 `quick_validate.py`。
- 脚本 dry-run 能生成审计报告。
- 脚本写入模式拒绝覆盖已有关键文件。
- worktree 应用不会影响当前工作区未提交改动。

## 风险与边界

- 不自动覆盖人类维护的 `AGENTS.md`、`.roorules`、`ARCHITECTURE.md`。
- 不生成庞大的设计文档，只创建索引和轻量模板。
- 不尝试替代 Codex 自带代码审查、工作流或可观测能力，只暴露项目入口。
