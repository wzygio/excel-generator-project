# daily_report

## When To Use
Use this skill when Codex or Agent Runtime needs to run the full OLED daily-report workbook workflow.

This skill is a thin Python adapter around the user-facing `$task0-task4-orchestrator` CLI. It does not call or expose per-step wrapper skills directly.

Do not duplicate the orchestrator's business rules here.

## Inputs
- `report_date`: Report date.
- `spec_path`: Optional YAML spec path. Local file aliases can be read from `inputs.local_files`.
- `template_ref`: Optional Excel template path.
- `product_models`: Optional product filter. If omitted, all shipped products from `spotfire` are used.
- `source_files`: Optional alias-to-path mapping. For the native runtime, supported orchestration aliases are `orchestrator_workspace`, `orchestrator_root`, and `task0_task4_orchestrator_root`; legacy data aliases are still accepted by helper tests.
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
- `data.runtime`: `task0-task4-orchestrator`.
- `data.workflow`: orchestrator task ids executed in order.
- `data.native_result`: raw JSON returned by the external orchestrator CLI.

## Workflow
1. Resolve the external orchestrator workspace and `$task0-task4-orchestrator` root.
2. Run `C:\Users\V0141351\.agents\skills\task0-task4-orchestrator\scripts\daily_report_cli.py run --mode write`.
3. Parse the orchestrator JSON result.
4. Return the generated workbook as the Excel artifact.

## Error Handling
- `daily_report.native_pipeline.failed`: orchestrator CLI, workbook generation, JSON parsing, or filesystem failure.
