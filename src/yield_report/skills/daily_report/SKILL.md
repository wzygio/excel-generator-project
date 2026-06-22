# daily_report

## When To Use
Use this skill when Codex or Agent Runtime needs to run the full OLED daily-report workbook workflow.

This skill is now a thin Python adapter around the Task0-Task4 orchestrator:

1. `basic-preparation`
2. `task1-gap-analysis`
3. `task2-extract-anomalies`
4. `task3-batch-month-analysis`
5. `task4-daily-report-generation`

Do not duplicate the child skills' business rules here.

## Inputs
- `report_date`: Report date.
- `spec_path`: Optional YAML spec path. Local file aliases can be read from `inputs.local_files`.
- `template_ref`: Optional Excel template path.
- `product_models`: Optional product filter. If omitted, all shipped products from `spotfire` are used.
- `source_files`: Optional alias-to-path mapping. Supported aliases are `spotfire`, `daily_yield`, `target_decomposition`, `gap_template`, `ct_exception`, and `code_mapping`.
- `output_dir`: Optional output directory.
- `sections`: Sections to write.
- `analysis_results`: Upstream data-analysis results.
- `output_name`: Optional output file name.
- `emit_intermediate_artifacts`: Whether to emit JSON and Markdown sidecar artifacts.
- `use_llm_polishing`: Whether to ask LLMManager to polish deterministic report text. Defaults to false.
- `orchestrator_workspace`: Optional external duty-workflow root. Defaults to `D:\wzy\工作-值班工作\相关文件`.
- `orchestrator_now`: Optional deterministic run time, for example `2026-06-15 16:00`.
- `download_sources`: Whether Task0 should download fresh FineReport sources before writing.
- `reference_workbook`: Optional target workbook used for value-level comparison.

## Outputs
- Excel artifact: the generated daily report workbook.
- `data.workflow`: child skills executed in order.
- `data.steps`: child script command results.
- `data.verification`: Data Packet and Sheet1 row counts, nonblank counts, and HTML style checks.
- `data.comparison`: optional generated-vs-reference workbook comparison.

## Workflow
1. Resolve the external orchestrator workspace and output workbook path.
2. Run `scripts/task0_report_download.py --write --output <workbook>`.
3. Run `scripts/task1_overstock_impact.py --write <workbook>`.
4. Run `scripts/task2_extract_anomalies.py --source <workbook> --write`.
5. Run `scripts/task3_batch_month_analysis.py --source <workbook> --write`.
6. Run `scripts/task4_daily_report_generation.py --source <workbook> --write`.
7. Verify the final workbook contains `Data Packet` and `Sheet1`/`sheet1` and report nonblank counts.
8. If `reference_workbook` is provided, compare Data Packet and upload sheet cell values.

## Error Handling
- `daily_report.orchestrator.failed`: child script, workbook verification, or filesystem failure.
- `daily_report.reference_mismatch`: generated workbook differs from `reference_workbook`.
