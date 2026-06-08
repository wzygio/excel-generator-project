# Refactor Agent Architecture Prompt

This repository keeps the full execution brief in:

```text
docs/design/refactor-excel_generator_agent_architecture.md
```

When a task references `docs/prompt/refactor-agent_architecture.md`, use that design document as the canonical source and keep these constraints:

- Keep the existing `application/`, `core/`, and `infrastructure/` modules.
- Keep the three Python Skills: `report_download`, `data_analysis`, and `daily_report`.
- Do not introduce LangChain or LangGraph.
- Add and use `RunStore`, `SpecBuilder`, `scripts/create_daily_report_spec.py`, and `scripts/run_task_spec.py`.
- Keep run-state files under `specs/runs/<run_id>/`: `spec.yaml`, `trace.jsonl`, `memory_candidates.json`, `run_summary.json`, and `outputs/`.
- For this backend-only phase, do not change `app/main.py`.
