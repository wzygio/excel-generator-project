# report_download

## When To Use
Use this skill when Codex needs to download or locate source reports for yield-report workflows.

## Inputs
- `user_query`: Optional natural-language download request.
- `report_type`: `daily_yield`, `batch_yield`, `ct_exception`, `target_decomposition`, or `gap_template`.
- `start_date` / `end_date`: Optional `YYYY-MM-DD` filters.
- `product_models`: Optional product model list. Use `[]` for all models.
- `filters`: Extra structured filters from a Spec.
- `prefer_decrypted`: Reserved for downstream workflows.

## Outputs
- Excel artifacts for successfully acquired files.
- `data.parsed_request`: the structured legacy request.
- `data.files`: one item per acquisition result.

## Workflow
1. If only `user_query` is provided, parse it with the existing query parser.
2. If structured fields are provided, build `ReportQueryRequest` directly.
3. Reuse `DataAcquisitionOrchestrator`.
4. Return unified `SkillResult`.

## Error Handling
- `report_download.execution.failed`: no requested file was acquired or a required acquisition failed.

## Examples
- "下载 M678 今天的月周天良率报表" -> `report_type=daily_yield`, `product_models=["M678"]`.
- "获取 2026-05-01 到 2026-06-01 的批次报表" -> `report_type=batch_yield`.
