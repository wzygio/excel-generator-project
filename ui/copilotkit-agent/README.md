# CopilotKit Agent UI

这是良率日报项目的 CopilotKit Agent 工作台，复用原项目的 Python Skill 能力。

## 入口

- 页面源码: `app/page.tsx`
- CopilotKit Runtime: `app/api/copilotkit/route.ts`
- Python Skill API: `app/api/yield-skill/route.ts`
- 产物下载 API: `app/api/artifact/route.ts`
- Python bridge: `../../scripts/copilotkit_skill_bridge.py`

## 运行

```powershell
npm ci
npm run dev
```

可选环境变量:

```powershell
$env:YIELD_REPORT_WORKSPACE="D:\wzy\Python\excel-generator-project"
$env:COPILOTKIT_MODEL="openai:gpt-5.4-mini"
```

## 验证

```powershell
npm run typecheck
npm run build
```

当前 UI 通过 `/api/yield-skill` 调用现有 `report_download`、`data_analysis`、`daily_report` 三个 Skill。日报下载链接来自 SkillResult 的 artifacts，并由 `/api/artifact` 校验路径后返回。
