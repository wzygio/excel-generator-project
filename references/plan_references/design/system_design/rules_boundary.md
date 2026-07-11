# Rules Boundary

Spec-owned rules are stable, repeatable, and user-maintainable. Put them in specs, templates, or documented Spec fields when code already supports the rule.

Examples of spec-owned rules:

- product models, dates, filters, and output expectations
- selectable analysis sections and reusable report parameters

Public-skill-owned rules stay behind that skill's public CLI. For `$daily-report-generator`, this includes Mod0-Mod4 ordering/dependencies, report-generation source names, date policy, workbook handoff, rendering, and validation behavior. The Agent project must not copy these values into Specs or Python wrappers.

Project configuration owns Agent integration and acquisition defaults. Report/source display names, filename patterns, default paths, FineReport directory/labels/browser timeouts, and public-skill installation paths live in `config/global.yaml` and are consumed only through `AppConfig` Pydantic models.

Code-owned logic belongs in typed Python modules.

Examples of code-owned logic:

- Excel reading, decryption, validation, and writing
- FineReport automation primitives and file download orchestration
- dataframe transformations and analyzers
- Skill request/result/error/artifact contracts
- security, filesystem, logging, and runtime trace handling

Do not hard-code frequently changing business rules in Python unless the user explicitly asks for a one-off experiment.
