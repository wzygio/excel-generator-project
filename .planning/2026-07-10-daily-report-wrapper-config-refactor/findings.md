# Findings & Decisions: Daily Report Wrapper and Configuration Refactor

## Requirements
- Understand the current Agent project before changing it.
- Verify that `src/yield_report/skills/daily_report/` is only a wrapper over `C:\Users\V0141351\.agents\skills\daily-report-generator`.
- Correct the local skill if it generates reports or owns business runtime logic itself.
- Inventory scattered hard-coded configuration, beginning with `V3CT修正良率及不良率By月周天报表`.
- Move public daily-report business values back behind the public skill boundary.
- Move unrelated but invalid hard-coded Agent configuration to the correct `yield_report` configuration/reference layer.
- Load configuration with Pydantic as required by the project coding conventions.
- Implement and verify the complete refactor, not only report recommendations.

## Research Findings
- `.codegraph/` does not exist in the current on-disk worktree, so the current turn must skip CodeGraph and use repository text/source inspection. Earlier plan notes came from pre-interruption state or a now-removed index.
- The public `daily-report-generator` skill documents `scripts/daily_report_cli.py` as the stable entry point.
- The public skill explicitly owns `configs/`, Mod0-Mod4 sequencing, command arguments, business-owned values, artifacts, workbook handoff, and final reporting.
- The project-local `daily_report` skill therefore should own only Agent-side request adaptation and process/result integration.
- The previously active file-based plan is complete and unrelated to this task.
- The project architecture defines the main chain as `TaskSpec -> Agent Runtime -> Skill Tool -> SkillResult -> Trace / Memory / Output` and favors explicit, testable, traceable workflows.
- The coding conventions require updating Pydantic configuration models before changing configuration files and preserving existing public entrypoints unless explicitly authorized.
- The first broad CodeGraph query surfaced a separate `data_analysis/daily_report_analysis.py` implementation containing substantial local report-analysis rules. It did not yet prove whether that module belongs to the requested `daily_report` wrapper path, so it must be traced rather than deleted by name similarity.
- CodeGraph identified an old `DailyReportGenerator`, but the authoritative on-disk `implementation.py` is already a 21-line thin wrapper. The index retains symbols that no longer exist.
- `src/yield_report/skills/daily_report/tool.py` preserves the Agent `SkillTool` contract and calls `execute_daily_report`, which only delegates to `native_pipeline.run_native_daily_report`.
- `execute_daily_report` currently delegates to `run_native_daily_report` in `native_pipeline.py`; it does not call `DailyReportGenerator` directly.
- CodeGraph's `execute_legacy_daily_report` and legacy test-call trails are also stale relative to the current on-disk implementation. Current text and tests, rather than those indexed symbols, must drive the final blast-radius check.
- `run_native_daily_report` is structurally a process adapter: normalize request, resolve public generator root/workspace/output, execute the generator CLI, and map its JSON result into `SkillResult`. This is the correct general shape for the wrapper.
- The local `daily_report/SKILL.md` already states the intended contract explicitly: it is a thin Python adapter around `$daily-report-generator` and must not duplicate generator business rules.
- `native_pipeline.py` currently hard-codes adapter defaults (`~/.agents/skills/daily-report-generator`, CLI relative path, output subdirectory, and environment-variable names) as module constants. These are Agent integration settings rather than report business rules, but they still need a typed configuration boundary under the user's Pydantic requirement.
- The local wrapper currently always passes `--workspace`, resolving it from the Agent `context.workspace` when no explicit generator workspace is supplied. This conflicts with the public skill contract, which says normal calls omit `--workspace` so the CLI uses its own repository root containing its configs/resources/.env.
- `_normalize_runner_request` converts every `report_date` into a hard-coded `16:00` `--now` value. The `16:00` date policy is business runtime logic and must not be invented by the wrapper; the public skill already owns date policy in `configs/shared.toml`.
- `_resolve_generator_root` overloads `request.source_files` with non-source magic keys (`daily_report_generator_root`, `generator_root`, `orchestrator_root`). `_resolve_workspace` and `_resolve_output_dir` do the same for workspace/output. This is weakly typed configuration leakage and directly contradicts the Pydantic guidance.
- The public architecture confirms that `configs/shared.toml` owns yield-mode mapping and both exact report names, including `V3CT修正良率及不良率By月周天报表`. Those literals therefore must not be duplicated in the local `daily_report` implementation.
- `DailyReportRequest` mixes the new wrapper inputs (`generator_workspace`, `generator_now`) with many legacy compatibility inputs. Maintaining those request fields may be necessary for TaskSpec compatibility, but they must not drive local business computation.
- The current request model has no explicit `generator_root`; tests and the adapter hide that override in `source_files`. Add a real typed `generator_root` field and stop interpreting non-source keys from `source_files`.
- Existing wrapper tests currently codify the boundary violations: they expect invalid generator workspaces to fall back to the Agent workspace, expect `report_date` to overwrite an explicit `generator_now` with `16:00`, and expect `--workspace` on every CLI call. These tests must be rewritten to enforce the public skill contract instead.
- Current text search confirms `DailyReportGenerator` and `execute_legacy_daily_report` do not exist anywhere under `src/` or `tests/`; no local generator engine removal is required.
- The public skill installation contains the documented stable CLI, its own `configs/*.toml`, contracts, orchestrator, mod adapters, templates, schemas, specs, and tests. It is visibly the correct owner for generation behavior and report-specific values.
- The public CLI confirms `--workspace` defaults to the public skill root and `--config` defaults to its own `configs/pipeline.toml`. It already accepts explicit `--now`, `--end-date`, `--output-dir`, `--snapshot-dir`, and `--yield-type` arguments; the wrapper does not need to reconstruct report rules.
- The project already has a Pydantic V2 configuration chain: `ConfigLoader` loads `config/global.yaml`, merges product YAML and environment overrides, then validates `AppConfig`. New Agent integration and report-source settings should extend this model rather than introduce a second loader.
- `config/global.yaml` is already the likely central home for report metadata, but current active code is not consistently consuming it. The config model and exact YAML schema must be inspected before moving literals.
- `config/global.yaml` already contains `source_files.daily_yield.description` and `.pattern`, but `AppConfig` has no `source_files` field and uses `extra="ignore"`. Pydantic therefore silently discards that entire YAML section today; it is configuration-shaped text without a validated or usable runtime contract.
- `AgentConfig` has natural room for a typed daily-report wrapper subsection. `AppConfig` can also add a typed `source_files` mapping whose entries include description, filename pattern, and default path.
- `PathsConfig.template_file` and `ReportConfig` still represent legacy project-owned generation settings. They are not needed by the public wrapper and should not be reused to configure the public Mod0-Mod4 business engine.
- `REPORT_TYPE_META` is shared by query parsing, analysis query parsing, and file resolution. Semantic descriptions can stay in code, but exact external report names should come from validated source configuration.
- `yield_download_service.py` groups other operational values beside report names (portal directory, UI labels, filename defaults, and timeout). These are Agent/FineReport adapter configuration and should be modeled together rather than moving only one string.
- There is no existing typed FineReport download settings model or YAML section for the portal directory, parameter labels, filenames, or wait timeout. A dedicated `report_download.finereport` Pydantic section is preferable to stuffing those values into generic path/report-generation config.
- FineReport construction is infrastructure-owned, while `application/orchestrator.py` only needs a configured external report display name for `AcquisitionResult`. Source-file metadata and FineReport UI settings should therefore be separate Pydantic models even though both live in `config/global.yaml`.
- `DataAcquisitionOrchestrator.__init__` currently accepts only LLM provider and clock. Configuration can be read through the existing `ConfigLoader` at construction time or injected as an optional typed object without changing its public default behavior.
- CodeGraph could not resolve the expected download-service class symbol, so its current class name/constructor must be taken from on-disk source after this graph-first attempt.
- The current class is `YieldDownloadService`. Its constructor already receives web-automation and credential dependencies, so adding one optional typed `FineReportDownloadConfig` is a clean injection point. Report names, directory, filenames, labels, browser timeout, and report-wait timeout can then become instance settings instead of module literals.
- `DataAcquisitionOrchestrator` lazily constructs `FinereportClient` and only needs typed source metadata for result labels; it does not need to understand portal UI settings.
- `FinereportClient` currently has a no-argument constructor and lazily creates the RPA service. It is the appropriate bridge for loading/injecting `report_download.finereport` settings before constructing `YieldDownloadService`.
- `SpecBuilder` already has several optional constructor dependencies and can accept optional typed source configuration (or an `AppConfig`) without breaking default callers. This is cleaner than freezing YAML-derived paths in module constants.
- `SpecBuilder._build_workflow` still emits a large legacy `daily_report` request (`template_ref`, product models, source files, sections, analysis results, output name, download/inspection flags, and task timeout). The public CLI wrapper does not consume these as generation inputs. New fixed-flow specs should call the wrapper with only public CLI-compatible inputs such as `report_date`; legacy request fields can remain accepted by the Pydantic model for old specs.
- `SpecBuilder._build_inputs` separately records report aliases and local file paths for traceability. Those paths can stay in TaskSpec inputs, but must be built from typed `source_files` configuration rather than module constants and must not be forwarded to the generator wrapper.
- `LOCAL_SOURCE_FILES` is used in three SpecBuilder paths, not only the final daily-report SkillCall. Refactor it into instance data derived from Pydantic config so anomaly/data-analysis/report-download specs keep their current traceable inputs.
- Existing `test_yield_download_service.py` imports the hard-coded constants directly. Tests should instead build a `FineReportDownloadConfig` plus source catalog and assert that the service uses injected values; preserving exported constants would defeat the configuration boundary.
- SpecBuilder tests cover both LLM-produced arbitrary TaskSpecs and the fixed rule builder. Keep the Pydantic runtime compatible with legacy LLM/spec fields, but change only newly generated fixed-flow `daily_report` inputs to the minimal wrapper contract.
- `FinereportClient._get_rpa_service` also hard-codes browser timeout/headless/slow-motion/channel. These are FineReport adapter settings and can be included in the same typed download config while credentials remain secret environment values.
- `FinereportClient` already imports `ConfigLoader` for output/resource paths. Extending that existing typed configuration dependency is preferable to introducing a new loader. FineReport credentials must remain in environment variables and must not be copied into YAML.
- Current-source confirmation after resume: `native_pipeline.py` always emits `--workspace`, overwrites an explicit `generator_now` whenever `report_date` is present, and resolves generator/workspace/output overrides from `source_files` magic keys. These are concrete wrapper defects, not only stale documentation.
- Current `daily_report/SKILL.md` documents those same magic aliases and the Agent repo default workspace, so the local skill contract must be corrected together with code and tests.
- The active example literal is absent from `daily_report/native_pipeline.py` but remains duplicated in Agent/spec, query/parser, acquisition/orchestrator, FineReport infrastructure, and `config/global.yaml`. This confirms two separate changes: clean the wrapper boundary and centralize Agent-owned acquisition/source metadata.
- Root `ARCHITECTURE.md` is otherwise consistent with an Agent facade, but its final Daily Report boundary sentence incorrectly says the Agent repo is the default run root.
- The existing validated configuration implementation is under `src/shared_kernel/config_model.py` and `src/shared_kernel/config.py`; all new settings should extend that chain.
- `config/global.yaml` already provides source descriptions/patterns but no default paths and no FineReport UI/runtime section. `SpecBuilder` therefore separately hard-codes source paths, while FineReport infrastructure separately hard-codes report names, filenames, UI labels, browser behavior, and wait timeouts.
- `FinereportClient` already loads `ConfigLoader` for path settings and lazily creates `YieldDownloadService`; this confirms a backward-compatible injection path for the typed FineReport settings.
- `AppConfig` currently validates `paths`, `llm`, `logging`, `report`, `agent`, and `products`, then ignores every other YAML key. Adding typed `source_files` and `report_download` roots (plus `agent.daily_report`) is required before editing YAML, exactly matching the coding convention.
- The least-duplicated schema is: source catalog entries own `description`, `pattern`, `filename`, and optional `default_path`; FineReport settings own only portal directory, parameter labels, browser behavior, and wait timeouts; Agent daily-report settings own generator installation/CLI/output integration defaults.
- Preserve `DailyReportRequest` legacy fields for old TaskSpecs, add an explicit `generator_root`, and stop interpreting generator configuration through `source_files`. Newly generated fixed-flow specs should contain only `report_date` for the daily-report call.
- `query_parser.py` duplicates every report display name in both `REPORT_TYPE_META` and the LLM system prompt. The prompt should be rendered from the validated source catalog; general extraction instructions may remain code because they are parser behavior, while report-specific names/purposes/sources/aliases/filters belong in YAML.
- `DataAcquisitionOrchestrator` repeats the daily report display name in every success/error branch. Injecting or loading the same typed source catalog once and resolving descriptions by alias removes these duplicates without coupling acquisition to the public daily-report generator.
- FineReport service tests currently import program-level business constants. They should construct typed settings/catalog entries and assert the injected behavior, proving there is one YAML/Pydantic ownership boundary rather than mirrored constants.
- Wrapper tests explicitly enforce the wrong behavior (implicit Agent workspace, report-date-to-16:00 override, source-file magic keys). Rewrite them to enforce omission of `--workspace` by default, forwarding only explicit `generator_now`, and explicit typed `generator_root`.
- `SpecBuilder._build_workflow` currently embeds template, product, source, sections, analysis, output, inspection, and timeout values into the `daily_report` call even though the external CLI wrapper does not own them. Its new fixed-flow call should be exactly the stable Agent input (`report_date`) plus no generator business payload.
- Existing config test fixtures intentionally omit the new sections. New Pydantic sections therefore need safe structural defaults, while consumers that require a named entry should raise a focused configuration error or accept explicit injected test settings.
- `REPORT_TYPE_META` has multiple existing consumers (`analysis_query_parser`, `analysis_file_resolver`), so retain it as a compatibility view derived from validated config while adding injectable/dynamic metadata at parser/orchestrator boundaries.
- The parser's report-type prompt block contains only report-specific catalog rows plus generic extraction rules. Replace those rows with a renderer over typed entries; no LLM behavior needs to be removed or moved into the public daily-report generator.
- Test fixtures intentionally load minimal YAML and rely on Pydantic defaults. New config sections therefore need safe structural defaults, while runtime helpers should raise clear errors only when a required source/skill entry is actually used.
- The pytest fixture resets `ConfigLoader` singleton state between tests. Runtime code should call `ConfigLoader().get()` rather than retain a separate cached `AppConfig` at module import when tests need configurable isolation.
- Current design references are internally stale. `design-agent_skill_boundary.md` still describes `daily_report` as a local writer consuming analysis facts and returning RequiredActions, while `skill_contract.md` says the wrapper defaults to the Agent repo as run root. Both conflict with the installed public skill contract and must be corrected.
- `rules_boundary.md` says report aliases/required sources are Spec-owned and frequently changing rules must not be hard-coded in Python. A sound split is: validated YAML provides project defaults/catalog metadata; individual Specs may override aliases/filters; the public generator owns Mod0-Mod4 business behavior.
- The relevant design files currently live under the user's untracked `references/plan_references/` reorganization. Edits should target that on-disk location and avoid recreating the deleted tracked tree.
- Root `ARCHITECTURE.md` repeats the incorrect claim that the wrapper uses the Agent repo as its default run root. It must say the public CLI uses its own installed skill root unless an explicit compatibility workspace override is supplied.
- `shared_kernel.md` documents the Pydantic-before-YAML rule but does not yet list Agent skill integration, source catalog, or report-download settings. It should be updated when those models are added.
- `design-spec_builder.md` correctly allows `daily_report` as a fixed flow; it should additionally state that the generated SkillCall uses the minimal public-wrapper input rather than embedding report business inputs.
- `SpecBuilder.LOCAL_SOURCE_FILES` duplicates default paths for five aliases. TaskSpec defaults should come from the same typed source-file entries used by local discovery and result labels.
- The target report literal appears in active program code outside the wrapper: `application/orchestrator.py` (repeated request construction), `infrastructure/yield_download_service.py` (report/filename constants), `agent/spec_builder.py` (default name/path), `core/query_parser.py` (source descriptions/prompt text), and `data_analysis/daily_report_analysis.py` (filename pattern). It also appears in `config/global.yaml`, tests, docs, scripts, templates, and historical runtime traces.
- The literal is not present inside the primary `daily_report/native_pipeline.py` path. The scattered values are mainly source-download/spec/parser concerns, not parameters that should be forwarded into public daily-report generation.
- Historical files under `specs/runs/` are runtime traces and must not be normalized as source configuration; tests may retain literal fixture names when they verify external contracts.
- CodeGraph is internally inconsistent for `native_pipeline.py`: the verbatim current function body calls `_resolve_generator_root` and `_run_generator_cli`, while its trail references older `_resolve_orchestrator_root`/`_run_orchestrator_cli`, and direct node lookup cannot find the new helpers. This indicates unindexed working-tree edits or a stale symbol graph; on-disk source is authoritative for this file.
- Git shows no changes in `daily_report/native_pipeline.py`, `implementation.py`, or `models.py`; the CodeGraph mismatch is an index-staleness problem, not an overlapping local edit in those files.
- The repository has extensive unrelated reference-tree changes: many tracked files under `references/` are deleted while `references/plan_references/` is untracked, plus an unrelated XMind edit and an untracked resource directory. These belong to the user and must not be reverted or swept into this refactor.
- The exact-literal CodeGraph question did not locate usable occurrences of `V3CT修正良率及不良率By月周天报表`; repository text search is now appropriate because the required CodeGraph-first attempt has been completed.

## Decisions
| Decision | Rationale |
|---|---|
| Treat the public CLI as the only execution boundary for daily-report business logic. | The public skill's Runtime Contract explicitly assigns business values and orchestration to itself. |
| Do not assume every matching literal belongs to `daily_report`; trace each caller and owner first. | The same report name may be used by download/UI/Agent request code with different ownership. |
| Preserve the project `SkillTool` facade (`tool.py`, Pydantic request, `SkillResult`) while replacing its implementation boundary. | Existing Agent runtime callers depend on the project contract; only the business engine should move behind the public CLI. |
| Centralize Agent-owned report source metadata rather than passing report-name literals into the public daily-report wrapper. | FineReport acquisition and TaskSpec construction are project responsibilities, distinct from Mod0-Mod4 report generation. |
| Model wrapper installation/CLI/output defaults as Agent configuration, not public business configuration. | The project must know how to locate and invoke the public skill, while the public skill remains responsible for what the report does. |
| Omit `--workspace` unless a caller explicitly requests the compatibility override. | The public CLI derives its normal workspace from its own installed repository; forcing the Agent repo changes ownership and resource resolution. |
| Do not synthesize `16:00` in the wrapper. | Date/time business policy belongs to the public skill config; the wrapper may forward an explicitly supplied timestamp or date. |
| Extend the existing `AppConfig`/`ConfigLoader` chain. | It already provides the project-required Pydantic validation and YAML/environment layering; another settings mechanism would fragment configuration further. |
| Add typed `source_files` entries to `AppConfig` instead of moving the existing YAML block elsewhere. | The intended central location already exists; the defect is that Pydantic ignores it and program code duplicates it. |
| Add `DailyReportRequest.generator_root` and keep `source_files` semantically pure. | Installation/runtime overrides are not source workbook aliases and should be validated by Pydantic as their own fields. |
| Separate `source_files` metadata from `report_download.finereport` UI/portal settings. | Report aliases/paths/patterns are shared domain metadata; portal labels, directory, and timeouts belong to the FineReport adapter. |
| Inject FineReport download settings into `YieldDownloadService`. | The service is the sole consumer of portal UI details, and constructor injection keeps infrastructure configuration explicit/testable. |
| Simplify newly built `daily_report` SkillCalls to the public wrapper surface. | Keeping legacy inputs in the model preserves old specs, but continuing to generate them would perpetuate the obsolete project-owned business contract. |
| Keep FineReport secrets in `.env`; move only non-secret operational settings to YAML/Pydantic. | This preserves the security boundary while centralizing legitimate configuration values. |
| Update the current moved design references to describe external delegation. | Leaving the old local-generation/Agent-workspace narrative would recreate the same boundary violation during future maintenance. |
| Remove program-level exported business constants and update tests to assert injected config behavior. | A constant that simply mirrors YAML still creates dual sources of truth and encourages future callers to bypass Pydantic. |
| Render report-specific LLM prompt content from `SourceFileConfig` entries. | Exact report names and per-source descriptions/aliases/filters are configuration; only the generic extraction procedure remains parser code. |
| Fail on an invalid explicit generator workspace and omit workspace when none is configured. | Silent fallback hides bad input; omission restores the public CLI's own-root default contract. |

## Issues / Risks
- The public `SKILL.md` displayed mojibake under the first default-encoding read; it was re-read as UTF-8 before using Chinese values.
- The working tree may contain unrelated user changes and must be audited before editing.
- The stale CodeGraph result makes a working-tree audit especially important before modifying `native_pipeline.py`; those helper changes may already belong to the user.
- Documentation edits must follow the current on-disk reference layout carefully because the tracked `references/design/` tree is being moved/reorganized in unrelated work.
- `daily_report` and `data_analysis` both mention daily-report behavior. Their runtime ownership may differ, and changing the latter without caller evidence would exceed scope.
- Because CodeGraph contains removed symbols for this area, final verification must combine current-text search with focused tests.
- One guessed fixed-flow test filename did not exist; test discovery must use `rg --files` rather than inferred names.

## Resources
- `AGENTS.md`
- `ARCHITECTURE.md`
- `references/index.md`
- `references/dev_references/coding_spec/coding_conventions.md`
- `C:\Users\V0141351\.agents\skills\daily-report-generator\SKILL.md`

## External / Untrusted Content
- None. All inputs are local project or user-owned skill files.
