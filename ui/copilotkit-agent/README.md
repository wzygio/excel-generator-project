# CopilotKit Agent UI

这是良率日报项目的 CopilotKit Agent 工作台，复用原项目的 Python Skill 能力。

## 入口

- 页面源码: `app/page.tsx`
- CopilotKit Runtime: `app/api/copilotkit/route.ts`
- Agent Run API: `app/api/agent-runs/route.ts`
- 产物下载 API: `app/api/artifact/route.ts`
- Python bridge: `../../scripts/agent_workbench_bridge.py`

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

当前 UI 通过 `/api/agent-runs` 创建并执行 `specs/runs/<run_id>/spec.yaml`。后端由 `RunStore` 收敛 `trace.jsonl`、`run_summary.json`、`memory_candidates.json` 和 `outputs/`，并通过 RuntimeRouter 调用 Python Skills 或 Pi/OMP Runtime。
