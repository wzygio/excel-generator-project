# Coding Conventions

- Add `from __future__ import annotations` to new Python modules.
- Use type annotations for new functions and methods.
- Update Pydantic config models before changing configuration files.
- Keep Core logic mostly pure; browser, Excel, filesystem, and network IO belong in infrastructure or adapters.
- Use the shared LLM manager for LLM calls; do not instantiate provider clients in business code.
- Keep existing public entrypoints compatible unless the user explicitly asks for a breaking refactor.
- Add dependencies only through project dependency files and explain why existing dependencies are insufficient.
- Prefer focused tests for parser, selector, Skill contract, file naming, logging, and download behavior.

## Runtime Output Paths

Runtime产物必须写入 `output/` 下的稳定类别目录，不要新增业务名顶层目录。业务名、Skill名、workflow名只能作为稳定类别下的子目录或文件名前缀。

| File Type | Write Path | Notes |
|---|---|---|
| Generated final business reports | `output/artifacts/reports/generated/` | Runtime生成的最终业务报告。 |
| Source report copies | `output/artifacts/reports/source/` | 下载后用于复现的源报表副本。 |
| Upload-ready workbooks | `output/artifacts/reports/upload_ready/` | 可提交给业务系统或用户的填报件。 |
| Decrypted workbooks | `output/artifacts/workbooks/decrypted/` | 替代旧顶层 `output/decrypted_files/`。 |
| Normalized workbooks | `output/artifacts/workbooks/normalized/` | 格式标准化、schema对齐后的Excel。 |
| Intermediate workbooks | `output/artifacts/workbooks/intermediate/` | 多步骤任务中的中间Excel。 |
| Extracted structured data | `output/artifacts/data/extracted/` | 从Excel、网页或API抽取的JSON/CSV/Parquet。 |
| Transformed data | `output/artifacts/data/transformed/` | 聚合、筛选、分析后的中间数据。 |
| Data validation reports | `output/artifacts/data/validation/` | schema、字段、行数、业务校验结果。 |
| User download copies | `output/artifacts/exports/user_downloads/` | UI/API实际交付给用户的下载副本。 |
| FineReport raw downloads | `output/downloads/raw/finereport/` | 替代旧顶层 `output/rpa_downloads/`。 |
| Browser raw downloads | `output/downloads/raw/browser/` | Playwright或浏览器下载文件。 |
| API raw downloads | `output/downloads/raw/api/` | API抓取或下载的原始文件。 |
| Staged downloads | `output/downloads/staged/` | 下载完成后等待识别或校验的暂存文件。 |
| Failed downloads | `output/downloads/failed/` | 不完整、损坏或失败下载。 |
| Run observations | `output/observations/runs/` | Agent Verify阶段优先读取的run级简洁摘要。 |
| Skill observations | `output/observations/skills/` | Skill输入/输出摘要与契约检查摘要。 |
| Smoke observations | `output/observations/smoke/` | smoke结果摘要。 |
| Observation summaries | `output/observations/summaries/` | 跨产物的compact observation。 |
| Runtime traces | `output/traces/runtime/` | Runtime调度、状态、生命周期轨迹。 |
| Agent traces | `output/traces/agent/` | Agent消息、工具调用摘要轨迹。 |
| Tool traces | `output/traces/tools/` | 工具调用参数和结果摘要。 |
| Browser traces | `output/traces/browser/` | Playwright/browser trace。 |
| Application logs | `output/logs/application/` | 应用层日志。 |
| Agent logs | `output/logs/agent/` | Agent Runtime日志。 |
| Runtime logs | `output/logs/runtime/` | Runtime worker、queue、run-store日志；替代模糊的 `output/logs/core/`。 |
| Skill logs | `output/logs/skills/` | Skill内部日志。 |
| Infrastructure logs | `output/logs/infrastructure/` | Excel、filesystem、config、dependency等基础设施日志。 |
| External-system logs | `output/logs/external/` | 门户/API调用摘要；不得包含secrets、cookies、tokens。 |
| RPA logs | `output/logs/rpa/` | RPA步骤和selector日志。 |
| RPA diagnostics | `output/diagnostics/rpa/` | 替代旧顶层 `output/rpa_debug/`，存放截图、HTML、console、失败文本。 |
| Browser diagnostics | `output/diagnostics/browser/` | e2e/browser截图、视频、trace。 |
| Excel diagnostics | `output/diagnostics/excel/` | COM、文件锁、格式问题诊断。 |
| Network diagnostics | `output/diagnostics/network/` | HAR、响应快照；必须脱敏。 |
| Failure bundles | `output/diagnostics/failures/` | 失败收敛包和triage notes。 |
| Unit smoke artifacts | `output/smoke/unit/` | 单元级smoke产物。 |
| Integration smoke artifacts | `output/smoke/integration/` | API/service集成smoke产物。 |
| E2E smoke artifacts | `output/smoke/e2e/` | UI/E2E截图、下载件和摘要。 |
| Business smoke artifacts | `output/smoke/business/` | 业务场景smoke；替代旧顶层 `output/task2_smoke/`。 |
| Runtime audits | `output/audits/runtime/` | tool allowlist、artifact manifest、runtime audit。 |
| Quality audits | `output/audits/quality/` | pytest/ruff/pyright/harness check摘要。 |
| Security audits | `output/audits/security/` | path allowlist、secret scan、安全边界摘要。 |
| Runtime metrics | `output/metrics/runtime/` | run耗时、队列、工具耗时等指标。 |
| Performance metrics | `output/metrics/performance/` | benchmark和性能测试结果。 |
| Quality metrics | `output/metrics/quality/` | coverage、通过率、趋势指标。 |
| Regenerable cache | `output/cache/` | runtime、LLM、browser等可再生成缓存。 |
| Temporary scratch files | `output/tmp/` | 可随时清理的临时文件。 |

When a new runtime artifact does not fit this table, update the enterprise output architecture first: `D:\wzy\Visionox-Docs_Backup\dev-docs\dev-system_arch\runtime-output-architecture.md`.
