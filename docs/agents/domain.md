# Domain Docs

This is a single-context repository. Engineering skills use the following documentation when exploring or changing domain behavior.

## Before exploring, read these

- Root `CONTEXT.md` for domain language, operating model, and hard boundaries.
- Relevant decisions under `docs/ADR/`.
- `references/design_references/domain/GLOSSARY.md` for stable OLED manufacturing terminology.

If a referenced document does not exist, proceed with the available evidence. Do not create domain documents speculatively.

## Consumer Rules

- Use the vocabulary defined in `CONTEXT.md` and the glossary in issue titles, plans, hypotheses, tests, and design proposals.
- Surface conflicts with an existing ADR explicitly; do not silently override a recorded decision.
- When a needed term is absent, treat it as a potential documentation gap and record it for the appropriate design discussion.

## Layout

```text
repository root/
|- CONTEXT.md
|- docs/ADR/
|- references/design_references/domain/
`- src/
```
