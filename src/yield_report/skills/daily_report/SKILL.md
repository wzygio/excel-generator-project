# daily_report

## When To Use
Use this skill when Codex needs to generate the final Excel yield daily report from a daily-report spec or from structured source-file inputs.

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

## Outputs
- Excel artifact: the generated daily report.
- JSON artifact: structured product-level facts used for the report.
- Markdown artifact: human-readable report preview.
- `data.products`: product rows, Gap TopN, trend result, known exceptions, new exceptions, and final report text.
- `warnings`: missing optional source files or fallback decisions.

## Workflow
1. Resolve report date, source files, and template.
2. Read `spotfire` to identify shipped products.
3. For each product, compute positive Defect Group Gap Top3 from the CT sheet and target table.
4. Check latest-three-day CT yield decline and MVI share increase.
5. Match known exceptions in the last 30 days and new exceptions on the report date.
6. Compose deterministic report text, optionally polish through `LLMManager`.
7. Write `sheet1` from row 4, preserving the header row.

## Error Handling
- `daily_report.file.missing_required`: Required source file cannot be found.
- `daily_report.file.missing_sheet`: Required worksheet is missing.
- `daily_report.spotfire.missing_header`: `spotfire` does not contain the expected product headers.
- `daily_report.data.no_products`: No shipped products matched the request.
- `daily_report.execution.failed`: Unexpected generation failure.
