# Coding Conventions

- Add `from __future__ import annotations` to new Python modules.
- Use type annotations for new functions and methods.
- Update Pydantic config models before changing configuration files.
- Keep Core logic mostly pure; browser, Excel, filesystem, and network IO belong in infrastructure or adapters.
- Use the shared LLM manager for LLM calls; do not instantiate provider clients in business code.
- Keep existing public entrypoints compatible unless the user explicitly asks for a breaking refactor.
- Add dependencies only through project dependency files and explain why existing dependencies are insufficient.
- Prefer focused tests for parser, selector, Skill contract, file naming, logging, and download behavior.

