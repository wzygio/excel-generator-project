# Safety Rules

- Do not print, commit, or copy secrets from `.env`, credentials, cookies, tokens, or internal portal sessions.
- Do not delete or overwrite user-provided Excel files under `resources/` unless explicitly asked.
- Do not commit runtime outputs from `output/`, `downloads/`, `specs/runs/`, `.pytest_cache/`, `.playwright-*`, or decrypted resource folders.
- If ignored files are still tracked, verify with Git before removing them from the index, and do so only when asked.
- Do not leave ad-hoc scripts or logs in the repository root; promote reusable scripts to `scripts/` or keep temporary artifacts in ignored output folders.
- Do not rewrite large modules, public contracts, or file formats unless the task explicitly asks for that scope.
- Preserve unrelated user changes in the working tree.

