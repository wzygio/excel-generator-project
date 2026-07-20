# Triage Labels

The engineering skills use five canonical triage roles. This file maps them to the state strings used by this repository's local Markdown issue tracker.

| Canonical role | Local state | Meaning |
|---|---|---|
| `needs-triage` | `needs-triage` | Maintainer needs to evaluate the issue. |
| `needs-info` | `needs-info` | Waiting on the reporter for more information. |
| `ready-for-agent` | `ready-for-agent` | Fully specified and ready for an agent to implement. |
| `ready-for-human` | `ready-for-human` | Requires human implementation. |
| `wontfix` | `wontfix` | Will not be actioned. |

When a skill refers to a triage role, write the corresponding local state string in the issue's `Status:` line. Use exactly one category, `bug` or `enhancement`, for each issue.
