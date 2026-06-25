# Development Reference Index

## Folder Routes

| Folder | When To Read | Read Guidance | Commands |
|---|---|---|---|
| `references/dev_references/coding_spec/` | Writing or refactoring code, adding modules, changing dependency or output-path practices. | Read the coding-spec index and the conventions document before editing code. | Run `uv run ruff check .`, targeted tests, and `uv run pyright` when typing risk is high. |
| `references/dev_references/restrictions/` | Touching secrets, user files, runtime outputs, portal sessions, destructive actions, or safety-sensitive flows. | Read the restrictions index and safety rules before acting. | Run `git status --short`; verify no secrets or runtime outputs are staged. |
| `references/dev_references/table/` | Working with Excel schemas, workbook templates, report columns, or table images. | Read the table index, then the schema/template area relevant to the file type. | Run focused parser/report tests and workbook smoke checks when table contracts change. |

## Update Rule

Use this area for coding rules, restrictions, reusable implementation knowledge, and stable development assets.
