---
name: yield-report-daily
description: Guides Codex through the Spec-driven OLED yield daily-report workflow in excel-generator-project. Use when generating, running, debugging, or updating yield daily-report TaskSpecs, traces, artifacts, or the report_download/data_analysis/daily_report Skill workflow.
---

# Yield Report Daily

## Quick Start

1. Read `AGENTS.md`, `ARCHITECTURE.md`, and `docs/agent/`.
2. Create or update a run spec:

```bash
uv run python scripts/create_daily_report_spec.py --goal "生成 M678 今天良率日报，重点分析 CT 良率趋势" --print-path
```

3. Execute the spec:

```bash
uv run python scripts/run_task_spec.py --spec specs/runs/<run_id>/spec.yaml
```

4. Inspect `specs/runs/<run_id>/trace.jsonl`, `run_summary.json`, `memory_candidates.json`, and `outputs/`.
5. Fix the smallest failing backend layer and rerun focused tests.

## Workflow Rules

- Treat `specs/runs/<run_id>/spec.yaml` as the task contract.
- Keep runtime files inside `specs/runs/<run_id>/`.
- Use Python Skills for stable work:
  `report_download`, `data_analysis`, and `daily_report`.
- Keep `application/`, `core/`, and `infrastructure/` as compatible implementation layers.
- Do not introduce LangChain, LangGraph, or a generic agent framework.
- Do not modify Streamlit UI during backend-only phases.

## Failure Handling

- If a skill fails, read the failed trace event first.
- If the request is malformed, update the Spec or `SpecBuilder`.
- If a skill input is valid but execution fails, fix the target Python Skill or its compatible implementation.
- If the run produces memory updates, leave them as pending candidates unless the user explicitly confirms them.

## Examples

Natural-language goal:

```text
生成 M678 今天良率日报，重点分析 CT 良率趋势和异常。
```

Expected flow:

```text
SpecBuilder -> specs/runs/<run_id>/spec.yaml
AgentRuntime -> data_analysis -> daily_report
TraceWriter -> specs/runs/<run_id>/trace.jsonl
RunStore -> run_summary.json / memory_candidates.json / outputs/
```
