# Rules Boundary

Spec-owned rules are stable, repeatable, and user-maintainable. Put them in specs, templates, or documented Spec fields when code already supports the rule.

Examples of spec-owned rules:

- report workflow steps and ordering
- report aliases and required source reports
- product models, dates, filters, and output expectations
- selectable analysis sections and reusable report parameters

Code-owned logic belongs in typed Python modules.

Examples of code-owned logic:

- Excel reading, decryption, validation, and writing
- FineReport automation primitives and file download orchestration
- dataframe transformations and analyzers
- Skill request/result/error/artifact contracts
- security, filesystem, logging, and runtime trace handling

Do not hard-code frequently changing business rules in Python unless the user explicitly asks for a one-off experiment.

