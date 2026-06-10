# Yield Report Agent

This context describes the language of the yield-report Agent project: a system where users express report-generation intent, Codex coordinates skills, and stable code executes repeatable yield-report work.

## Language

**Task Chain**:
The runtime execution relationship between business abilities, currently `daily_report > data_analysis > report_download`. A task chain may use direct code calls or Runtime orchestration; it describes execution order, not user-facing rule editing.
_Avoid_: Rule chain, architecture chain

**Rule Iteration Mechanism**:
The user-facing mechanism for changing supported report rules without directly editing Python code. It describes how user changes are captured in a spec and interpreted by Codex or stable skill contracts.
_Avoid_: Runtime chain, execution chain

**Maintainable Rule Boundary**:
The allowed range of rule changes a user can make through spec or natural language without asking the system to redesign the project. It supports adding, removing, enabling, disabling, or parameterizing known rules, but not arbitrary code restructuring.
_Avoid_: Full customization, unrestricted self-maintenance

**Skill**:
A callable business ability exposed to Codex with a stable contract and Codex-readable instructions. A Skill is not the whole implementation; it is the interface through which Codex invokes stable code.
_Avoid_: Prompt-only module

**Spec**:
A user-editable task contract that records goals, inputs, selected rules, and output expectations for a yield-report run. A Spec is only executable when its fields map to supported Skill contracts or code-backed rule parameters.
_Avoid_: Free-form requirements document

**Harness**:
The project support structure that lets Codex understand intent, find the right context, execute safely, and verify its work. A Harness is a map and feedback system around the codebase, not a single prompt file.
_Avoid_: Prompt pack, documentation dump

**Knowledge System**:
The progressive-disclosure part of the Harness that points Codex from a short entry file to architecture, design, plans, specs, references, and generated facts.
_Avoid_: One giant AGENTS file, project encyclopedia

**Mechanical Constraint System**:
The executable rules that keep Codex work inside project boundaries, such as tests, type checks, lint checks, schemas, and structural checks.
_Avoid_: Style advice, informal preference

**Feedback and Garbage Collection System**:
The Harness mechanism for turning review findings, failures, stale docs, generated artifacts, and recurring cleanup needs into durable project updates.
_Avoid_: One-off cleanup note, forgotten TODO

## Example Dialogue

Developer: "Can the user change the daily report rule without editing code?"

Domain expert: "Only if the change is inside the Maintainable Rule Boundary. For example, changing the daily-yield cutoff hour is a Spec or config rule if code already supports that parameter."

Developer: "Does daily_report calling data_analysis mean the user can modify analysis rules?"

Domain expert: "No. That is the Task Chain. Rule Iteration Mechanism is separate: the Spec must expose a supported rule field, and the Skill or Codex must know how to apply it."
